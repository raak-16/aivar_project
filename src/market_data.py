from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import pandas as pd
import requests

try:
    import yfinance as yf
except Exception:  # pragma: no cover
    yf = None


@dataclass
class MarketSnapshot:
    symbol: str
    price: float
    volatility: float
    previous_close: Optional[float]
    change_pct: float
    currency: str = "USD"
    source: str = "yfinance"
    confidence: float = 0.5


class MockMarketDataProvider:
    def __init__(self) -> None:
        self._data = {
            "AAPL": {"price": 150.0, "volatility": 0.016, "previous_close": 148.0, "change_pct": 1.35},
            "MSFT": {"price": 320.0, "volatility": 0.018, "previous_close": 318.0, "change_pct": 0.63},
            "GOOGL": {"price": 170.0, "volatility": 0.02, "previous_close": 168.0, "change_pct": 1.19},
            "TSLA": {"price": 220.0, "volatility": 0.05, "previous_close": 210.0, "change_pct": 4.76},
            "BTC": {"price": 54000.0, "volatility": 0.08, "previous_close": 52000.0, "change_pct": 3.85},
        }

    def fetch(self, symbol: str) -> MarketSnapshot:
        cleaned = symbol.upper()
        seed = self._data.get(cleaned, {"price": 100.0, "volatility": 0.03, "previous_close": 99.0, "change_pct": 1.0})
        price = float(seed["price"])
        previous_close = float(seed["previous_close"])
        volatility = float(seed["volatility"])
        change_pct = float(seed["change_pct"])
        confidence = max(0.2, min(0.95, 0.8 - min(volatility * 7, 0.6)))
        return MarketSnapshot(
            symbol=cleaned,
            price=price,
            volatility=volatility,
            previous_close=previous_close,
            change_pct=change_pct,
            source="mock",
            confidence=confidence,
        )


class MarketDataProvider:
    def __init__(self, fallback_provider: Optional[MockMarketDataProvider] = None) -> None:
        self._cache: Dict[str, MarketSnapshot] = {}
        self._cache_updated_at: Dict[str, float] = {}
        self._fallback_provider = fallback_provider or MockMarketDataProvider()
        # yfinance-only: no Binance websocket streams
        self._yf_cache: Dict[str, MarketSnapshot] = {}

    def _fetch_yfinance_snapshot(self, symbol: str) -> Optional[MarketSnapshot]:
        """Fetch market snapshot using yfinance only."""
        if yf is None:
            return None
        try:
            cleaned = symbol.upper().strip().replace("-", "")
            ticker = yf.Ticker(symbol)
            history = ticker.history(period="5d", interval="1d", auto_adjust=True)
            if history.empty:
                return None
            closes = history["Close"].dropna()
            if closes.empty:
                return None
            price = float(closes.iloc[-1])
            previous_close = float(closes.iloc[-2]) if len(closes) > 1 else price
            returns = closes.pct_change().dropna()
            volatility = float(returns.std(ddof=0)) if not returns.empty else 0.01
            change_pct = ((price - previous_close) / previous_close * 100) if previous_close else 0.0
            confidence = max(0.2, min(0.95, 0.75 - min(volatility * 10, 0.55)))
            return MarketSnapshot(
                symbol=symbol.upper().strip(),
                price=price,
                volatility=volatility,
                previous_close=previous_close,
                change_pct=change_pct,
                source="yfinance",
                confidence=confidence,
            )
        except Exception:
            return None

    def fetch(self, symbol: str) -> MarketSnapshot:
        cleaned = symbol.upper().strip()
        if not cleaned:
            raise ValueError("Symbol cannot be empty")

        # Check cache first (valid for 5 seconds)
        cached = self._cache.get(cleaned)
        if cached is not None and time.time() - self._cache_updated_at.get(cleaned, 0) < 5:
            return cached

        # Try yfinance first
        snapshot = self._fetch_yfinance_snapshot(cleaned)
        if snapshot is not None:
            self._cache[cleaned] = snapshot
            self._cache_updated_at[cleaned] = time.time()
            return snapshot

        # Fallback to mock data
        snapshot = self._fallback_provider.fetch(cleaned)
        self._cache[cleaned] = snapshot
        self._cache_updated_at[cleaned] = time.time()
        return snapshot

    def get(self, symbol: str) -> MarketSnapshot:
        return self.fetch(symbol)

    def history(self, symbol: str, limit: int = 72) -> Tuple[pd.DataFrame, str]:
        """Return chart-ready OHLCV data using yfinance only."""
        cleaned = symbol.upper().strip()
        
        # Try yfinance first
        if yf is not None:
            try:
                frame = yf.Ticker(cleaned).history(period="5d", interval="1h", auto_adjust=True).reset_index()
                if not frame.empty:
                    timestamp = "Datetime" if "Datetime" in frame.columns else "Date"
                    frame = frame.rename(columns={timestamp: "timestamp", "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"})
                    return frame[["timestamp", "open", "high", "low", "close", "volume"]].dropna().tail(limit), "yfinance"
            except Exception:
                pass

        # Fallback: generate mock history from snapshot
        snapshot = self.fetch(cleaned)
        index = pd.date_range(end=pd.Timestamp.now(tz="UTC"), periods=limit, freq="h")
        drift = pd.Series(range(limit), dtype=float).sub(limit - 1).mul(snapshot.change_pct / 100 / limit)
        close = snapshot.price * (1 + drift)
        frame = pd.DataFrame({"timestamp": index, "close": close})
        frame["open"] = frame["close"].shift(1).fillna(snapshot.previous_close or snapshot.price)
        frame["high"] = frame[["open", "close"]].max(axis=1) * 1.001
        frame["low"] = frame[["open", "close"]].min(axis=1) * 0.999
        frame["volume"] = 0.0
        return frame[["timestamp", "open", "high", "low", "close", "volume"]], "mock"
