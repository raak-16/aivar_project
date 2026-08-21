from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .autonomy_router import AutonomyDecision


@dataclass
class ExecutionResult:
    action_id: str
    action_type: str
    status: str
    decision: str
    risk_score: float
    message: str


class TradeExecutor:
    def __init__(self, storage=None, logger=None) -> None:
        self.storage = storage
        self.logger = logger

    def execute(self, action: Dict[str, Any], decision: AutonomyDecision, approved: Optional[bool] = None) -> ExecutionResult:
        action_type = str(action.get("type", "hold")).lower()
        risk_score = float(decision.risk_score)
        action_id = action.get("action_id") or "local-action"

        if decision.level == "autonomous":
            status = "EXECUTED"
            message = "Trade executed autonomously"
        elif decision.level == "confirm":
            if approved is None:
                status = "PENDING_CONFIRMATION"
                message = "Awaiting approval"
            elif approved:
                status = "CONFIRMED"
                message = "Trade approved and executed"
            else:
                status = "REJECTED"
                message = "Trade rejected by user"
        else:
            status = "QUEUED_FOR_REVIEW"
            message = "Trade escalated to human review"

        if self.storage is not None:
            self.storage.create_action(action, risk_score, status)

        if self.logger is not None:
            self.logger.log_decision(action_id, action, risk_score, decision.level, status)

        return ExecutionResult(
            action_id=str(action_id),
            action_type=action_type,
            status=status,
            decision=decision.level,
            risk_score=risk_score,
            message=message,
        )
