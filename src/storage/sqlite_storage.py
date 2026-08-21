from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from .base import StorageBackend


class SQLiteStorage(StorageBackend):
    def __init__(self, db_path: str = "data/local.db") -> None:
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS actions (
                    action_id TEXT PRIMARY KEY,
                    action_type TEXT,
                    symbol TEXT,
                    quantity REAL,
                    price REAL,
                    status TEXT,
                    risk_score REAL,
                    created_at TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS confirmations (
                    confirmation_id TEXT PRIMARY KEY,
                    action_id TEXT,
                    risk_score REAL,
                    status TEXT,
                    created_at TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS reviews (
                    review_id TEXT PRIMARY KEY,
                    action_id TEXT,
                    risk_score REAL,
                    status TEXT,
                    assigned_to TEXT,
                    created_at TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_logs (
                    log_id TEXT PRIMARY KEY,
                    action_id TEXT,
                    timestamp TEXT,
                    risk_score REAL,
                    decision TEXT,
                    breakdown TEXT
                )
                """
            )
            connection.execute("CREATE TABLE IF NOT EXISTS paper_account (account_id INTEGER PRIMARY KEY CHECK (account_id = 1), cash REAL NOT NULL)")
            connection.execute("CREATE TABLE IF NOT EXISTS paper_positions (symbol TEXT PRIMARY KEY, quantity REAL NOT NULL, average_price REAL NOT NULL)")
            connection.execute("""CREATE TABLE IF NOT EXISTS paper_trades (
                trade_id TEXT PRIMARY KEY, symbol TEXT NOT NULL, action TEXT NOT NULL,
                quantity REAL NOT NULL, price REAL NOT NULL, notional REAL NOT NULL,
                cash_after REAL NOT NULL, signal_direction TEXT NOT NULL,
                signal_confidence REAL NOT NULL, created_at TEXT NOT NULL)""")
            connection.execute("CREATE TABLE IF NOT EXISTS settings (setting_key TEXT PRIMARY KEY, setting_value TEXT NOT NULL)")

    def create_action(self, action: Dict[str, Any], risk_score: float, status: str) -> Dict[str, Any]:
        action_id = str(action.get("action_id") or uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        payload = {
            "action_id": action_id,
            "action_type": str(action.get("type", "hold")).lower(),
            "symbol": str(action.get("symbol", "")),
            "quantity": float(action.get("quantity", 0) or 0),
            "price": float(action.get("price", 0) or 0),
            "status": status,
            "risk_score": float(risk_score),
            "created_at": created_at,
        }
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO actions (
                    action_id, action_type, symbol, quantity, price, status, risk_score, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["action_id"],
                    payload["action_type"],
                    payload["symbol"],
                    payload["quantity"],
                    payload["price"],
                    payload["status"],
                    payload["risk_score"],
                    payload["created_at"],
                ),
            )
        return payload

    def update_action_status(self, action_id: str, status: str) -> Dict[str, Any]:
        with self._connect() as connection:
            connection.execute("UPDATE actions SET status = ? WHERE action_id = ?", (status, action_id))
        row = self.get_action(action_id)
        return row or {"action_id": action_id, "status": status}

    def get_action(self, action_id: str) -> Dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM actions WHERE action_id = ?", (action_id,)).fetchone()
        return dict(row) if row is not None else None

    def save_confirmation(self, action_id: str, risk_score: float, status: str = "PENDING") -> Dict[str, Any]:
        record = {
            "confirmation_id": str(uuid.uuid4()),
            "action_id": action_id,
            "risk_score": float(risk_score),
            "status": status,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO confirmations (confirmation_id, action_id, risk_score, status, created_at) VALUES (?, ?, ?, ?, ?)",
                (
                    record["confirmation_id"],
                    record["action_id"],
                    record["risk_score"],
                    record["status"],
                    record["created_at"],
                ),
            )
        return record

    def save_review(self, action_id: str, risk_score: float, status: str = "OPEN", assigned_to: str = "human-review") -> Dict[str, Any]:
        record = {
            "review_id": str(uuid.uuid4()),
            "action_id": action_id,
            "risk_score": float(risk_score),
            "status": status,
            "assigned_to": assigned_to,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO reviews (review_id, action_id, risk_score, status, assigned_to, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    record["review_id"],
                    record["action_id"],
                    record["risk_score"],
                    record["status"],
                    record["assigned_to"],
                    record["created_at"],
                ),
            )
        return record

    def log_audit(self, action_id: str, risk_score: float, decision: str, breakdown: Dict[str, float]) -> Dict[str, Any]:
        record = {
            "log_id": str(uuid.uuid4()),
            "action_id": action_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "risk_score": float(risk_score),
            "decision": decision,
            "breakdown": json.dumps(breakdown, sort_keys=True),
        }
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO audit_logs (log_id, action_id, timestamp, risk_score, decision, breakdown) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    record["log_id"],
                    record["action_id"],
                    record["timestamp"],
                    record["risk_score"],
                    record["decision"],
                    record["breakdown"],
                ),
            )
        return record

    def list_actions(self) -> List[Dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM actions ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in rows]

    def list_confirmations(self) -> List[Dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM confirmations ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in rows]

    def list_reviews(self) -> List[Dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM reviews ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in rows]

    def list_audit_logs(self) -> List[Dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM audit_logs ORDER BY timestamp DESC").fetchall()
        return [dict(row) for row in rows]

    def get_paper_account(self, initial_cash: float = 100.0) -> Dict[str, Any]:
        with self._connect() as connection:
            connection.execute("INSERT OR IGNORE INTO paper_account (account_id, cash) VALUES (1, ?)", (float(initial_cash),))
            row = connection.execute("SELECT cash FROM paper_account WHERE account_id = 1").fetchone()
        return {"cash": float(row["cash"])}

    def get_paper_position(self, symbol: str) -> Dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM paper_positions WHERE symbol = ?", (symbol.upper(),)).fetchone()
        return dict(row) if row is not None else None

    def list_paper_positions(self) -> List[Dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM paper_positions WHERE quantity > 0 ORDER BY symbol").fetchall()
        return [dict(row) for row in rows]

    def list_paper_trades(self, limit: int = 8) -> List[Dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM paper_trades ORDER BY created_at DESC LIMIT ?", (int(limit),)).fetchall()
        return [dict(row) for row in rows]

    def record_paper_trade(self, *, symbol: str, action: str, quantity: float, price: float, notional: float, cash_after: float, signal_direction: str, signal_confidence: float) -> None:
        symbol, created_at = symbol.upper(), datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            current = connection.execute("SELECT quantity, average_price FROM paper_positions WHERE symbol = ?", (symbol,)).fetchone()
            held = float(current["quantity"]) if current else 0.0
            average_price = float(current["average_price"]) if current else 0.0
            if action == "BUY":
                new_quantity = held + quantity
                new_average = ((held * average_price) + (quantity * price)) / new_quantity
            elif action == "SELL":
                new_quantity, new_average = max(0.0, held - quantity), average_price
            else:
                new_quantity, new_average = held, average_price
            connection.execute("UPDATE paper_account SET cash = ? WHERE account_id = 1", (cash_after,))
            connection.execute("INSERT OR REPLACE INTO paper_positions (symbol, quantity, average_price) VALUES (?, ?, ?)", (symbol, new_quantity, new_average))
            connection.execute("""INSERT INTO paper_trades (trade_id, symbol, action, quantity, price, notional, cash_after, signal_direction, signal_confidence, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (str(uuid.uuid4()), symbol, action, quantity, price, notional, cash_after, signal_direction, float(signal_confidence), created_at))

    def get_setting(self, key: str, default: str = "") -> str:
        with self._connect() as connection:
            row = connection.execute("SELECT setting_value FROM settings WHERE setting_key = ?", (key,)).fetchone()
        return str(row["setting_value"]) if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self._connect() as connection:
            connection.execute("INSERT OR REPLACE INTO settings (setting_key, setting_value) VALUES (?, ?)", (key, value))
