"""Autonomy router for graduated autonomy decisions.

Routes actions based on risk score to:
- AUTONOMOUS: Execute immediately (risk < low_threshold)
- CONFIRMATION: Queue for user confirmation (low_threshold <= risk <= medium_threshold)
- REVIEW: Escalate to human review queue (risk > medium_threshold)

Thresholds are configurable via the governance policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .governance import GOVERNANCE_ENGINE


@dataclass
class AutonomyDecision:
    level: Literal["autonomous", "confirm", "review"]
    risk_score: float
    message: str
    risk_level: str = ""


class AutonomyRouter:
    """Routes actions to autonomy levels based on configurable thresholds.
    
    Default thresholds:
    - low_threshold: 0.3 (below this = autonomous)
    - medium_threshold: 0.7 (above this = review)
    
    These can be configured in the governance policy.
    """
    
    def __init__(self, low_threshold: float = 0.3, medium_threshold: float = 0.7):
        """Initialize with configurable thresholds.
        
        Args:
            low_threshold: Risk score below which actions are autonomous
            medium_threshold: Risk score above which actions require human review
        """
        self.low_threshold = low_threshold
        self.medium_threshold = medium_threshold
    
    @classmethod
    def from_policy(cls) -> "AutonomyRouter":
        """Create router from governance policy thresholds."""
        policy = GOVERNANCE_ENGINE.policy
        low = policy.autonomy_thresholds.get("low", 0.3)
        medium = policy.autonomy_thresholds.get("medium", 0.7)
        return cls(low_threshold=low, medium_threshold=medium)
    
    def route(self, risk_score: float) -> AutonomyDecision:
        """Route a risk score to an autonomy level.
        
        Args:
            risk_score: The governance risk score (0-1)
            
        Returns:
            AutonomyDecision with level, score, and message
        """
        score = max(0.0, min(1.0, float(risk_score)))
        
        if score < self.low_threshold:
            return AutonomyDecision(
                level="autonomous",
                risk_score=round(score, 4),
                message="Execute immediately",
                risk_level="low"
            )
        if score <= self.medium_threshold:
            return AutonomyDecision(
                level="confirm",
                risk_score=round(score, 4),
                message="Queue for user confirmation",
                risk_level="medium"
            )
        return AutonomyDecision(
            level="review",
            risk_score=round(score, 4),
            message="Escalate to human review queue",
            risk_level="high"
        )
    
    @staticmethod
    def route_static(risk_score: float) -> AutonomyDecision:
        """Static method for backward compatibility with default thresholds."""
        router = AutonomyRouter()
        return router.route(risk_score)


# Default instance
DEFAULT_ROUTER = AutonomyRouter()


# Convenience function
def route(risk_score: float) -> AutonomyDecision:
    """Route a risk score using the default router."""
    return DEFAULT_ROUTER.route(risk_score)
