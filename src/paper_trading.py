"""Local paper-trading execution driven by the Kronos forecast signal."""

from __future__ import annotations

from dataclasses import dataclass

from .predictor import ForecastSignal
from .storage.sqlite_storage import SQLiteStorage


INITIAL_CASH = 100.0


@dataclass(frozen=True)
class PaperTradeResult:
    action: str
    symbol: str
    quantity: float
    price: float
    cash: float
    message: str


class KronosPaperTrader:
    """Convert the latest Kronos signal into a local, fractional paper order."""

    def __init__(self, storage: SQLiteStorage) -> None:
        self.storage = storage

    def trade(self, symbol: str, price: float, signal: ForecastSignal, action: str | None = None, allocation: float = 0.25, sell_fraction: float = 0.5, rationale: str = "") -> PaperTradeResult:
        if price <= 0:
            raise ValueError("A positive market price is required for paper trading.")

        account = self.storage.get_paper_account(INITIAL_CASH)
        position = self.storage.get_paper_position(symbol)
        cash = float(account["cash"])
        held = float(position["quantity"]) if position else 0.0
        direction = signal.direction.lower()
        action = (action or ("BUY" if direction == "bullish" else "SELL" if direction == "bearish" else "HOLD")).upper()

        if action == "BUY" and cash >= 0.01:
            notional = round(cash * min(0.25, max(0.0, allocation)), 2)
            quantity = round(notional / price, 8)
            cash_after = round(cash - notional, 2)
            action, message = "BUY", f"Kronos is bullish; bought ${notional:.2f} of {symbol}."
        elif action == "SELL" and held > 0:
            quantity = round(held * min(1.0, max(0.0, sell_fraction)), 8)
            notional = round(quantity * price, 2)
            cash_after = round(cash + notional, 2)
            action, message = "SELL", f"Kronos is bearish; sold half of the {symbol} position."
        elif action == "SELL":
            quantity, notional, cash_after = 0.0, 0.0, cash
            action, message = "HOLD", f"Kronos is bearish, but there is no {symbol} position to sell."
        else:
            quantity, notional, cash_after = 0.0, 0.0, cash
            action, message = "HOLD", rationale or "The ensemble is neutral; no paper order was placed."

        self.storage.record_paper_trade(
            symbol=symbol, action=action, quantity=quantity, price=price, notional=notional,
            cash_after=cash_after, signal_direction=direction, signal_confidence=signal.confidence,
        )
        return PaperTradeResult(action, symbol, quantity, price, cash_after, message)
