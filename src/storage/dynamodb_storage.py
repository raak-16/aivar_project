from __future__ import annotations

from typing import Any, Dict, List

from .base import StorageBackend

try:
    import boto3  # type: ignore
except Exception:  # pragma: no cover
    boto3 = None


class DynamoDBStorage(StorageBackend):
    """Optional AWS implementation. Local development does not require boto3."""

    def __init__(self, resource=None) -> None:
        self.resource = resource or (boto3.resource("dynamodb") if boto3 is not None else None)

    def create_action(self, action: Dict[str, Any], risk_score: float, status: str) -> Dict[str, Any]:
        if self.resource is None:
            raise RuntimeError("boto3 is required for DynamoDBStorage, but local mode should use SQLiteStorage.")
        return {"status": status, "risk_score": risk_score}

    def update_action_status(self, action_id: str, status: str) -> Dict[str, Any]:
        if self.resource is None:
            raise RuntimeError("boto3 is required for DynamoDBStorage, but local mode should use SQLiteStorage.")
        return {"action_id": action_id, "status": status}

    def get_action(self, action_id: str) -> Dict[str, Any] | None:
        if self.resource is None:
            raise RuntimeError("boto3 is required for DynamoDBStorage, but local mode should use SQLiteStorage.")
        return {"action_id": action_id}

    def save_confirmation(self, action_id: str, risk_score: float, status: str = "PENDING") -> Dict[str, Any]:
        if self.resource is None:
            raise RuntimeError("boto3 is required for DynamoDBStorage, but local mode should use SQLiteStorage.")
        return {"action_id": action_id, "risk_score": risk_score, "status": status}

    def save_review(self, action_id: str, risk_score: float, status: str = "OPEN", assigned_to: str = "human-review") -> Dict[str, Any]:
        if self.resource is None:
            raise RuntimeError("boto3 is required for DynamoDBStorage, but local mode should use SQLiteStorage.")
        return {"action_id": action_id, "risk_score": risk_score, "status": status, "assigned_to": assigned_to}

    def log_audit(self, action_id: str, risk_score: float, decision: str, breakdown: Dict[str, float]) -> Dict[str, Any]:
        if self.resource is None:
            raise RuntimeError("boto3 is required for DynamoDBStorage, but local mode should use SQLiteStorage.")
        return {"action_id": action_id, "risk_score": risk_score, "decision": decision, "breakdown": breakdown}

    def list_actions(self) -> List[Dict[str, Any]]:
        if self.resource is None:
            raise RuntimeError("boto3 is required for DynamoDBStorage, but local mode should use SQLiteStorage.")
        return []

    def list_confirmations(self) -> List[Dict[str, Any]]:
        if self.resource is None:
            raise RuntimeError("boto3 is required for DynamoDBStorage, but local mode should use SQLiteStorage.")
        return []

    def list_reviews(self) -> List[Dict[str, Any]]:
        if self.resource is None:
            raise RuntimeError("boto3 is required for DynamoDBStorage, but local mode should use SQLiteStorage.")
        return []

    def list_audit_logs(self) -> List[Dict[str, Any]]:
        if self.resource is None:
            raise RuntimeError("boto3 is required for DynamoDBStorage, but local mode should use SQLiteStorage.")
        return []
