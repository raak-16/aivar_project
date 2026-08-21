from __future__ import annotations

from typing import Any, Dict, Optional


class ConfirmationHandler:
    def __init__(self, storage=None) -> None:
        self.storage = storage

    def prompt(self, action: Dict[str, Any], risk_score: float) -> bool:
        print(f"Action: {action.get('type', 'hold').upper()} {action.get('symbol', '')} qty={action.get('quantity', 0)} price={action.get('price', 0)}")
        print(f"Risk score: {risk_score:.3f} -> Prompting for user confirmation")
        response = input("Approve? (y/n): ").strip().lower()
        approved = response in {"y", "yes"}
        if self.storage is not None:
            self.storage.save_confirmation(str(action.get("action_id", "local-action")), risk_score, "APPROVED" if approved else "REJECTED")
        return approved

    def webhook(self, action: Dict[str, Any], risk_score: float, approved: bool) -> Dict[str, Any]:
        confirmation = {
            "action_id": str(action.get("action_id", "local-action")),
            "risk_score": risk_score,
            "status": "APPROVED" if approved else "REJECTED",
        }
        if self.storage is not None:
            self.storage.save_confirmation(confirmation["action_id"], risk_score, confirmation["status"])
        return confirmation
