from __future__ import annotations

from typing import Any, Dict


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Optional AWS Lambda wrapper for the autonomy router."""
    risk_score = float(event.get("risk_score", 0.0))
    if risk_score < 0.3:
        decision = "autonomous"
    elif risk_score <= 0.7:
        decision = "confirm"
    else:
        decision = "review"
    return {"statusCode": 200, "body": {"decision": decision, "risk_score": risk_score}}
