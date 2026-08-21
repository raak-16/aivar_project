"""Flask backend for Graduated Autonomy Engine.

Integrates:
- yfinance market data
- Kronos predictor
- TA-Lib technical analysis
- VectorBT backtesting
- TradingAgents (read-only research)
- Governance engine with PS-9.1 risk scoring
- Graduated autonomy routing
- Paper trading execution
- Full audit logging

Key architecture principle:
TradingAgents NEVER directly executes.
The only legal path to execution is:
  Agent Proposal -> Trading Risk Validation -> Graduated Autonomy Risk Assessment ->
  Autonomy Router -> AUTO / CONFIRM / REVIEW -> Approved -> Paper Executor -> Audit
"""

from __future__ import annotations

import json
import os
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from flask import Flask, jsonify, redirect, render_template, request, url_for
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv

# Import existing components
from .audit_logger import AuditLogger
from .autonomy_router import AutonomyRouter, DEFAULT_ROUTER
from .market_data import MarketDataProvider, MarketSnapshot
from .paper_trading import INITIAL_CASH, KronosPaperTrader
from .predictor import MarketPredictor, ForecastSignal
from .risk_scorer import RiskScorer
from .storage.sqlite_storage import SQLiteStorage
from .strategy import STRATEGIES, get_strategy
from .trade_executor import TradeExecutor
from .trading_agents_adapter import TradingAgentsAdapter, TradingAgentsUnavailableError

# Import new components
from .technical_analysis import TECHNICAL_ENGINE, calculate_indicators, generate_signal
from .position_sizer import POSITION_SIZER, size_position
from .strategy_engine import STRATEGY_ENGINE, generate_strategy_signal
from .backtester import BACKTESTER, run_simple_backtest
from .governance import (
    GOVERNANCE_ENGINE,
    RiskAssessment,
    TradeProposal,
    ActionType,
    AutonomyLevel,
)
from .demo import DEMO_ENGINE, run_demo_scenario, run_all_demos, list_demo_scenarios


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
app = Flask(__name__, template_folder=str(BASE_DIR / "templates"))
app.config["SECRET_KEY"] = "graduated-autonomy-demo"
socketio = SocketIO(app, cors_allowed_origins="*")

# Check if React frontend is available (built)
REACT_AVAILABLE = (BASE_DIR / "templates" / "react" / "index.html").exists()

WATCHLIST_SYMBOLS = ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "ADA-USD", "XRP-USD", "DOGE-USD", "AVAX-USD", "LINK-USD", "TRX-USD"]
MARKET_PROVIDER: Optional[MarketDataProvider] = None
MARKET_PREDICTOR: Optional[MarketPredictor] = None

# Autonomy decision interval (configurable, separate from market display)
AUTONOMY_DECISION_INTERVAL = int(os.environ.get("AUTONOMY_INTERVAL", "30"))  # seconds

# Initialize components
RISK_SCORER = RiskScorer(model_confidence=0.8)
AUDIT_LOGGER = AuditLogger(log_path=str(BASE_DIR / "audit.log"))


def get_market_provider() -> MarketDataProvider:
    global MARKET_PROVIDER
    if MARKET_PROVIDER is None:
        MARKET_PROVIDER = MarketDataProvider()
    return MARKET_PROVIDER


def get_market_predictor() -> MarketPredictor:
    global MARKET_PREDICTOR
    if MARKET_PREDICTOR is None:
        MARKET_PREDICTOR = MarketPredictor(get_market_provider())
    return MARKET_PREDICTOR


def get_trading_agents_adapter() -> TradingAgentsAdapter:
    return TradingAgentsAdapter(BASE_DIR)


def _coerce_symbol_list(value: str | None) -> List[str]:
    if not value:
        return WATCHLIST_SYMBOLS
    symbols = [symbol.strip().upper() for symbol in value.split(",") if symbol.strip()]
    return symbols or WATCHLIST_SYMBOLS


def _build_market_snapshot(symbol: str) -> Dict[str, Any]:
    """Build market snapshot for display (does NOT trigger decisions)."""
    provider = get_market_provider()
    predictor = get_market_predictor()
    snapshot = provider.fetch(symbol)
    signal = predictor.forecast(symbol)
    return {
        "symbol": snapshot.symbol,
        "price": round(float(snapshot.price), 2),
        "previous_close": round(float(snapshot.previous_close), 2) if snapshot.previous_close is not None else None,
        "change_pct": round(float(snapshot.change_pct), 4),
        "volatility": round(float(snapshot.volatility), 4),
        "source": snapshot.source,
        "direction": signal.direction,
        "confidence": round(float(signal.confidence), 4),
        "expected_return": round(float(signal.expected_return), 4),
        "summary": signal.summary,
    }


