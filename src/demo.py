"""Deterministic demo mode for hackathon judging.

Provides three demo scenarios:
1. LOW-risk action -> AUTONOMOUS EXECUTION
2. MEDIUM-risk action -> USER CONFIRMATION  
3. HIGH-risk action -> HUMAN REVIEW QUEUE

Each demo generates audit entries and demonstrates the full governance flow.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .governance import GOVERNANCE_ENGINE
from .risk_scorer import RiskScorer
from .autonomy_router import AutonomyRouter
from .market_data import MarketSnapshot
from .predictor import ForecastSignal


class DemoEngine:
    """Engine for running deterministic demo scenarios."""
    
    def __init__(self):
        self.scorer = RiskScorer(model_confidence=0.75)
        self.router = AutonomyRouter()
        self.governance = GOVERNANCE_ENGINE
    
    def run_scenario(self, scenario_id: str) -> Dict[str, Any]:
        """Run a demo scenario through the full governance flow."""
        scenarios = {
            "demo_low": {
                "name": "Read-Only Query",
                "type": "read_only_query",
                "symbol": "BTC-USD",
                "expected": "autonomous",
                "confidence": 0.95,
                "volatility": 0.01,
                "price": 50000.0,
            },
            "demo_medium": {
                "name": "Medium Trade",
                "type": "medium_trade",
                "symbol": "ETH-USD", 
                "expected": "confirmation",
                "confidence": 0.75,
                "volatility": 0.05,
                "price": 2000.0,
                "quantity": 0.5,
            },
            "demo_high": {
                "name": "High-Impact Trade",
                "type": "high_impact_trade",
                "symbol": "AAPL",
                "expected": "review",
                "confidence": 0.5,
                "volatility": 0.10,
                "price": 150.0,
                "quantity": 1000.0,
            },
        }
        
        scenario = scenarios.get(scenario_id)
        if not scenario:
            return {"error": f"Unknown scenario: {scenario_id}"}
        
        decision_id = str(uuid.uuid4())
        action = {
            "action_id": decision_id,
            "type": scenario["type"],
            "symbol": scenario["symbol"],
            "price": scenario["price"],
            "confidence": scenario["confidence"],
        }
        if "quantity" in scenario:
            action["quantity"] = scenario["quantity"]
        
        market_snapshot = MarketSnapshot(
            symbol=scenario["symbol"],
            price=scenario["price"],
            volatility=scenario["volatility"],
            previous_close=scenario["price"] * 0.99,
            change_pct=1.0,
            confidence=scenario["confidence"],
        )
        
        prediction = ForecastSignal(
            symbol=scenario["symbol"],
            direction="bullish",
            expected_return=0.05,
            confidence=scenario["confidence"],
            summary="Demo",
        )
        
        # Governance risk assessment
        governance_assessment = self.scorer.score_action(action, market_snapshot, prediction)
        
        # Autonomy routing
        autonomy_decision = self.router.route(governance_assessment.risk_score)
        
        # Trading risk assessment
        trading_assessment = self.scorer.assess_trading_risk(
            symbol=scenario["symbol"],
            action=scenario["type"],
            price=scenario["price"],
            portfolio_equity=10000.0,
            current_cash=5000.0,
            position_size_pct=10.0,
            volatility=scenario["volatility"],
        )
        
        # Combined assessment
        combined = self.scorer.assess_combined_risk(
            action=action,
            market_snapshot=market_snapshot,
            prediction=prediction,
            portfolio_equity=10000.0,
            current_cash=5000.0,
            position_size_pct=10.0,
        )
        
        # Create proposal
        proposal = self.governance.create_trade_proposal(
            symbol=scenario["symbol"],
            action=scenario["type"],
            quantity=scenario.get("quantity", 0),
            price=scenario["price"],
            confidence=scenario["confidence"],
            strategy="demo",
            reason=f"Demo: {scenario['name']}",
            position_size_pct=10.0,
            risk_amount=200.0,
            stop_distance=scenario["price"] * 0.02,
        )
        
        # Determine outcome
        if combined.autonomy_level == "autonomous":
            status = "EXECUTED"
            outcome = "auto_executed"
        elif combined.autonomy_level == "confirmation":
            status = "PENDING_CONFIRMATION"
            outcome = "pending_confirmation"
        else:
            status = "QUEUED_FOR_REVIEW"
            outcome = "queued_for_review"
        
        return {
            "scenario": scenario_id,
            "name": scenario["name"],
            "governance_risk": {
                "score": governance_assessment.risk_score,
                "level": governance_assessment.risk_level,
                "autonomy": governance_assessment.autonomy_level,
                "breakdown": governance_assessment.breakdown,
                "policy_version": governance_assessment.policy_version,
            },
            "trading_risk": {
                "score": trading_assessment.trading_risk_score,
                "is_safe": trading_assessment.is_safe(),
            },
            "outcome": {
                "status": status,
                "outcome": outcome,
                "expected": scenario["expected"],
                "matched": outcome.startswith(scenario["expected"]),
            },
            "audit": {
                "decision_id": decision_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action_id": decision_id,
                "action_type": scenario["type"],
                "symbol": scenario["symbol"],
                "quantity": scenario.get("quantity"),
                "agent": "DemoEngine",
                "confidence": scenario["confidence"],
                "reversibility": governance_assessment.reversibility,
                "data_scope": governance_assessment.data_scope,
                "regulatory_category": governance_assessment.regulatory,
                "risk_score": governance_assessment.risk_score,
                "risk_level": governance_assessment.risk_level,
                "autonomy_level": governance_assessment.autonomy_level,
                "policy_version": governance_assessment.policy_version,
                "execution_status": status,
                "final_outcome": outcome,
            },
        }
    
    def run_all_demos(self) -> Dict[str, Any]:
        """Run all three demo scenarios."""
        results = {}
        for sid in ["demo_low", "demo_medium", "demo_high"]:
            results[sid] = self.run_scenario(sid)
        return {
            "status": "ok",
            "scenarios": results,
            "summary": {
                "demo_low": "LOW -> AUTONOMOUS -> EXECUTED",
                "demo_medium": "MEDIUM -> CONFIRMATION -> PENDING",
                "demo_high": "HIGH -> REVIEW -> QUEUED",
            },
        }
    
    def list_scenarios(self) -> List[Dict[str, Any]]:
        """List available scenarios."""
        return [
            {"id": "demo_low", "name": "Read-Only Query", "risk": "LOW", "autonomy": "AUTONOMOUS"},
            {"id": "demo_medium", "name": "Medium Trade", "risk": "MEDIUM", "autonomy": "CONFIRMATION"},
            {"id": "demo_high", "name": "High-Impact Trade", "risk": "HIGH", "autonomy": "REVIEW"},
        ]


DEMO_ENGINE = DemoEngine()


def run_demo_scenario(scenario_id: str) -> Dict[str, Any]:
    """Run a demo scenario by ID."""
    return DEMO_ENGINE.run_scenario(scenario_id)


def run_all_demos() -> Dict[str, Any]:
    """Run all demo scenarios."""
    return DEMO_ENGINE.run_all_demos()


def list_demo_scenarios() -> List[Dict[str, Any]]:
    """List available demo scenarios."""
    return DEMO_ENGINE.list_scenarios()


if __name__ == "__main__":
    result = run_all_demos()
    for sid, data in result["scenarios"].items():
        print(f"{sid}: {data['outcome']['outcome']} (expected: {data['outcome']['expected']})")
        print(f"  Risk: {data['governance_risk']['score']:.4f} -> {data['governance_risk']['autonomy']}")
