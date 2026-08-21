"""Risk scoring module for graduated autonomy.

This module separates TRADING RISK from GOVERNANCE RISK:

TRADING RISK:
- position size
- portfolio exposure
- volatility
- stop loss
- drawdown
- daily loss
- leverage

GOVERNANCE RISK:
- reversibility
- data scope
- regulatory category
- confidence

The governance risk score uses the four PS-9.1 dimensions:
1. reversibility
2. data scope
3. regulatory category
4. confidence (higher confidence = LOWER risk, so we invert)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .market_data import MarketSnapshot
from .predictor import ForecastSignal
from .governance import GOVERNANCE_ENGINE, RiskAssessment


@dataclass
class TradingRiskAssessment:
    """Assessment of trading-specific risk factors."""
    symbol: str
    
    # Position sizing risk
    position_size_pct: float
    portfolio_exposure: float
    
    # Volatility risk
    volatility: float
    atr_pct: float
    
    # Stop loss risk
    stop_distance_pct: float
    risk_reward_ratio: float
    
    # Drawdown risk
    max_drawdown_risk: float
    daily_loss_risk: float
    
    # Overall trading risk score (0-1)
    trading_risk_score: float
    
    # Limits
    limits: Dict[str, Any]
    
    def is_safe(self, max_risk: float = 0.25) -> bool:
        """Check if trading risk is within safe limits."""
        return self.trading_risk_score <= max_risk


@dataclass
class CombinedRiskAssessment:
    """Combined trading and governance risk assessment."""
    action_id: str
    action_type: str
    symbol: str
    
    trading_risk: TradingRiskAssessment
    governance_risk: RiskAssessment
    
    risk_score: float
    risk_level: str
    autonomy_level: str
    
    can_execute: bool


class RiskScorer:
    """Risk scorer for graduated autonomy.
    
    Separates TRADING RISK (financial safety) from GOVERNANCE RISK (autonomy level).
    
    The flow is:
    1. Trading Risk Engine: "Is this trade financially safe to size?"
    2. Graduated Autonomy Engine: "How much autonomy should this action receive?"
    """
    
    def __init__(self, model_confidence: float = 0.75) -> None:
        self.model_confidence = float(model_confidence)
        self.governance_engine = GOVERNANCE_ENGINE
    
    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        return (symbol or "").upper().strip()
    
    @staticmethod
    def _is_crypto(symbol: str) -> bool:
        normalized = (symbol or "").upper().strip()
        crypto_symbols = {"BTC", "ETH", "SOL", "DOGE", "USDT", "ADA", "XRP", "BNB", "AVAX", "LINK", "TRX"}
        return normalized in crypto_symbols or normalized.split("-")[0] in crypto_symbols
    
    def score_action(
        self,
        action: Dict[str, Any],
        market_snapshot: Optional[MarketSnapshot] = None,
        prediction: Optional[ForecastSignal] = None
    ) -> RiskAssessment:
        """Score action for GOVERNANCE risk using PS-9.1 dimensions.
        
        This is the main method for determining autonomy level.
        The four dimensions are:
        1. reversibility
        2. data_scope
        3. regulatory
        4. confidence (higher confidence = LOWER risk, so we invert)
        
        Args:
            action: Action dictionary
            market_snapshot: Market data snapshot
            prediction: Model prediction
            
        Returns:
            RiskAssessment with governance risk score and autonomy level
        """
        # Convert to dict for governance engine
        action_type = str(action.get("type", "hold")).lower()
        symbol = self._normalize_symbol(action.get("symbol") or action.get("portfolio", [""])[0] if action_type == "rebalance" else action.get("symbol"))
        
        action_dict = dict(action)
        snapshot_dict = None
        prediction_dict = None
        
        if market_snapshot:
            snapshot_dict = {
                'price': market_snapshot.price,
                'volatility': market_snapshot.volatility,
                'confidence': market_snapshot.confidence,
            }
        if prediction:
            prediction_dict = {
                'direction': prediction.direction,
                'confidence': prediction.confidence,
                'expected_return': prediction.expected_return,
            }
        
        # Use governance engine for risk assessment
        assessment = self.governance_engine.assess_risk(
            action_dict,
            snapshot_dict,
            prediction_dict,
            action_type
        )
        
        return assessment
    
    def assess_trading_risk(
        self,
        symbol: str,
        action: str,
        price: float,
        portfolio_equity: float,
        current_cash: float,
        position_size_pct: float = 0.0,
        volatility: float = 0.0,
        atr: Optional[float] = None,
        stop_distance_pct: float = 0.02,
        take_profit_pct: float = 0.04,
    ) -> TradingRiskAssessment:
        """Assess TRADING RISK (financial safety) for a proposed trade.
        
        This checks if the trade is financially safe to size.
        """
        action_upper = action.upper()
        
        # Hard limits
        max_position_size = 0.25
        max_portfolio_exposure = 0.80
        max_risk_per_trade = 0.02
        max_daily_loss = 0.05
        
        limits = {
            'max_position_size': max_position_size,
            'max_portfolio_exposure': max_portfolio_exposure,
            'max_risk_per_trade': max_risk_per_trade,
            'max_daily_loss': max_daily_loss,
        }
        
        # Calculate trading risk factors
        position_size_risk = position_size_pct / 100
        exposure_risk = min(position_size_pct / 100, 1.0)
        
        # Volatility risk
        volatility_risk = min(volatility * 100, 1.0) if volatility > 0 else 0.0
        
        # ATR risk
        atr_pct = atr / price if atr and price > 0 else 0.0
        atr_risk = min(atr_pct * 10, 1.0)
        
        # Stop loss risk
        stop_risk = min(stop_distance_pct * 5, 1.0)
        
        # Risk-reward ratio
        rr_ratio = take_profit_pct / stop_distance_pct if stop_distance_pct > 0 else 1.0
        rr_risk = 1.0 - min(rr_ratio / 5, 0.9)
        
        # Daily loss risk
        daily_loss_risk = 0.0
        
        # Max drawdown risk
        max_drawdown_risk = volatility_risk * 0.5
        
        # Calculate overall trading risk score
        trading_risk_score = (
            0.25 * position_size_risk +
            0.20 * exposure_risk +
            0.15 * volatility_risk +
            0.15 * atr_risk +
            0.10 * stop_risk +
            0.10 * rr_risk +
            0.05 * max_drawdown_risk
        )
        
        return TradingRiskAssessment(
            symbol=symbol,
            position_size_pct=position_size_pct,
            portfolio_exposure=position_size_pct,
            volatility=volatility,
            atr_pct=atr_pct,
            stop_distance_pct=stop_distance_pct,
            risk_reward_ratio=rr_ratio,
            max_drawdown_risk=max_drawdown_risk,
            daily_loss_risk=daily_loss_risk,
            trading_risk_score=min(max(0.0, trading_risk_score), 1.0),
            limits=limits,
        )
    
    def assess_combined_risk(
        self,
        action: Dict[str, Any],
        market_snapshot: Optional[MarketSnapshot] = None,
        prediction: Optional[ForecastSignal] = None,
        portfolio_equity: float = 100.0,
        current_cash: float = 100.0,
        position_size_pct: float = 0.0,
        atr: Optional[float] = None,
    ) -> CombinedRiskAssessment:
        """Assess both trading and governance risk together."""
        # Governance risk assessment
        governance_assessment = self.score_action(action, market_snapshot, prediction)
        
        # Trading risk assessment
        action_upper = str(action.get('type', 'hold')).upper()
        symbol = self._normalize_symbol(action.get('symbol', ''))
        price = float(action.get('price', 0) or (market_snapshot.price if market_snapshot else 0))
        volatility = float(action.get('volatility', 0) or (market_snapshot.volatility if market_snapshot else 0))
        
        trading_assessment = self.assess_trading_risk(
            symbol=symbol,
            action=action_upper,
            price=price,
            portfolio_equity=portfolio_equity,
            current_cash=current_cash,
            position_size_pct=position_size_pct,
            volatility=volatility,
            atr=atr,
        )
        
        # Combined risk: governance risk is primary for autonomy
        # Trading risk can veto execution if too high
        combined_score = governance_assessment.risk_score
        
        # If trading risk is too high, block execution regardless of governance
        can_execute = trading_assessment.is_safe()
        
        # Determine risk level and autonomy from governance assessment
        risk_level = governance_assessment.risk_level
        autonomy_level = governance_assessment.autonomy_level
        
        # If trading risk is unsafe, force to highest risk
        if not can_execute:
            risk_level = "high"
            autonomy_level = "review"
            combined_score = max(combined_score, 0.8)
        
        return CombinedRiskAssessment(
            action_id=governance_assessment.action_id,
            action_type=governance_assessment.action_type,
            symbol=governance_assessment.symbol,
            trading_risk=trading_assessment,
            governance_risk=governance_assessment,
            risk_score=round(combined_score, 4),
            risk_level=risk_level,
            autonomy_level=autonomy_level,
            can_execute=can_execute,
        )
