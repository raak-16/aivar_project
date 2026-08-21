"""Generic governance engine for graduated autonomy.

This module implements a domain-independent governance engine that can handle
various types of actions (READ, UPDATE, TRADE, DELETE, BULK_DELETE, etc.)
with configurable risk scoring and autonomy routing.

The key concept: "The AI does not get the same level of autonomy for every action."
The autonomy level must dynamically depend on the risk of the proposed action.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class ActionType(Enum):
    """Generic action types for governance."""
    READ = "read"
    UPDATE = "update"
    TRADE = "trade"
    DELETE = "delete"
    BULK_DELETE = "bulk_delete"
    REBALANCE = "rebalance"
    READ_ONLY_QUERY = "read_only_query"
    SINGLE_RECORD_UPDATE = "single_record_update"
    MEDIUM_TRADE = "medium_trade"
    HIGH_IMPACT_TRADE = "high_impact_trade"


class RiskLevel(Enum):
    """Risk level classifications."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AutonomyLevel(Enum):
    """Autonomy level classifications."""
    AUTONOMOUS = "autonomous"
    CONFIRMATION = "confirmation"
    REVIEW = "review"


@dataclass
class GovernancePolicy:
    """Centralized governance policy configuration.
    
    Contains risk weights, autonomy thresholds, and policy metadata.
    Every decision records the policy version.
    """
    # Policy metadata
    version: str = "graduated-autonomy-v1"
    description: str = "PS-9.1 Graduated Autonomy Policy"
    
    # Risk weights (0-1, sum to 1.0)
    risk_weights: Dict[str, float] = field(default_factory=lambda: {
        "reversibility": 0.2,
        "data_scope": 0.3,
        "regulatory": 0.3,
        "confidence": 0.2,
    })
    
    # Autonomy thresholds
    autonomy_thresholds: Dict[str, float] = field(default_factory=lambda: {
        "low": 0.3,
        "medium": 0.7,
    })
    
    # Risk limits
    risk_limits: Dict[str, Any] = field(default_factory=lambda: {
        "max_risk_per_trade": 0.02,
        "max_position_size": 0.25,
        "max_portfolio_exposure": 0.80,
        "max_daily_loss": 0.05,
    })
    
    # Action type mappings to risk categories
    action_risk_categories: Dict[str, str] = field(default_factory=lambda: {
        "read": "low",
        "read_only_query": "low",
        "update": "medium",
        "single_record_update": "medium",
        "trade": "medium",
        "medium_trade": "medium",
        "delete": "high",
        "bulk_delete": "high",
        "rebalance": "medium",
        "high_impact_trade": "high",
    })
    
    # Regulatory category mappings
    regulatory_categories: Dict[str, float] = field(default_factory=lambda: {
        "crypto": 0.0,
        "stock": 1.0,
        "forex": 0.5,
        "commodity": 0.7,
        "etf": 0.6,
        "unknown": 0.5,
    })
    
    @classmethod
    def load_from_file(cls, policy_path: str = "config/governance_policy.json") -> "GovernancePolicy":
        """Load policy from JSON file."""
        path = Path(policy_path)
        if not path.exists():
            # Return default policy
            return cls()
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return cls(
                    version=data.get('version', 'graduated-autonomy-v1'),
                    description=data.get('description', 'PS-9.1 Graduated Autonomy Policy'),
                    risk_weights=data.get('risk_weights', cls().risk_weights),
                    autonomy_thresholds=data.get('autonomy_thresholds', cls().autonomy_thresholds),
                    risk_limits=data.get('risk_limits', cls().risk_limits),
                    action_risk_categories=data.get('action_risk_categories', cls().action_risk_categories),
                    regulatory_categories=data.get('regulatory_categories', cls().regulatory_categories),
                )
        except (json.JSONDecodeError, IOError):
            return cls()
    
    def save_to_file(self, policy_path: str = "config/governance_policy.json") -> None:
        """Save policy to JSON file."""
        path = Path(policy_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert policy to dictionary."""
        return {
            'version': self.version,
            'description': self.description,
            'risk_weights': self.risk_weights,
            'autonomy_thresholds': self.autonomy_thresholds,
            'risk_limits': self.risk_limits,
            'action_risk_categories': self.action_risk_categories,
            'regulatory_categories': self.regulatory_categories,
        }
    
    def get_risk_weight(self, dimension: str) -> float:
        """Get weight for a risk dimension."""
        return self.risk_weights.get(dimension, 0.0)
    
    def get_threshold(self, level: str) -> float:
        """Get threshold for autonomy level."""
        level = level.lower()
        if level == "low":
            return self.autonomy_thresholds.get("low", 0.3)
        elif level == "medium":
            return self.autonomy_thresholds.get("medium", 0.7)
        return 1.0
    
    def get_action_category(self, action_type: str) -> str:
        """Get risk category for an action type."""
        return self.action_risk_categories.get(action_type.lower(), "medium")
    
    def get_regulatory_score(self, symbol: str) -> float:
        """Get regulatory score for a symbol."""
        # Extract category from symbol
        symbol_upper = symbol.upper()
        if symbol_upper.endswith("-USD") or symbol_upper in {"BTC", "ETH", "SOL", "DOGE", "USDT", "ADA", "XRP", "BNB", "AVAX", "LINK", "TRX"}:
            return self.regulatory_categories.get("crypto", 0.0)
        # Add more mappings as needed
        return self.regulatory_categories.get("unknown", 0.5)


@dataclass
class RiskAssessment:
    """Governance risk assessment with four PS-9.1 dimensions."""
    action_id: str
    action_type: str
    symbol: str
    
    # Raw dimension scores (0-1)
    reversibility: float
    data_scope: float
    regulatory: float
    confidence: float
    
    # Calculated risk score (0-1)
    risk_score: float
    
    # Risk level
    risk_level: str
    
    # Autonomy level
    autonomy_level: str
    
    # Policy version
    policy_version: str
    
    # Breakdown
    breakdown: Dict[str, float]
    
    # Additional context
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TradeProposal:
    """Structured trade proposal for governance evaluation.
    
    This is the contract that goes through:
    TradingAgents -> Trading Risk Engine -> Graduated Autonomy Engine
    
    Only after governance approval can it reach PaperTradeExecutor.
    """
    decision_id: str
    action: str  # BUY, SELL, HOLD
    symbol: str
    quantity: float
    price: float
    confidence: float
    strategy: str
    entry_price: float
    stop_loss: float
    take_profit: Optional[float] = None
    reason: str = ""
    technical_signal: str = ""
    backtest_metrics: Optional[Dict[str, Any]] = None
    position_size_pct: float = 0.0
    risk_amount: float = 0.0
    stop_distance: float = 0.0
    
    # Metadata
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    agent: str = "TradingAgents"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert proposal to dictionary."""
        return {
            'decision_id': self.decision_id,
            'action': self.action,
            'symbol': self.symbol,
            'quantity': self.quantity,
            'price': self.price,
            'confidence': self.confidence,
            'strategy': self.strategy,
            'entry_price': self.entry_price,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'reason': self.reason,
            'technical_signal': self.technical_signal,
            'backtest_metrics': self.backtest_metrics,
            'position_size_pct': self.position_size_pct,
            'risk_amount': self.risk_amount,
            'stop_distance': self.stop_distance,
            'created_at': self.created_at,
            'agent': self.agent,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TradeProposal":
        """Create proposal from dictionary."""
        return cls(
            decision_id=data.get('decision_id', ''),
            action=data.get('action', 'HOLD'),
            symbol=data.get('symbol', ''),
            quantity=float(data.get('quantity', 0)),
            price=float(data.get('price', 0)),
            confidence=float(data.get('confidence', 0)),
            strategy=data.get('strategy', ''),
            entry_price=float(data.get('entry_price', 0)),
            stop_loss=float(data.get('stop_loss', 0)),
            take_profit=float(data.get('take_profit')) if data.get('take_profit') is not None else None,
            reason=data.get('reason', ''),
            technical_signal=data.get('technical_signal', ''),
            backtest_metrics=data.get('backtest_metrics'),
            position_size_pct=float(data.get('position_size_pct', 0)),
            risk_amount=float(data.get('risk_amount', 0)),
            stop_distance=float(data.get('stop_distance', 0)),
            created_at=data.get('created_at', datetime.now(timezone.utc).isoformat()),
            agent=data.get('agent', 'TradingAgents'),
        )


@dataclass
class GovernanceDecision:
    """Final governance decision with all audit information."""
    decision_id: str
    action_id: str
    action: Dict[str, Any]
    risk_assessment: RiskAssessment
    autonomy_level: str
    status: str  # PENDING, APPROVED, REJECTED, EXECUTED, BLOCKED
    timestamp: str
    
    # Audit fields (PS-9.1 requirements)
    symbol: str
    quantity: Optional[float] = None
    agent: str = ""
    confidence: float = 0.0
    reversibility: float = 0.0
    data_scope: float = 0.0
    regulatory_category: float = 0.0
    risk_score: float = 0.0
    risk_level: str = ""
    policy_version: str = ""
    execution_status: str = ""
    confirmation_id: Optional[str] = None
    review_id: Optional[str] = None
    user_reviewer: Optional[str] = None
    final_outcome: Optional[str] = None
    reason: str = ""
    
    def to_audit_dict(self) -> Dict[str, Any]:
        """Convert to audit log dictionary with all PS-9.1 fields."""
        return {
            'decision_id': self.decision_id,
            'timestamp': self.timestamp,
            'action': self.action.get('type', self.action.get('action', 'unknown')),
            'symbol': self.symbol,
            'resource': self.symbol,
            'quantity': self.quantity,
            'agent': self.agent,
            'confidence': self.confidence,
            'reversibility': self.reversibility,
            'data_scope': self.data_scope,
            'regulatory_category': self.regulatory_category,
            'risk_score': self.risk_score,
            'risk_level': self.risk_level,
            'autonomy_level': self.autonomy_level,
            'policy_version': self.policy_version,
            'execution_status': self.execution_status,
            'confirmation_id': self.confirmation_id,
            'review_id': self.review_id,
            'user_reviewer': self.user_reviewer,
            'final_outcome': self.final_outcome,
            'reason': self.reason,
        }


class GovernanceEngine:
    """Main governance engine for graduated autonomy.
    
    Implements the PS-9.1 requirements:
    - LOW RISK -> AUTONOMOUS EXECUTION
    - MEDIUM RISK -> USER CONFIRMATION -> EXECUTION
    - HIGH RISK -> HUMAN REVIEW QUEUE -> HUMAN APPROVAL -> EXECUTION
    
    Every decision is auditable with all four PS-9.1 risk dimensions.
    """
    
    def __init__(self, policy: Optional[GovernancePolicy] = None):
        self.policy = policy or self._load_default_policy()
    
    def _load_default_policy(self) -> GovernancePolicy:
        """Load default policy from file or create new."""
        # Try to load from config directory
        base_dir = Path(__file__).parent.parent
        policy_path = base_dir / "config" / "governance_policy.json"
        if policy_path.exists():
            return GovernancePolicy.load_from_file(str(policy_path))
        return GovernancePolicy()
    
    def assess_risk(
        self,
        action: Dict[str, Any],
        market_snapshot: Optional[Dict[str, Any]] = None,
        prediction: Optional[Dict[str, Any]] = None,
        action_type: Optional[str] = None,
    ) -> RiskAssessment:
        """Assess governance risk using PS-9.1 four dimensions.
        
        The four dimensions:
        1. reversibility - How reversible is the action?
        2. data_scope - How much data/records does it affect?
        3. regulatory_category - What regulatory category?
        4. confidence - Confidence level (higher confidence = LOWER risk)
        
        Args:
            action: Action dictionary with type, symbol, quantity, etc.
            market_snapshot: Market data snapshot
            prediction: Model prediction
            action_type: Override action type
            
        Returns:
            RiskAssessment with all dimensions and final score
        """
        import uuid
        
        action_id = str(action.get('action_id') or action.get('decision_id') or uuid.uuid4())
        action_type_str = action_type or str(action.get('type') or action.get('action', 'unknown')).lower()
        symbol = str(action.get('symbol') or action.get('portfolio', [''])[0] if action_type_str == 'rebalance' else '')
        
        # Dimension 1: Reversibility
        # Higher = harder to reverse = higher risk
        reversibility = self._calculate_reversibility(action, action_type_str)
        
        # Dimension 2: Data Scope
        # Higher = more data affected = higher risk
        data_scope = self._calculate_data_scope(action, action_type_str)
        
        # Dimension 3: Regulatory Category
        # Higher = more regulated = higher risk
        regulatory = self._calculate_regulatory(symbol)
        
        # Dimension 4: Confidence
        # IMPORTANT: High confidence = LOWER risk, so we invert
        # confidence_risk = 1 - confidence
        confidence = self._calculate_confidence(action, market_snapshot, prediction)
        confidence_risk = 1.0 - confidence  # Invert so high confidence reduces risk
        
        # Calculate weighted risk score
        weights = self.policy.risk_weights
        risk_score = (
            weights.get('reversibility', 0.2) * reversibility +
            weights.get('data_scope', 0.3) * data_scope +
            weights.get('regulatory', 0.3) * regulatory +
            weights.get('confidence', 0.2) * confidence_risk
        )
        risk_score = max(0.0, min(1.0, risk_score))
        
        # Determine risk level
        if risk_score < self.policy.get_threshold('low'):
            risk_level = RiskLevel.LOW.value
            autonomy_level = AutonomyLevel.AUTONOMOUS.value
        elif risk_score <= self.policy.get_threshold('medium'):
            risk_level = RiskLevel.MEDIUM.value
            autonomy_level = AutonomyLevel.CONFIRMATION.value
        else:
            risk_level = RiskLevel.HIGH.value
            autonomy_level = AutonomyLevel.REVIEW.value
        
        # Build breakdown
        breakdown = {
            'reversibility': round(reversibility, 4),
            'data_scope': round(data_scope, 4),
            'regulatory': round(regulatory, 4),
            'confidence': round(confidence, 4),  # Store original confidence, not inverted
            'confidence_risk': round(confidence_risk, 4),  # Store the risk component
        }
        
        return RiskAssessment(
            action_id=action_id,
            action_type=action_type_str,
            symbol=symbol,
            reversibility=round(reversibility, 4),
            data_scope=round(data_scope, 4),
            regulatory=round(regulatory, 4),
            confidence=round(confidence, 4),
            risk_score=round(risk_score, 4),
            risk_level=risk_level,
            autonomy_level=autonomy_level,
            policy_version=self.policy.version,
            breakdown=breakdown,
            metadata={
                'action': action,
                'market_snapshot': market_snapshot,
                'prediction': prediction,
            }
        )
    
    def _calculate_reversibility(self, action: Dict[str, Any], action_type: str) -> float:
        """Calculate reversibility score (0-1).
        
        Higher score = harder to reverse = higher risk.
        """
        # HOLD is most reversible
        if action_type == 'hold':
            return 0.0
        
        # READ operations are reversible
        if action_type in {'read', 'read_only_query'}:
            return 0.0
        
        # Market/limit orders are more reversible than instant market orders
        order_type = str(action.get('order_type', 'market')).lower()
        if order_type in {'limit', 'pending'}:
            return 0.8
        
        # UPDATE operations are somewhat reversible
        if action_type in {'update', 'single_record_update'}:
            return 0.5
        
        # TRADE operations - market orders
        if action_type in {'trade', 'buy', 'sell', 'medium_trade'}:
            return 0.3
        
        # REBALANCE affects multiple positions
        if action_type == 'rebalance':
            portfolio_size = len(action.get('portfolio', []))
            return min(0.2 + (portfolio_size * 0.1), 0.9)
        
        # DELETE and BULK operations are hard to reverse
        if action_type in {'delete', 'bulk_delete', 'high_impact_trade'}:
            return 0.9
        
        return 0.5
    
    def _calculate_data_scope(self, action: Dict[str, Any], action_type: str) -> float:
        """Calculate data scope score (0-1).
        
        Higher score = more data/records affected = higher risk.
        """
        # HOLD affects nothing
        if action_type == 'hold':
            return 0.1
        
        # READ operations have minimal scope
        if action_type in {'read', 'read_only_query'}:
            return 0.1
        
        # UPDATE single record
        if action_type in {'update', 'single_record_update'}:
            return 0.4
        
        # TRADE - based on quantity
        if action_type in {'trade', 'buy', 'sell', 'medium_trade'}:
            quantity = float(action.get('quantity', 0) or 0)
            # Normalize quantity - for crypto, use absolute; for stocks, divide by 1000
            if action.get('symbol', '').upper().endswith('-USD'):
                # Crypto: 0.01 BTC = small, 1 BTC = large
                return min(quantity / 10.0, 1.0)
            else:
                # Stocks: normalize by 1000 shares
                return min(quantity / 1000.0, 1.0)
        
        # REBALANCE - based on portfolio size
        if action_type == 'rebalance':
            portfolio = action.get('portfolio', [])
            return min(len(portfolio) / 10.0, 1.0)
        
        # DELETE single
        if action_type == 'delete':
            return 0.7
        
        # BULK operations affect many records
        if action_type == 'bulk_delete':
            return 1.0
        
        if action_type == 'high_impact_trade':
            return 0.8
        
        return 0.5
    
    def _calculate_regulatory(self, symbol: str) -> float:
        """Calculate regulatory category score (0-1).
        
        Higher score = more regulated = higher risk.
        """
        if not symbol:
            return 0.5
        
        return self.policy.get_regulatory_score(symbol)
    
    def _calculate_confidence(self, action: Dict[str, Any], market_snapshot: Optional[Dict[str, Any]], prediction: Optional[Dict[str, Any]]) -> float:
        """Calculate confidence score (0-1).
        
        Higher score = higher confidence = LOWER risk (will be inverted in assessment).
        """
        # Get confidence from multiple sources
        confidence_scores = []
        
        # From action itself
        if 'confidence' in action:
            conf = float(action['confidence'])
            if 0 <= conf <= 1:
                confidence_scores.append(conf)
        
        # From market snapshot
        if market_snapshot and 'confidence' in market_snapshot:
            conf = float(market_snapshot['confidence'])
            if 0 <= conf <= 1:
                confidence_scores.append(conf)
        
        # From prediction
        if prediction and 'confidence' in prediction:
            conf = float(prediction['confidence'])
            if 0 <= conf <= 1:
                confidence_scores.append(conf)
        
        # If no explicit confidence, use volatility-based estimate
        if not confidence_scores:
            if market_snapshot and 'volatility' in market_snapshot:
                volatility = float(market_snapshot['volatility'])
                # Higher volatility = lower confidence
                return max(0.2, min(0.95, 0.8 - min(volatility * 7, 0.6)))
            return 0.75  # Default confidence
        
        # Average all confidence scores
        return float(np.mean(confidence_scores))
    
    def route_action(
        self,
        risk_assessment: RiskAssessment,
        action: Dict[str, Any],
    ) -> Tuple[str, str, Optional[str]]:
        """Route action based on risk assessment.
        
        Returns:
            Tuple of (autonomy_level, message, next_step)
        """
        autonomy_level = risk_assessment.autonomy_level
        risk_score = risk_assessment.risk_score
        
        if autonomy_level == AutonomyLevel.AUTONOMOUS.value:
            return autonomy_level, "Execute immediately", "auto_execute"
        elif autonomy_level == AutonomyLevel.CONFIRMATION.value:
            return autonomy_level, "Queue for user confirmation", "confirmation_queue"
        else:
            return autonomy_level, "Escalate to human review queue", "review_queue"
    
    def evaluate_and_route(
        self,
        action: Dict[str, Any],
        market_snapshot: Optional[Dict[str, Any]] = None,
        prediction: Optional[Dict[str, Any]] = None,
        action_type: Optional[str] = None,
    ) -> Tuple[RiskAssessment, Tuple[str, str, Optional[str]]]:
        """Convenience method to assess and route in one call.
        
        Returns:
            Tuple of (risk_assessment, routing_result)
        """
        assessment = self.assess_risk(action, market_snapshot, prediction, action_type)
        routing = self.route_action(assessment, action)
        return assessment, routing
    
    def create_trade_proposal(
        self,
        symbol: str,
        action: str,
        quantity: float,
        price: float,
        confidence: float,
        strategy: str = "technical",
        entry_price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        reason: str = "",
        technical_signal: str = "",
        backtest_metrics: Optional[Dict[str, Any]] = None,
        position_size_pct: float = 0.0,
        risk_amount: float = 0.0,
        stop_distance: float = 0.0,
    ) -> TradeProposal:
        """Create a structured trade proposal."""
        import uuid
        return TradeProposal(
            decision_id=str(uuid.uuid4()),
            action=action,
            symbol=symbol,
            quantity=quantity,
            price=price,
            confidence=confidence,
            strategy=strategy,
            entry_price=entry_price or price,
            stop_loss=stop_loss or price * 0.98,  # Default 2% stop
            take_profit=take_profit,
            reason=reason,
            technical_signal=technical_signal,
            backtest_metrics=backtest_metrics,
            position_size_pct=position_size_pct,
            risk_amount=risk_amount,
            stop_distance=stop_distance,
        )
    
    def create_generic_action(
        self,
        action_type: str,
        resource: str,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Create a generic action for non-trading governance."""
        import uuid
        action = {
            'action_id': str(uuid.uuid4()),
            'type': action_type,
            'resource': resource,
            **kwargs
        }
        return action


# Singleton instance
GOVERNANCE_ENGINE = GovernanceEngine()


# Convenience functions
def assess_risk(
    action: Dict[str, Any],
    market_snapshot: Optional[Dict[str, Any]] = None,
    prediction: Optional[Dict[str, Any]] = None,
    action_type: Optional[str] = None,
) -> RiskAssessment:
    """Assess governance risk for an action."""
    return GOVERNANCE_ENGINE.assess_risk(action, market_snapshot, prediction, action_type)


def evaluate_and_route(
    action: Dict[str, Any],
    market_snapshot: Optional[Dict[str, Any]] = None,
    prediction: Optional[Dict[str, Any]] = None,
    action_type: Optional[str] = None,
) -> Tuple[RiskAssessment, Tuple[str, str, Optional[str]]]:
    """Assess and route an action."""
    return GOVERNANCE_ENGINE.evaluate_and_route(action, market_snapshot, prediction, action_type)


# Import numpy for confidence calculation
try:
    import numpy as np
except ImportError:
    import sys
    import math
    
    class MockNumpy:
        @staticmethod
        def mean(values):
            if not values:
                return 0.0
            return sum(values) / len(values)
    
    sys.modules['numpy'] = MockNumpy()
    np = MockNumpy()
