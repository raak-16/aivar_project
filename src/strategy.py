"""Selectable, local alpha strategies for the Kronos paper-trading simulator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import pandas as pd

from .predictor import ForecastSignal


@dataclass(frozen=True)
class TradeDecision:
    action: str
    allocation: float
    sell_fraction: float
    regime: str
    score: float
    rationale: str


@dataclass(frozen=True)
class Indicators:
    rsi: float
    macd_bullish: bool
    trend_gap: float
    atr_pct: float
    z_score: float
    regime: str
    price: float


class TradingStrategy(Protocol):
    key: str
    name: str
    description: str
    def decide(self, history: pd.DataFrame, signal: ForecastSignal, entry_price: float | None = None) -> TradeDecision: ...


def _indicators(history: pd.DataFrame) -> Indicators | None:
    frame = history.copy().dropna(subset=["close", "high", "low"])
    if len(frame) < 55:
        return None
    close, high, low = frame["close"].astype(float), frame["high"].astype(float), frame["low"].astype(float)
    ema_fast, ema_slow = close.ewm(span=20, adjust=False).mean(), close.ewm(span=50, adjust=False).mean()
    delta = close.diff()
    gain, loss = delta.clip(lower=0).rolling(14).mean(), -delta.clip(upper=0).rolling(14).mean()
    rs = gain / loss.replace(0, float("nan"))
    rsi = float((100 - (100 / (1 + rs))).iloc[-1])
    if pd.isna(rsi):
        rsi = 100.0 if float(gain.iloc[-1] or 0) > 0 else 50.0
    macd = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
    macd_signal = macd.ewm(span=9, adjust=False).mean()
    previous = close.shift(1)
    true_range = pd.concat([high - low, (high - previous).abs(), (low - previous).abs()], axis=1).max(axis=1)
    atr_pct = float(true_range.rolling(14).mean().iloc[-1] / close.iloc[-1])
    mean, std = close.rolling(20).mean().iloc[-1], close.rolling(20).std().iloc[-1]
    z_score = float((close.iloc[-1] - mean) / std) if std and not pd.isna(std) else 0.0
    trend_gap = float((ema_fast.iloc[-1] - ema_slow.iloc[-1]) / close.iloc[-1])
    regime = "high-volatility" if atr_pct > 0.05 else "trending" if abs(trend_gap) > 0.003 else "ranging"
    return Indicators(rsi, bool(macd.iloc[-1] > macd_signal.iloc[-1]), trend_gap, atr_pct, z_score, regime, float(close.iloc[-1]))


def _hold(regime: str, reason: str, score: float = 0.0) -> TradeDecision:
    return TradeDecision("HOLD", 0.0, 0.0, regime, round(score, 2), reason)


class TrendFollowingStrategy:
    key = "trend_following"
    name = "Trend Following"
    description = "EMA 20/50 crossover plus MACD confirmation. Designed for persistent trends."

    def decide(self, history: pd.DataFrame, signal: ForecastSignal, entry_price: float | None = None) -> TradeDecision:
        data = _indicators(history)
        if not data:
            return _hold("insufficient-data", "Need 55 completed candles before trading.")
        if data.regime == "high-volatility" or signal.confidence < 0.5:
            return _hold(data.regime, "Risk guard: high volatility or low Kronos confidence.")
        if entry_price and data.price <= entry_price * 0.92:
            return TradeDecision("SELL", 0.0, 1.0, data.regime, -3.0, "Hard 8% stop-loss triggered.")
        score = (1 if data.trend_gap > 0 else -1) + (0.5 if data.macd_bullish else -0.5) + (1 if signal.direction == "bullish" else -1 if signal.direction == "bearish" else 0)
        if score >= 1.5:
            return TradeDecision("BUY", min(0.25, max(0.10, 0.01 / max(data.atr_pct, 0.005))), 0.0, data.regime, score, "Uptrend confirmed by EMA, MACD, and Kronos.")
        if score <= -1.5:
            return TradeDecision("SELL", 0.0, 0.5, data.regime, score, "Downtrend confirmed by EMA, MACD, and Kronos.")
        return _hold(data.regime, "Trend signals do not agree.", score)


class MeanReversionStrategy:
    key = "mean_reversion"
    name = "Mean Reversion"
    description = "Buys statistically oversold prices using 20-bar z-score and RSI; only in ranging markets."

    def decide(self, history: pd.DataFrame, signal: ForecastSignal, entry_price: float | None = None) -> TradeDecision:
        data = _indicators(history)
        if not data:
            return _hold("insufficient-data", "Need 55 completed candles before trading.")
        if data.regime != "ranging" or signal.confidence < 0.5:
            return _hold(data.regime, "Mean reversion is enabled only in a low-volatility ranging regime.")
        if entry_price and data.price <= entry_price * 0.92:
            return TradeDecision("SELL", 0.0, 1.0, data.regime, -3.0, "Hard 8% stop-loss triggered.")
        if data.z_score <= -1.5 and data.rsi < 35:
            return TradeDecision("BUY", 0.15, 0.0, data.regime, data.z_score, f"Oversold: z-score {data.z_score:.2f}, RSI {data.rsi:.0f}.")
        if data.z_score >= 0.75 or data.rsi > 65:
            return TradeDecision("SELL", 0.0, 1.0, data.regime, data.z_score, f"Price reverted toward its mean: z-score {data.z_score:.2f}.")
        return _hold(data.regime, "No statistically significant mean-reversion entry.", data.z_score)


class KronosEnsembleStrategy(TrendFollowingStrategy):
    key = "kronos_ensemble"
    name = "Kronos Ensemble"
    description = "Combines Kronos direction with EMA trend, MACD, ATR, confidence, and stop-loss risk filters."


class AdaptiveStrategy:
    key = "adaptive"
    name = "Adaptive Regime Router"
    description = "Uses trend following in trends, mean reversion in ranges, and holds during high volatility."

    def __init__(self) -> None:
        self.trend, self.mean = TrendFollowingStrategy(), MeanReversionStrategy()

    def decide(self, history: pd.DataFrame, signal: ForecastSignal, entry_price: float | None = None) -> TradeDecision:
        data = _indicators(history)
        if not data:
            return _hold("insufficient-data", "Need 55 completed candles before trading.")
        if data.regime == "trending":
            return self.trend.decide(history, signal, entry_price)
        if data.regime == "ranging":
            return self.mean.decide(history, signal, entry_price)
        return _hold(data.regime, "Adaptive router paused trading during high volatility.")


STRATEGIES: dict[str, type[TradingStrategy]] = {
    KronosEnsembleStrategy.key: KronosEnsembleStrategy,
    TrendFollowingStrategy.key: TrendFollowingStrategy,
    MeanReversionStrategy.key: MeanReversionStrategy,
    AdaptiveStrategy.key: AdaptiveStrategy,
}


def get_strategy(key: str | None) -> TradingStrategy:
    return STRATEGIES.get(key or "", AdaptiveStrategy)()
