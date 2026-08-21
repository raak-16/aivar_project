from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class StorageBackend(ABC):
    @abstractmethod
    def create_action(self, action: Dict[str, Any], risk_score: float, status: str) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def update_action_status(self, action_id: str, status: str) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_action(self, action_id: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def save_confirmation(self, action_id: str, risk_score: float, status: str = "PENDING") -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def save_review(self, action_id: str, risk_score: float, status: str = "OPEN", assigned_to: str = "human-review") -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def log_audit(self, action_id: str, risk_score: float, decision: str, breakdown: Dict[str, float]) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def list_actions(self) -> List[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def list_confirmations(self) -> List[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def list_reviews(self) -> List[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def list_audit_logs(self) -> List[Dict[str, Any]]:
        raise NotImplementedError
