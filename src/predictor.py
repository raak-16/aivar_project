from __future__ import annotations

import os
import sys
import threading
import time
import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

import pandas as pd

try:
    import yfinance as yf
except Exception:  # pragma: no cover
    yf = None

from .market_data import MarketDataProvider, MarketSnapshot


@dataclass
class ForecastSignal:
    symbol: str
    direction: str
    expected_return: float
    confidence: float
    summary: str


class MarketPredictor:
    """Cached forecasting facade.

    Kronos is deliberately loaded once per process and forecasts are retained
    briefly. Quotes can therefore update every few seconds without making a
    model download/inference request for every websocket tick.
    """

    _kronos_predictor: Any = None
    _kronos_error: Optional[str] = None
    _kronos_loading = False
    _kronos_lock = threading.Lock()

    def __init__(self, market_provider: Optional[MarketDataProvider] = None, forecast_ttl: int = 300) -> None:
        self.market_provider = market_provider or MarketDataProvider()
        self.forecast_ttl = forecast_ttl
        self._forecast_cache: Dict[str, tuple[float, ForecastSignal]] = {}
        self._forecast_lock = threading.Lock()

    @classmethod
    def _load_kronos_predictor(cls):
        if cls._kronos_predictor is not None:
            return cls._kronos_predictor

        kronos_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, "kronos"))
        if not os.path.isdir(kronos_root):
            return None

        with cls._kronos_lock:
            if cls._kronos_predictor is not None:
                return cls._kronos_predictor
            try:
                if kronos_root not in sys.path:
                    sys.path.insert(0, kronos_root)
                from huggingface_hub import hf_hub_download
                from safetensors.torch import load_model
                from model import Kronos, KronosTokenizer, KronosPredictor as KronosPredictorClass

                # The installed Hugging Face mixin version does not pass the
                # repository config into Kronos' required constructor. Load the
                # official config + safetensors explicitly instead.
                def load_component(component_class: Any, repository: str) -> Any:
                    config_path = hf_hub_download(repository, "config.json")
                    weights_path = hf_hub_download(repository, "model.safetensors")
                    with open(config_path, encoding="utf-8") as config_file:
                        component = component_class(**json.load(config_file))
                    load_model(component, weights_path)
                    return component

                tokenizer = load_component(KronosTokenizer, "NeoQuasar/Kronos-Tokenizer-base")
                model = load_component(Kronos, "NeoQuasar/Kronos-mini")
                cls._kronos_predictor = KronosPredictorClass(model, tokenizer, max_context=512)
                cls._kronos_error = None
                return cls._kronos_predictor
            except Exception as exc:  # pragma: no cover
                cls._kronos_error = str(exc)
                cls._kronos_predictor = False
                return None

    @classmethod
    def kronos_status(cls) -> str:
        if cls._kronos_predictor and cls._kronos_predictor is not False:
            return "ready"
        if cls._kronos_loading:
            return "loading"
        if cls._kronos_error:
            return "unavailable"
        return "warming"

    @classmethod
    def warm_kronos(cls) -> None:
        """Load the model outside the request/update path."""
        import os
        # Skip if Kronos is disabled via environment variable
        if os.environ.get("DISABLE_KRONOS", "false").lower() == "true":
            return
        with cls._kronos_lock:
            if cls._kronos_loading or cls._kronos_predictor is not None:
                return
            cls._kronos_loading = True

        def load() -> None:
            try:
                cls._load_kronos_predictor()
            finally:
                cls._kronos_loading = False

        threading.Thread(target=load, name="kronos-warmup", daemon=True).start()

    def _fallback_signal(self, symbol: str, snapshot: MarketSnapshot) -> ForecastSignal:
        change_pct = float(snapshot.change_pct)
        volatility = float(snapshot.volatility)
        if change_pct > 0.5 and volatility < 0.05:
            direction = "bullish"
        elif change_pct < -0.5 and volatility < 0.05:
            direction = "bearish"
        else:
            direction = "neutral"

        confidence = max(0.15, min(0.95, 0.5 + (abs(change_pct) / 10.0) - (volatility * 4.0)))
        if direction == "neutral":
            confidence = min(confidence, 0.6)

        summary = (
            f"{direction.capitalize()} outlook for {snapshot.symbol}: "
            f"{change_pct:.2f}% move with volatility {volatility:.4f}."
        )
        return ForecastSignal(
            symbol=snapshot.symbol,
            direction=direction,
            expected_return=round(change_pct / 100.0, 4),
            confidence=round(confidence, 4),
            summary=summary,
        )

    def _kronos_signal(self, symbol: str, snapshot: MarketSnapshot) -> Optional[ForecastSignal]:
        predictor = self.__class__._kronos_predictor
        if not predictor or yf is None:
            return None

        try:
            history = yf.Ticker(symbol).history(period="90d", interval="1d", auto_adjust=True)
            if history.empty or len(history) < 10:
                return None
            history = history.copy()
            history = history[history["Close"].notna()].copy()
            history["volume"] = history.get("Volume", 0).fillna(0)
            history["amount"] = history.get("Volume", 0).fillna(0)
            history = history[["Open", "High", "Low", "Close", "volume", "amount"]].rename(
                columns={
                    "Open": "open",
                    "High": "high",
                    "Low": "low",
                    "Close": "close",
                }
            )
            history = history.dropna()
            if history.empty:
                return None

            x_timestamp = pd.Series(pd.DatetimeIndex(history.index), index=history.index)
            future_dates = pd.Series(pd.date_range(start=history.index[-1], periods=5, freq="1D"))
            prediction_df = predictor.predict(
                df=history,
                x_timestamp=x_timestamp,
                y_timestamp=future_dates,
                pred_len=5,
                sample_count=1,
                verbose=False,
            )
            if prediction_df.empty:
                return None
            predicted_close = float(prediction_df["close"].iloc[-1])
            last_close = float(history["close"].iloc[-1])
            expected_return = (predicted_close - last_close) / last_close
            direction = "bullish" if expected_return > 0.01 else "bearish" if expected_return < -0.01 else "neutral"
            confidence = min(0.95, max(0.5, abs(expected_return) * 10 + 0.4))
            summary = (
                f"Kronos forecast for {symbol}: {direction.capitalize()} direction with "
                f"expected return {expected_return:.4f} and model confidence {confidence:.3f}."
            )
            return ForecastSignal(
                symbol=symbol.upper(),
                direction=direction,
                expected_return=round(float(expected_return), 6),
                confidence=round(float(confidence), 4),
                summary=summary,
            )
        except Exception:
            return None

    def forecast(self, symbol: str) -> ForecastSignal:
        snapshot = self.market_provider.fetch(symbol)
        cache_key = snapshot.symbol
        with self._forecast_lock:
            cached = self._forecast_cache.get(cache_key)
            if cached and time.monotonic() - cached[0] < self.forecast_ttl:
                # Replace a temporary heuristic result as soon as the real
                # Kronos model becomes ready; do not wait for the full TTL.
                if not (
                    self.__class__.kronos_status() == "ready"
                    and not cached[1].summary.startswith("Kronos forecast")
                ):
                    return cached[1]
        kronos_signal = self._kronos_signal(symbol, snapshot)
        signal = kronos_signal or self._fallback_signal(symbol, snapshot)
        with self._forecast_lock:
            self._forecast_cache[cache_key] = (time.monotonic(), signal)
        return signal

    def enrich_market_snapshot(self, symbol: str) -> Dict[str, Any]:
        snapshot = self.market_provider.fetch(symbol)
        signal = self.forecast(symbol)
        return {
            "symbol": snapshot.symbol,
            "price": snapshot.price,
            "volatility": snapshot.volatility,
            "previous_close": snapshot.previous_close,
            "change_pct": snapshot.change_pct,
            "source": snapshot.source,
            "confidence": signal.confidence,
            "forecast_direction": signal.direction,
            "expected_return": signal.expected_return,
            "summary": signal.summary,
        }

    def chart_forecast(self, history: pd.DataFrame, steps: int = 5) -> tuple[pd.DataFrame, str]:
        """Forecast the supplied OHLCV series and identify the prediction backend."""
        history = history.copy().dropna(subset=["timestamp", "open", "high", "low", "close"])
        if history.empty:
            return pd.DataFrame(), "unavailable"
        history["timestamp"] = pd.to_datetime(history["timestamp"], utc=True)
        frame = history[["open", "high", "low", "close", "volume"]].copy()
        frame["amount"] = frame["volume"] * frame[["open", "high", "low", "close"]].mean(axis=1)
        future = pd.date_range(start=history["timestamp"].iloc[-1] + pd.Timedelta(hours=1), periods=steps, freq="h")
        predictor = self.__class__._kronos_predictor
        if predictor:
            try:
                predicted = predictor.predict(
                    df=frame[["open", "high", "low", "close", "volume", "amount"]],
                    x_timestamp=history["timestamp"], y_timestamp=pd.Series(future), pred_len=steps,
                    sample_count=1, verbose=False,
                ).reset_index(names="timestamp")
                return predicted, "kronos"
            except Exception:
                pass

        # Clearly marked fallback until the model finishes loading or is unavailable.
        last_close = float(frame["close"].iloc[-1])
        trend = float(frame["close"].pct_change().tail(12).mean() or 0.0)
        closes = [last_close * (1 + trend) ** (point + 1) for point in range(steps)]
        return pd.DataFrame({"timestamp": future, "close": closes}), "heuristic"