def _evaluate_action(action: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate action through full governance flow."""
    action_payload = dict(action)
    action_payload["type"] = str(action_payload.get("type", "hold")).lower()
    action_payload["symbol"] = str(action_payload.get("symbol") or action_payload.get("portfolio", ["AAPL"])[0]).upper()
    
    if action_payload["type"] == "rebalance":
        action_payload["portfolio"] = action_payload.get("portfolio", [])
    
    market_provider = get_market_provider()
    predictor = get_market_predictor()
    snapshot = market_provider.fetch(action_payload["symbol"])
    signal = predictor.forecast(action_payload["symbol"])
    
    if not action_payload.get("price") and snapshot:
        action_payload["price"] = snapshot.price
    
    # Use new governance-based risk assessment
    assessment = RISK_SCORER.score_action(action_payload, snapshot, prediction=signal)
    decision = DEFAULT_ROUTER.route(assessment.risk_score)
    
    return {
        "action": action_payload,
        "risk_score": assessment.risk_score,
        "breakdown": assessment.breakdown,
        "decision": decision.level,
        "decision_message": decision.message,
        "risk_level": assessment.risk_level,
        "autonomy_level": assessment.autonomy_level,
        "policy_version": assessment.policy_version,
        "summary": {
            "risk_band": decision.risk_level,
            "score": round(float(assessment.risk_score), 4),
        },
    }


def _evaluate_trade_proposal(
    symbol: str,
    action: str,
    quantity: float,
    price: float,
    confidence: float,
    strategy: str = "technical",
) -> Dict[str, Any]:
    """Evaluate a trade proposal through the full governance flow.
    
    This is the proper flow:
    TradingAgents Proposal -> Trading Risk Validation -> Governance Risk Assessment ->
    Autonomy Router -> AUTO / CONFIRM / REVIEW
    """
    # Step 1: Create structured TradeProposal
    proposal = GOVERNANCE_ENGINE.create_trade_proposal(
        symbol=symbol,
        action=action,
        quantity=quantity,
        price=price,
        confidence=confidence,
        strategy=strategy,
        entry_price=price,
        stop_loss=price * 0.98,  # 2% stop
        reason=f"Proposal for {action} {quantity} {symbol} @ ${price}",
        technical_signal="technical",
    )
    
    # Step 2: Get market data
    market_provider = get_market_provider()
    snapshot = market_provider.fetch(symbol)
    
    # Step 3: Position sizing (trading risk)
    storage = get_storage()
    account = storage.get_paper_account(INITIAL_CASH)
    current_cash = float(account["cash"])
    position = storage.get_paper_position(symbol)
    holdings_value = 0.0
    if position:
        holdings_value = float(position["quantity"]) * price
    portfolio_equity = float(account["cash"]) + holdings_value
    
    sizing_result = POSITION_SIZER.size_position(
        symbol=symbol,
        action=action,
        price=price,
        portfolio_equity=portfolio_equity,
        current_cash=current_cash,
        current_position=position,
        atr=snapshot.volatility * price if snapshot else None,
        volatility=snapshot.volatility if snapshot else 0.0,
    )
    
    # Step 4: Governance risk assessment
    action_payload = {
        "action_id": proposal.decision_id,
        "type": action.lower(),
        "symbol": symbol,
        "quantity": quantity,
        "price": price,
        "confidence": confidence,
    }
    
    assessment = RISK_SCORER.score_action(action_payload, snapshot)
    
    # Step 5: Autonomy routing
    autonomy_decision = DEFAULT_ROUTER.route(assessment.risk_score)
    
    # Step 6: Determine if can execute (trading risk check)
    trading_risk = RISK_SCORER.assess_trading_risk(
        symbol=symbol,
        action=action,
        price=price,
        portfolio_equity=portfolio_equity,
        current_cash=current_cash,
        position_size_pct=sizing_result.position_size_pct,
        volatility=snapshot.volatility if snapshot else 0.0,
    )
    can_execute = trading_risk.is_safe()
    
    # Step 7: Combined assessment
    combined = RISK_SCORER.assess_combined_risk(
        action=action_payload,
        market_snapshot=snapshot,
        portfolio_equity=portfolio_equity,
        current_cash=current_cash,
        position_size_pct=sizing_result.position_size_pct,
    )
    
    # Step 8: Log to audit
    AUDIT_LOGGER.log_decision(
        action_id=proposal.decision_id,
        action=action_payload,
        risk_score=assessment.risk_score,
        decision=autonomy_decision.level,
        status="EXECUTED" if autonomy_decision.level == "autonomous" and can_execute else "PENDING",
        symbol=symbol,
        quantity=quantity,
        agent="TradingAgents",
        confidence=confidence,
        reversibility=assessment.reversibility,
        data_scope=assessment.data_scope,
        regulatory_category=assessment.regulatory,
        risk_level=assessment.risk_level,
        autonomy_level=assessment.autonomy_level,
        policy_version=assessment.policy_version,
        execution_status="EXECUTED" if autonomy_decision.level == "autonomous" and can_execute else "PENDING",
    )
    
    return {
        "proposal": {
            "decision_id": proposal.decision_id,
            "action": proposal.action,
            "symbol": proposal.symbol,
            "quantity": proposal.quantity,
            "price": proposal.price,
            "confidence": proposal.confidence,
            "strategy": proposal.strategy,
            "stop_loss": proposal.stop_loss,
            "reason": proposal.reason,
        },
        "sizing": {
            "quantity": sizing_result.quantity,
            "notional": sizing_result.notional,
            "position_size_pct": sizing_result.position_size_pct,
            "risk_amount": sizing_result.risk_amount,
            "stop_distance": sizing_result.stop_distance,
            "stop_loss_price": sizing_result.stop_loss_price,
            "limits_hit": sizing_result.limits_hit,
            "rationale": sizing_result.rationale,
        },
        "trading_risk": {
            "score": trading_risk.trading_risk_score,
            "is_safe": can_execute,
            "limits": trading_risk.limits,
        },
        "governance_risk": {
            "score": assessment.risk_score,
            "level": assessment.risk_level,
            "autonomy_level": assessment.autonomy_level,
            "breakdown": assessment.breakdown,
            "policy_version": assessment.policy_version,
        },
        "autonomy_decision": {
            "level": autonomy_decision.level,
            "message": autonomy_decision.message,
            "risk_level": autonomy_decision.risk_level,
        },
        "combined": {
            "risk_score": combined.risk_score,
            "risk_level": combined.risk_level,
            "autonomy_level": combined.autonomy_level,
            "can_execute": combined.can_execute,
        },
        "final_status": "EXECUTED" if autonomy_decision.level == "autonomous" and can_execute else 
                       "PENDING_CONFIRMATION" if autonomy_decision.level == "confirm" else
                       "QUEUED_FOR_REVIEW",
    }


def get_storage() -> SQLiteStorage:
    return SQLiteStorage(db_path=str(BASE_DIR / "data" / "local.db"))


def _paper_portfolio(storage: SQLiteStorage) -> Dict[str, Any]:
    account = storage.get_paper_account(INITIAL_CASH)
    positions = storage.list_paper_positions()
    holdings_value = 0.0
    for position in positions:
        price = float(get_market_provider().fetch(position["symbol"]).price)
        position["market_price"] = round(price, 4)
        position["market_value"] = round(float(position["quantity"]) * price, 2)
        holdings_value += position["market_value"]
    return {
        "cash": round(float(account["cash"]), 2),
        "holdings_value": round(holdings_value, 2),
        "equity": round(float(account["cash"]) + holdings_value, 2),
        "positions": positions,
        "trades": storage.list_paper_trades(),
    }


def reset_local_state() -> None:
    db_path = BASE_DIR / "data" / "local.db"
    log_path = BASE_DIR / "audit.log"
    for path in [db_path, log_path]:
        if path.exists():
            path.unlink()


def seed_demo_data(reset_db: bool = False) -> None:
    if reset_db:
        reset_local_state()
    storage = get_storage()
    storage.get_paper_account(INITIAL_CASH)


@app.route("/")
def index() -> str:
    # Serve React app if available
    if REACT_AVAILABLE:
        return app.send_static_file("react/index.html")
    
    # Fall back to Jinja2 template
    # Removed warm_kronos() - now controlled by DISABLE_KRONOS env var
    reset_requested = os.environ.get("RESET_LOCAL_DB", "").lower() in {"1", "true", "yes"}
    seed_demo_data(reset_db=reset_requested)
    storage = get_storage()
    actions = storage.list_actions()
    confirmations = storage.list_confirmations()
    reviews = storage.list_reviews()
    logs = storage.list_audit_logs()
    predictor = get_market_predictor()
    provider = get_market_provider()

    # Limit symbols for memory efficiency
    display_symbols = WATCHLIST_SYMBOLS[:int(os.environ.get("DASHBOARD_SYMBOL_COUNT", "3"))]
    
    market_overview = {}
    watchlist = []
    for symbol in display_symbols:
        snapshot = provider.fetch(symbol)
        signal = predictor.forecast(symbol)
        market_overview[symbol] = {
            "direction": signal.direction,
            "confidence": signal.confidence,
            "expected_return": signal.expected_return,
            "summary": signal.summary,
        }
        change_pct = float(snapshot.change_pct)
        price = float(snapshot.price)
        watchlist.append({
            "symbol": symbol,
            "price": round(price, 2),
            "change_pct": round(change_pct, 2),
            "direction": signal.direction,
            "confidence": round(signal.confidence, 4),
        })

    summary = {
        "total_actions": len(actions),
        "pending_confirmations": sum(1 for item in confirmations if item.get("status") == "PENDING"),
        "open_reviews": sum(1 for item in reviews if item.get("status") == "OPEN"),
        "latest_log": logs[0] if logs else {},
    }
    paper_portfolio = _paper_portfolio(storage)
    active_strategy = storage.get_setting("paper_strategy", "adaptive")
    
    # Get demo scenarios for display
    demo_scenarios = list_demo_scenarios()
    
    return render_template(
        "index.html",
        actions=actions[:5],
        confirmations=confirmations[:5],
        reviews=reviews[:5],
        logs=logs[:8],
        summary=summary,
        market_overview=market_overview,
        watchlist=watchlist,
        paper_portfolio=paper_portfolio,
        active_strategy=active_strategy,
        current_date=date.today().isoformat(),
        demo_scenarios=demo_scenarios,
        autonomy_interval=AUTONOMY_DECISION_INTERVAL,
    )


@app.route("/react")
def react_app() -> str:
    """Serve React frontend if available."""
    if REACT_AVAILABLE:
        return app.send_static_file("react/index.html")
    return redirect("/")


def _market_payload() -> Dict[str, Any]:
    """Market data payload for Socket.IO (display only, no decisions)."""
    # Reduced for memory: only 2 workers, only first 3 symbols
    max_workers = int(os.environ.get("MARKET_WORKERS", "2"))
    symbols_to_fetch = WATCHLIST_SYMBOLS[:int(os.environ.get("MARKET_SYMBOL_COUNT", "3"))]
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        symbols = list(pool.map(_build_market_snapshot, symbols_to_fetch))
    return {
        "symbols": symbols,
        "count": len(symbols),
        "updated_at": int(time.time() * 1000),
        "kronos_status": MarketPredictor.kronos_status(),
    }


@socketio.on("connect")
def handle_connect() -> None:
    emit("market_update", _market_payload())


@socketio.on("request_market")
def handle_request_market() -> None:
    emit("market_update", _market_payload())


def stream_market_updates() -> None:
    """Stream market data updates (configurable interval, default 30s for memory)."""
    update_interval = int(os.environ.get("MARKET_UPDATE_INTERVAL", "30"))
    while True:
        socketio.emit("market_update", _market_payload())
        socketio.sleep(update_interval)


def autonomous_decision_loop() -> None:
    """Separate loop for autonomous trading decisions (configurable interval).
    
    This is SEPARATE from market display updates.
    Market display: 2 second refresh (Socket.IO)
    Autonomous decisions: configurable interval (default 30 seconds)
    
    Chart polling (1s) does NOT trigger this loop.
    """
    while True:
        try:
            # Only run if autonomy is enabled
            if os.environ.get("ENABLE_AUTONOMY", "true").lower() in {"1", "true", "yes"}:
                storage = get_storage()
                active_strategy_key = storage.get_setting("paper_strategy", "adaptive")
                strategy = get_strategy(active_strategy_key)
                
                for symbol in WATCHLIST_SYMBOLS[:int(os.environ.get("AUTONOMY_SYMBOL_COUNT", "3"))]:
                    try:
                        # Get market data
                        provider = get_market_provider()
                        predictor = get_market_predictor()
                        snapshot = provider.fetch(symbol)
                        signal = predictor.forecast(symbol)
                        
                        # Skip heavy operations in memory-saving mode
                        if os.environ.get("MEMORY_SAVE_MODE", "false").lower() == "true":
                            # Lightweight path: only use signal, skip history/backtest/indicators
                            decision_action = "HOLD"  # Default to no action
                        else:
                            history, _ = provider.history(symbol)
                            position = storage.get_paper_position(symbol)
                            
                            # Get technical indicators
                            indicators = TECHNICAL_ENGINE.calculate_indicators(history, symbol)
                            
                            # Get strategy signal
                            strategy_signal = STRATEGY_ENGINE.generate_signal(history, symbol)
                            
                            # Get backtest metrics
                            backtest_result = run_simple_backtest(history, symbol, "combined")
                            backtest_metrics = backtest_result.metrics.to_dict()
                            
                            # Strategy decision
                            decision = strategy.decide(
                                history, signal, float(position["average_price"]) if position else None
                            )
                            decision_action = decision.action
                        
                        # Determine action
                        if decision_action == "HOLD":
                            continue
                            
                        action = decision_action
                        
                        # Evaluate through governance (skip if in memory save mode)
                        if os.environ.get("MEMORY_SAVE_MODE", "false").lower() == "true":
                            # Skip evaluation in memory save mode
                            eval_result = None
                        else:
                            position = storage.get_paper_position(symbol)
                            eval_result = _evaluate_trade_proposal(
                                symbol=symbol,
                                action=action,
                                quantity=0.01 if action == "BUY" else (float(position["quantity"]) if position else 0),
                                price=float(snapshot.price),
                                confidence=signal.confidence,
                                strategy=active_strategy_key,
                            )
                        
                        # Only execute if autonomous and safe (and not in memory save mode)
                        if eval_result and eval_result["combined"]["autonomy_level"] == "autonomous" and eval_result["combined"]["can_execute"]:
                            # Execute paper trade
                            if os.environ.get("MEMORY_SAVE_MODE", "false").lower() == "true":
                                # Skip trade execution in memory save mode
                                trade_result = None
                            else:
                                trader = KronosPaperTrader(storage)
                                trade_result = trader.trade(
                                    symbol=symbol,
                                    price=float(snapshot.price),
                                    signal=signal,
                                    action=action,
                                    allocation=decision.allocation,
                                    sell_fraction=decision.sell_fraction,
                                    rationale=decision.rationale,
                                )
                            
                            # Log execution
                            AUDIT_LOGGER.log_action_execution(
                                action_id=eval_result["proposal"]["decision_id"],
                                action=eval_result["proposal"],
                                risk_assessment=RISK_SCORER.score_action(
                                    eval_result["proposal"],
                                    snapshot,
                                    signal
                                ),
                                autonomy_level="autonomous",
                                status="EXECUTED",
                                user="autonomous_agent",
                            )
                            
                            if trade_result:
                                print(f"[AUTONOMY] Executed {action} {symbol} @ ${snapshot.price:.2f}")
                        
                        elif eval_result and eval_result["combined"]["autonomy_level"] == "confirmation":
                            # Queue for confirmation
                            storage.save_confirmation(
                                eval_result["proposal"]["decision_id"],
                                eval_result["governance_risk"]["score"],
                                "PENDING"
                            )
                            print(f"[AUTONOMY] Queued {action} {symbol} for confirmation (risk: {eval_result['governance_risk']['score']:.4f})")
                        
                        elif eval_result and eval_result["combined"]["autonomy_level"] == "review":
                            # Queue for human review
                            storage.save_review(
                                eval_result["proposal"]["decision_id"],
                                eval_result["governance_risk"]["score"],
                                "OPEN",
                                "human-review"
                            )
                            print(f"[AUTONOMY] Queued {action} {symbol} for review (risk: {eval_result['governance_risk']['score']:.4f})")
                        
                        # Store action (skip if in memory save mode)
                        if eval_result:
                            storage.create_action(
                                eval_result["proposal"],
                                eval_result["governance_risk"]["score"],
                                "EXECUTED" if eval_result["combined"]["autonomy_level"] == "autonomous" and eval_result["combined"]["can_execute"] else
                                "PENDING_CONFIRMATION" if eval_result["combined"]["autonomy_level"] == "confirmation" else
                                "QUEUED_FOR_REVIEW"
                            )
                        else:
                            # In memory save mode, just log
                            print(f"[AUTONOMY] Skipped {action} {symbol} (memory save mode)")
                        
                        # Sleep between symbols to avoid rate limiting
                        time.sleep(1)
                        
                    except Exception as e:
                        print(f"[AUTONOMY] Error processing {symbol}: {e}")
                        continue
                
            # Sleep for the full interval
            time.sleep(AUTONOMY_DECISION_INTERVAL)
            
        except Exception as e:
            print(f"[AUTONOMY LOOP] Error: {e}")
            time.sleep(10)


@app.route("/api/market")
def api_market() -> Any:
    symbols = _coerce_symbol_list(request.args.get("symbols"))
    data = [_build_market_snapshot(symbol) for symbol in symbols]
    return jsonify({
        "symbols": data,
        "count": len(data),
        "updated_at": int(time.time() * 1000),
        "kronos_status": MarketPredictor.kronos_status(),
    })


@app.route("/api/forecast")
def api_forecast() -> Any:
    symbols = _coerce_symbol_list(request.args.get("symbols"))
    data = []
    for symbol in symbols:
        snapshot = _build_market_snapshot(symbol)
        data.append({
            "symbol": symbol,
            "direction": snapshot["direction"],
            "confidence": snapshot["confidence"],
            "expected_return": snapshot["expected_return"],
            "summary": snapshot["summary"],
        })
    return jsonify({"signals": data, "count": len(data)})


@app.route("/api/financial-analysis", methods=["POST"])
def api_financial_analysis() -> Any:
    """Run TradingAgents research (read-only, no execution)."""
    payload = request.get_json(silent=True) or request.form.to_dict()
    symbol = str(payload.get("symbol", "")).upper().strip()
    trade_date = payload.get("trade_date")
    if not symbol:
        return jsonify({"error": "A symbol is required."}), 400
    
    try:
        result = get_trading_agents_adapter().analyze(symbol, trade_date)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except TradingAgentsUnavailableError as exc:
        return jsonify({"error": str(exc)}), 503
    except Exception:
        app.logger.exception("TradingAgents analysis failed for %s", symbol)
        return jsonify({"error": "Financial analysis failed. Check the server log."}), 502
    
    # Evaluate the TradingAgents proposal through governance
    final_decision = result.get("final_trade_decision", "HOLD").upper()
    confidence = result.get("analysis", {}).get("confidence", 0.75)
    
    # Get market data for governance evaluation
    snapshot = get_market_provider().fetch(symbol)
    prediction = get_market_predictor().forecast(symbol)
    
    # Create action from TradingAgents result
    action = {
        "type": final_decision.lower(),
        "symbol": symbol,
        "confidence": confidence,
    }
    
    # Run through governance
    governance_eval = _evaluate_action(action)
    
    # Add governance info to response
    result["governance"] = {
        "risk_score": governance_eval["risk_score"],
        "risk_level": governance_eval.get("risk_level", "medium"),
        "autonomy_level": governance_eval["autonomy_level"],
        "decision": governance_eval["decision"],
        "breakdown": governance_eval["breakdown"],
        "policy_version": governance_eval.get("policy_version", "v1"),
    }
    
    return jsonify({"analysis": result, "execution": "not_started"})


@app.route("/api/chart")
def api_chart() -> Any:
    """Chart endpoint - DISPLAY ONLY, does NOT trigger trading decisions.
    
    Returns historical actual OHLCV data and forecast/predicted data for display.
    The frontend displays both on the same chart:
    - Blue line: Actual historical prices (what actually happened)
    - Amber dashed line: Forecast/predicted prices (what the model predicts)
    """
    symbol = str(request.args.get("symbol", WATCHLIST_SYMBOLS[0])).upper().strip()
    if symbol not in WATCHLIST_SYMBOLS:
        return jsonify({"error": "Symbol is not in the dashboard watchlist."}), 400
    history, source = get_market_provider().history(symbol)
    forecast, backend = get_market_predictor().chart_forecast(history)
    return jsonify({
        "symbol": symbol,
        "source": source,
        "model": backend,
        "actual": [{"time": row.timestamp.isoformat(), "close": round(float(row.close), 8)} for row in history.itertuples()],
        "prediction": [{"time": row.timestamp.isoformat(), "close": round(float(row.close), 8)} for row in forecast.itertuples()],
    })


@app.route("/api/paper-trade", methods=["POST"])
def api_paper_trade() -> Any:
    """Execute a paper trade through full governance flow."""
    payload = request.get_json(silent=True) or request.form.to_dict()
    symbol = str(payload.get("symbol", WATCHLIST_SYMBOLS[0])).upper().strip()
    if symbol not in WATCHLIST_SYMBOLS:
        return jsonify({"error": "Symbol is not in the dashboard watchlist."}), 400
    
    snapshot = get_market_provider().fetch(symbol)
    signal = get_market_predictor().forecast(symbol)
    storage = get_storage()
    position = storage.get_paper_position(symbol)
    history, _ = get_market_provider().history(symbol)
    strategy_key = storage.get_setting("paper_strategy", "adaptive")
    
    # Get strategy decision
    decision = get_strategy(strategy_key).decide(
        history, signal, float(position["average_price"]) if position else None
    )
    
    # Evaluate through governance
    eval_result = _evaluate_trade_proposal(
        symbol=symbol,
        action=decision.action,
        quantity=0.01,  # Will be recalculated by position sizer
        price=float(snapshot.price),
        confidence=signal.confidence,
        strategy=strategy_key,
    )
    
    # Only execute if autonomous or approved
    if eval_result["combined"]["autonomy_level"] == "autonomous" and eval_result["combined"]["can_execute"]:
        result = KronosPaperTrader(storage).trade(
            symbol, float(snapshot.price), signal,
            action=decision.action,
            allocation=decision.allocation,
            sell_fraction=decision.sell_fraction,
            rationale=decision.rationale,
        )
        status = "EXECUTED"
    else:
        result = None
        status = eval_result["final_status"]
    
    return jsonify({
        "trade": result.__dict__ if result else None,
        "signal": {"direction": signal.direction, "confidence": signal.confidence, "summary": signal.summary},
        "decision": decision.__dict__,
        "strategy": strategy_key,
        "governance": eval_result,
        "portfolio": _paper_portfolio(storage),
        "status": status,
    })


@app.route("/api/decisions", methods=["GET", "POST"])
def api_decisions() -> Any:
    if request.method == "GET":
        symbols = _coerce_symbol_list(request.args.get("symbols"))
        results = []
        for symbol in symbols:
            market = _build_market_snapshot(symbol)
            evaluation = _evaluate_action({"type": "hold", "symbol": symbol})
            results.append({
                "symbol": symbol,
                "price": market["price"],
                "decision": evaluation["decision"],
                "risk_score": evaluation["risk_score"],
                "breakdown": evaluation["breakdown"],
                "risk_level": evaluation.get("risk_level", "medium"),
                "autonomy_level": evaluation["autonomy_level"],
                "summary": evaluation["summary"],
            })
        return jsonify({"results": results, "count": len(results)})

    payload = request.get_json(silent=True) or request.form.to_dict()
    if not payload:
        return jsonify({"error": "No action payload supplied."}), 400

    action = {
        "type": payload.get("type", "hold"),
        "symbol": payload.get("symbol", "AAPL"),
        "quantity": float(payload.get("quantity", 0) or 0),
        "price": float(payload.get("price", 0) or 0),
        "order_type": payload.get("order_type", "market"),
    }
    if payload.get("portfolio"):
        action["portfolio"] = payload.get("portfolio")
    action["action_id"] = payload.get("action_id") or str(uuid.uuid4())

    evaluation = _evaluate_action(action)
    decision_status = (
        "EXECUTED"
        if evaluation["decision"] == "autonomous"
        else "PENDING_CONFIRMATION"
        if evaluation["decision"] == "confirm"
        else "QUEUED_FOR_REVIEW"
    )

    storage = get_storage()
    storage.create_action(action, float(evaluation["risk_score"]), decision_status)
    storage.log_audit(action["action_id"], float(evaluation["risk_score"]), evaluation["decision"], evaluation["breakdown"])
    if evaluation["decision"] == "confirm":
        storage.save_confirmation(action["action_id"], float(evaluation["risk_score"]), "PENDING")
    elif evaluation["decision"] == "review":
        storage.save_review(action["action_id"], float(evaluation["risk_score"]), "OPEN", "human-review")

    evaluation["action_id"] = action["action_id"]
    evaluation["status"] = decision_status
    return jsonify(evaluation)


@app.route("/api/governance/evaluate", methods=["POST"])
def api_governance_evaluate() -> Any:
    """Evaluate an action through the governance engine."""
    payload = request.get_json(silent=True) or request.form.to_dict()
    if not payload:
        return jsonify({"error": "No action payload supplied."}), 400
    
    action = dict(payload)
    action_id = action.get("action_id") or str(uuid.uuid4())
    action["action_id"] = action_id
    
    # Get market data if symbol provided
    symbol = action.get("symbol")
    market_snapshot = None
    prediction = None
    
    if symbol:
        try:
            provider = get_market_provider()
            predictor = get_market_predictor()
            market_snapshot = provider.fetch(symbol)
            prediction = predictor.forecast(symbol)
        except Exception:
            pass
    
    # Run governance assessment
    assessment = RISK_SCORER.score_action(action, market_snapshot, prediction)
    
    # Route to autonomy level
    autonomy_decision = DEFAULT_ROUTER.route(assessment.risk_score)
    
    # Trading risk assessment
    trading_assessment = None
    can_execute = True
    
    if action.get("type") in ["trade", "buy", "sell", "medium_trade", "high_impact_trade"]:
        storage = get_storage()
        account = storage.get_paper_account(INITIAL_CASH)
        current_cash = float(account["cash"])
        position = storage.get_paper_position(symbol) if symbol else None
        holdings_value = 0.0
        if position and symbol:
            try:
                holdings_value = float(position["quantity"]) * float(market_snapshot.price) if market_snapshot else 0
            except Exception:
                pass
        portfolio_equity = float(account["cash"]) + holdings_value
        
        trading_assessment = RISK_SCORER.assess_trading_risk(
            symbol=symbol or "",
            action=str(action.get("type", "trade")),
            price=float(action.get("price", 0) or (market_snapshot.price if market_snapshot else 0)),
            portfolio_equity=portfolio_equity,
            current_cash=current_cash,
            position_size_pct=10.0,  # Default
        )
        can_execute = trading_assessment.is_safe()
    
    # Combined assessment
    combined = RISK_SCORER.assess_combined_risk(
        action=action,
        market_snapshot=market_snapshot,
        portfolio_equity=10000.0,
        current_cash=5000.0,
        position_size_pct=10.0,
    )
    
    # Log to audit
    AUDIT_LOGGER.log_decision(
        action_id=action_id,
        action=action,
        risk_score=assessment.risk_score,
        decision=autonomy_decision.level,
        status="EXECUTED" if autonomy_decision.level == "autonomous" and can_execute else "PENDING",
        symbol=symbol or "",
        quantity=action.get("quantity"),
        agent=action.get("agent", "api"),
        confidence=action.get("confidence"),
        reversibility=assessment.reversibility,
        data_scope=assessment.data_scope,
        regulatory_category=assessment.regulatory,
        risk_level=assessment.risk_level,
        autonomy_level=assessment.autonomy_level,
        policy_version=assessment.policy_version,
    )
    
    return jsonify({
        "action_id": action_id,
        "assessment": {
            "risk_score": assessment.risk_score,
            "risk_level": assessment.risk_level,
            "autonomy_level": assessment.autonomy_level,
            "breakdown": assessment.breakdown,
            "policy_version": assessment.policy_version,
        },
        "autonomy": {
            "level": autonomy_decision.level,
            "message": autonomy_decision.message,
            "risk_level": autonomy_decision.risk_level,
        },
        "trading_risk": {
            "score": trading_assessment.trading_risk_score if trading_assessment else None,
            "is_safe": can_execute,
        } if trading_assessment else None,
        "combined": {
            "can_execute": combined.can_execute,
        },
        "final_status": "EXECUTED" if autonomy_decision.level == "autonomous" and can_execute else 
                       "PENDING_CONFIRMATION" if autonomy_decision.level == "confirm" else
                       "QUEUED_FOR_REVIEW",
    })


@app.route("/api/governance/decision/<decision_id>")
def api_governance_decision(decision_id: str) -> Any:
    """Get details of a governance decision."""
    storage = get_storage()
    action = storage.get_action(decision_id)
    if not action:
        return jsonify({"error": "Decision not found"}), 404
    
    # Get related data
    confirmations = [c for c in storage.list_confirmations() if c.get("action_id") == decision_id]
    reviews = [r for r in storage.list_reviews() if r.get("action_id") == decision_id]
    
    return jsonify({
        "action": action,
        "confirmations": confirmations,
        "reviews": reviews,
    })


@app.route("/api/agent/propose", methods=["POST"])
def api_agent_propose() -> Any:
    """Submit a trade proposal from an agent (TradingAgents)."""
    payload = request.get_json(silent=True) or request.form.to_dict()
    if not payload:
        return jsonify({"error": "No proposal payload supplied."}), 400
    
    required_fields = ["action", "symbol", "confidence"]
    for field in required_fields:
        if field not in payload:
            return jsonify({"error": f"Missing required field: {field}"}), 400
    
    # Create proposal
    proposal = GOVERNANCE_ENGINE.create_trade_proposal(
        symbol=str(payload["symbol"]),
        action=str(payload["action"]),
        quantity=float(payload.get("quantity", 0)),
        price=float(payload.get("price", 0)),
        confidence=float(payload["confidence"]),
        strategy=payload.get("strategy", "agent"),
        entry_price=float(payload.get("entry_price", 0)),
        stop_loss=float(payload.get("stop_loss", 0)),
        take_profit=float(payload.get("take_profit")) if payload.get("take_profit") else None,
        reason=payload.get("reason", ""),
        technical_signal=payload.get("technical_signal", ""),
        backtest_metrics=payload.get("backtest_metrics"),
    )
    
    # Get market data
    snapshot = get_market_provider().fetch(proposal.symbol)
    prediction = get_market_predictor().forecast(proposal.symbol)
    
    # Evaluate through governance
    action_payload = {
        "action_id": proposal.decision_id,
        "type": proposal.action.lower(),
        "symbol": proposal.symbol,
        "quantity": proposal.quantity,
        "price": proposal.price,
        "confidence": proposal.confidence,
    }
    
    eval_result = _evaluate_trade_proposal(
        symbol=proposal.symbol,
        action=proposal.action,
        quantity=proposal.quantity,
        price=proposal.price,
        confidence=proposal.confidence,
        strategy=proposal.strategy,
    )
    
    # Store in database
    storage = get_storage()
    status = eval_result["final_status"]
    storage.create_action(action_payload, eval_result["governance_risk"]["score"], status)
    
    if eval_result["combined"]["autonomy_level"] == "confirmation":
        storage.save_confirmation(proposal.decision_id, eval_result["governance_risk"]["score"], "PENDING")
    elif eval_result["combined"]["autonomy_level"] == "review":
        storage.save_review(proposal.decision_id, eval_result["governance_risk"]["score"], "OPEN", "human-review")
    
    # Log to audit
    AUDIT_LOGGER.log_action_execution(
        action_id=proposal.decision_id,
        action=action_payload,
        risk_assessment=RISK_SCORER.score_action(action_payload, snapshot, prediction),
        autonomy_level=eval_result["combined"]["autonomy_level"],
        status=status,
        user="TradingAgents",
    )
    
    return jsonify({
        "proposal": proposal.to_dict(),
        "evaluation": eval_result,
        "status": status,
        "decision_id": proposal.decision_id,
    })


@app.route("/api/agent/status")
def api_agent_status() -> Any:
    """Get agent status."""
    return jsonify({
        "status": "active",
        "governance_policy": GOVERNANCE_ENGINE.policy.to_dict(),
        "autonomy_enabled": os.environ.get("ENABLE_AUTONOMY", "true").lower() in {"1", "true", "yes"},
        "autonomy_interval": AUTONOMY_DECISION_INTERVAL,
    })


@app.route("/api/agent/start", methods=["POST"])
def api_agent_start() -> Any:
    """Start autonomous decision loop."""
    global autonomy_thread
    if not hasattr(app, 'autonomy_thread') or not app.autonomy_thread.is_alive():
        app.autonomy_thread = threading.Thread(
            target=autonomous_decision_loop,
            name="autonomy-loop",
            daemon=True
        )
        app.autonomy_thread.start()
        return jsonify({"status": "started", "message": "Autonomous decision loop started"})
    return jsonify({"status": "already_running"})


@app.route("/api/agent/stop", methods=["POST"])
def api_agent_stop() -> Any:
    """Stop autonomous decision loop (not fully implemented - daemon thread)."""
    return jsonify({"status": "ok", "message": "Use environment variable ENABLE_AUTONOMY=false to disable"})


@app.route("/api/technical-analysis/<symbol>")
def api_technical_analysis(symbol: str) -> Any:
    """Get technical analysis for a symbol."""
    symbol = symbol.upper().strip()
    provider = get_market_provider()
    history, _ = provider.history(symbol)
    
    if history.empty:
        return jsonify({"error": f"No history data for {symbol}"}), 404
    
    # Calculate indicators
    indicators = TECHNICAL_ENGINE.calculate_indicators(history, symbol)
    
    # Generate signal
    signal = TECHNICAL_ENGINE.generate_signal(indicators)
    
    return jsonify({
        "symbol": symbol,
        "indicators": {
            "close": indicators.close,
            "sma_20": indicators.sma_20,
            "sma_50": indicators.sma_50,
            "ema_20": indicators.ema_20,
            "ema_50": indicators.ema_50,
            "rsi_14": indicators.rsi_14,
            "macd": indicators.macd,
            "macd_signal": indicators.macd_signal,
            "macd_histogram": indicators.macd_histogram,
            "adx": indicators.adx,
            "atr_14": indicators.atr_14,
            "bb_upper": indicators.bb_upper,
            "bb_middle": indicators.bb_middle,
            "bb_lower": indicators.bb_lower,
            "volume_sma_20": indicators.volume_sma_20,
            "roc_1": indicators.roc_1,
            "roc_5": indicators.roc_5,
            "roc_10": indicators.roc_10,
        },
        "signal": {
            "action": signal.signal,
            "score": signal.score,
            "confidence": signal.confidence,
            "reasons": signal.reasons,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@app.route("/api/backtest/<symbol>")
def api_backtest(symbol: str) -> Any:
    """Run a backtest on a symbol."""
    symbol = symbol.upper().strip()
    provider = get_market_provider()
    history, _ = provider.history(symbol)
    
    if history.empty:
        return jsonify({"error": f"No history data for {symbol}"}), 404
    
    # Run backtest
    result = run_simple_backtest(history, symbol, "combined")
    
    return jsonify(result.to_dict())


@app.route("/api/demo/scenarios")
def api_demo_scenarios() -> Any:
    """List available demo scenarios."""
    return jsonify({"scenarios": list_demo_scenarios()})


@app.route("/api/demo/<scenario_id>")
def api_demo_scenario(scenario_id: str) -> Any:
    """Run a demo scenario."""
    return jsonify(run_demo_scenario(scenario_id))


@app.route("/api/demo/all")
def api_demo_all() -> Any:
    """Run all demo scenarios."""
    return jsonify(run_all_demos())


@app.route("/api/policy")
def api_policy() -> Any:
    """Get current governance policy."""
    return jsonify(GOVERNANCE_ENGINE.policy.to_dict())


@app.route("/api/policy/version")
def api_policy_version() -> Any:
    """Get policy version."""
    return jsonify({"version": GOVERNANCE_ENGINE.policy.version})


@socketio.on("request_autonomy_status")
def handle_autonomy_status() -> None:
    """WebSocket handler for autonomy status."""
    emit("autonomy_status", {
        "enabled": os.environ.get("ENABLE_AUTONOMY", "true").lower() in {"1", "true", "yes"},
        "interval": AUTONOMY_DECISION_INTERVAL,
    })


@socketio.on("run_demo")
def handle_run_demo(data: Dict[str, Any]) -> None:
    """WebSocket handler to run a demo scenario."""
    scenario_id = data.get("scenario_id", "demo_low")
    result = run_demo_scenario(scenario_id)
    emit("demo_result", result)


@app.route("/strategies", methods=["GET", "POST"])
def strategies() -> str | Any:
    storage = get_storage()
    if request.method == "POST":
        selected = str(request.form.get("strategy", "adaptive"))
        if selected not in STRATEGIES:
            return jsonify({"error": "Unknown strategy."}), 400
        storage.set_setting("paper_strategy", selected)
        return redirect(url_for("strategies"))
    active_strategy = storage.get_setting("paper_strategy", "adaptive")
    cards = [{"key": key, "name": cls.name, "description": cls.description} for key, cls in STRATEGIES.items()]
    return render_template("strategies.html", strategies=cards, active_strategy=active_strategy, paper_portfolio=_paper_portfolio(storage))


@app.route("/api/confirmations", methods=["POST"])
def api_confirmation_action() -> Any:
    payload = request.get_json(silent=True) or request.form.to_dict()
    action_id = payload.get("action_id")
    decision = payload.get("decision", "reject")
    if not action_id:
        return jsonify({"error": "Missing action_id."}), 400

    storage = get_storage()
    action = storage.get_action(action_id)
    if action is None:
        return jsonify({"error": "Action not found."}), 404

    approved = decision == "approve"
    storage.update_action_status(action_id, "CONFIRMED" if approved else "REJECTED")
    storage.save_confirmation(action_id, float(action.get("risk_score", 0)), "APPROVED" if approved else "REJECTED")
    
    # Log to audit
    AUDIT_LOGGER.log_decision(
        action_id=action_id,
        action=action,
        risk_score=float(action.get("risk_score", 0)),
        decision="CONFIRMED" if approved else "REJECTED",
        status="CONFIRMED" if approved else "REJECTED",
        user_reviewer="user",
        final_outcome="CONFIRMED" if approved else "REJECTED",
    )
    
    # If approved, execute the trade
    if approved:
        try:
            symbol = action.get("symbol", "AAPL")
            snapshot = get_market_provider().fetch(symbol)
            signal = get_market_predictor().forecast(symbol)
            trader = KronosPaperTrader(storage)
            result = trader.trade(
                symbol=symbol,
                price=float(snapshot.price),
                signal=signal,
                action=action.get("action_type", "buy"),
            )
            AUDIT_LOGGER.log_decision(
                action_id=action_id,
                action=action,
                risk_score=float(action.get("risk_score", 0)),
                decision="EXECUTED",
                status="EXECUTED",
                final_outcome="EXECUTED",
            )
        except Exception as e:
            app.logger.error(f"Failed to execute approved trade {action_id}: {e}")
    
    return jsonify({"status": "ok", "action_id": action_id, "approved": approved})


@app.route("/confirmations", methods=["GET", "POST"])
def confirmations() -> str | Any:
    storage = get_storage()
    if request.method == "POST":
        action_id = request.form.get("action_id")
        decision = request.form.get("decision")
        action = storage.get_action(action_id) if action_id else None
        if action is not None:
            approved = decision == "approve"
            storage.update_action_status(action_id, "CONFIRMED" if approved else "REJECTED")
            storage.save_confirmation(action_id, float(action["risk_score"]), "APPROVED" if approved else "REJECTED")
        return redirect(url_for("confirmations"))

    pending = []
    for item in storage.list_actions():
        if item.get("status") in {"PENDING_CONFIRMATION", "CONFIRMED", "REJECTED"}:
            pending.append(item)
    return render_template("index.html", actions=pending, confirmations=pending, reviews=storage.list_reviews()[:5], logs=storage.list_audit_logs()[:8], summary={})


@app.route("/reviews")
def reviews() -> str:
    storage = get_storage()
    review_list = storage.list_reviews()
    return render_template("index.html", actions=storage.list_actions()[:5], confirmations=storage.list_confirmations()[:5], reviews=review_list[:10], logs=storage.list_audit_logs()[:8], summary={})


@app.route("/audit")
def audit() -> str:
    storage = get_storage()
    return render_template("index.html", actions=storage.list_actions()[:5], confirmations=storage.list_confirmations()[:5], reviews=storage.list_reviews()[:5], logs=storage.list_audit_logs()[:12], summary={})


# Start background tasks at module level (runs on import, works with gunicorn)
# Warm Kronos only if not disabled (saves ~1-4GB RAM)
MarketPredictor.warm_kronos()

# Start market updates background task (reduced frequency saves memory)
socketio.start_background_task(stream_market_updates)

# Start autonomy loop if enabled (disabled by default for memory)
if os.environ.get("ENABLE_AUTONOMY", "false").lower() in {"1", "true", "yes"}:
    app.autonomy_thread = threading.Thread(
        target=autonomous_decision_loop,
        name="autonomy-loop",
        daemon=True
    )
    app.autonomy_thread.start()
    print("Autonomous decision loop started")


if __name__ == "__main__":
    reset_requested = "--reset-db" in sys.argv or os.environ.get("RESET_LOCAL_DB", "").lower() in {"1", "true", "yes"}
    if reset_requested:
        reset_local_state()
    seed_demo_data(reset_db=reset_requested)
    socketio.run(app, debug=False, host="127.0.0.1", port=5000)
