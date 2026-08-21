"""Audit logger for graduated autonomy engine.

Every action is recorded with all PS-9.1 fields for human-readable auditability.

Required fields from PS-9.1:
- decision_id
- timestamp
- action
- symbol/resource
- quantity if applicable
- agent
- confidence
- reversibility
- data scope
- regulatory category
- risk score
- risk level
- autonomy level
- policy version
- execution status
- confirmation/review ID
- user/reviewer
- final outcome
- reason
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from .governance import GovernanceDecision, RiskAssessment


class AuditLogger:
    """Logs all governance decisions with PS-9.1 compliance."""
    
    def __init__(self, log_path: str = "audit.log") -> None:
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_decision(
        self,
        action_id: str,
        action: Dict[str, Any],
        risk_score: float,
        decision: str,
        status: str,
        decision_id: Optional[str] = None,
        timestamp: Optional[str] = None,
        symbol: Optional[str] = None,
        quantity: Optional[float] = None,
        agent: Optional[str] = None,
        confidence: Optional[float] = None,
        reversibility: Optional[float] = None,
        data_scope: Optional[float] = None,
        regulatory_category: Optional[float] = None,
        risk_level: Optional[str] = None,
        autonomy_level: Optional[str] = None,
        policy_version: Optional[str] = None,
        execution_status: Optional[str] = None,
        confirmation_id: Optional[str] = None,
        review_id: Optional[str] = None,
        user_reviewer: Optional[str] = None,
        final_outcome: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> None:
        """Log a decision with all PS-9.1 fields.
        
        This is the main logging method that captures all required audit information.
        """
        timestamp = timestamp or datetime.now(timezone.utc).isoformat()
        
        payload = {
            "timestamp": timestamp,
            "decision_id": decision_id or action_id,
            "action_id": action_id,
            "action": action,
            "action_type": action.get("type") or action.get("action", "unknown"),
            "symbol": symbol or action.get("symbol") or "",
            "resource": symbol or action.get("symbol") or action.get("resource") or "",
            "quantity": quantity or action.get("quantity"),
            "agent": agent or action.get("agent") or "TradingAgents",
            "confidence": confidence or action.get("confidence"),
            "reversibility": reversibility,
            "data_scope": data_scope,
            "regulatory_category": regulatory_category,
            "risk_score": risk_score,
            "risk_level": risk_level or self._infer_risk_level(risk_score),
            "autonomy_level": autonomy_level or decision,
            "policy_version": policy_version or "graduated-autonomy-v1",
            "execution_status": execution_status or status,
            "confirmation_id": confirmation_id,
            "review_id": review_id,
            "user_reviewer": user_reviewer,
            "final_outcome": final_outcome or status,
            "reason": reason or action.get("reason") or "",
        }
        
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True, default=str) + "\n")

    def _infer_risk_level(self, risk_score: float) -> str:
        """Infer risk level from score."""
        if risk_score < 0.3:
            return "low"
        elif risk_score <= 0.7:
            return "medium"
        return "high"

    def log_risk_breakdown(
        self,
        action_id: str,
        action: Dict[str, Any],
        risk_score: float,
        breakdown: Dict[str, float],
        final_decision: str,
        policy_version: str = "graduated-autonomy-v1",
    ) -> None:
        """Log a risk breakdown for detailed analysis."""
        timestamp = datetime.now(timezone.utc).isoformat()
        payload = {
            "timestamp": timestamp,
            "action_id": action_id,
            "action": action,
            "risk_score": risk_score,
            "breakdown": breakdown,
            "final_decision": final_decision,
            "policy_version": policy_version,
        }
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True, default=str) + "\n")

    def log_governance_decision(self, decision: GovernanceDecision) -> None:
        """Log a complete governance decision with all fields."""
        self.log_decision(
            action_id=decision.action_id,
            action=decision.action,
            risk_score=decision.risk_score,
            decision=decision.autonomy_level,
            status=decision.status,
            decision_id=decision.decision_id,
            timestamp=decision.timestamp,
            symbol=decision.symbol,
            quantity=decision.quantity,
            agent=decision.agent,
            confidence=decision.confidence,
            reversibility=decision.reversibility,
            data_scope=decision.data_scope,
            regulatory_category=decision.regulatory_category,
            risk_level=decision.risk_level,
            autonomy_level=decision.autonomy_level,
            policy_version=decision.policy_version,
            execution_status=decision.execution_status,
            confirmation_id=decision.confirmation_id,
            review_id=decision.review_id,
            user_reviewer=decision.user_reviewer,
            final_outcome=decision.final_outcome,
            reason=decision.reason,
        )

    def log_risk_assessment(self, assessment: RiskAssessment) -> None:
        """Log a risk assessment with all PS-9.1 dimensions."""
        action = assessment.metadata.get("action", {})
        self.log_decision(
            action_id=assessment.action_id,
            action=action,
            risk_score=assessment.risk_score,
            decision=assessment.autonomy_level,
            status="assessed",
            symbol=assessment.symbol,
            agent="governance_engine",
            confidence=assessment.confidence,
            reversibility=assessment.reversibility,
            data_scope=assessment.data_scope,
            regulatory_category=assessment.regulatory,
            risk_level=assessment.risk_level,
            autonomy_level=assessment.autonomy_level,
            policy_version=assessment.policy_version,
            execution_status="pending",
            reason=f"Risk assessment: {assessment.risk_score:.4f} -> {assessment.autonomy_level}",
        )

    def log_action_execution(
        self,
        action_id: str,
        action: Dict[str, Any],
        risk_assessment: RiskAssessment,
        autonomy_level: str,
        status: str,
        user: Optional[str] = None,
    ) -> None:
        """Log an action execution with all relevant fields."""
        self.log_decision(
            action_id=action_id,
            action=action,
            risk_score=risk_assessment.risk_score,
            decision=autonomy_level,
            status=status,
            decision_id=action_id,
            symbol=risk_assessment.symbol,
            quantity=action.get("quantity"),
            agent=action.get("agent", "TradingAgents"),
            confidence=risk_assessment.confidence,
            reversibility=risk_assessment.reversibility,
            data_scope=risk_assessment.data_scope,
            regulatory_category=risk_assessment.regulatory,
            risk_level=risk_assessment.risk_level,
            autonomy_level=autonomy_level,
            policy_version=risk_assessment.policy_version,
            execution_status=status,
            user_reviewer=user,
            final_outcome=status,
            reason=f"Action executed: {action.get('type', 'unknown')} {action.get('symbol', '')}",
        )
