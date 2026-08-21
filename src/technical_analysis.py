"""TA-Lib based technical analysis module.

Calculates technical indicators using TA-Lib library for strategy signals.
All indicators handle warm-up NaN values correctly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

try:
    import talib as ta
    TA_LIB_AVAILABLE = True
except ImportError:
    TA_LIB_AVAILABLE = False


@dataclass
class TechnicalIndicators:
    """Structured result for all calculated technical indicators."""
    symbol: str
    timestamp: Optional[str] = None
    
    # Price data
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[float] = None
    
    # Moving Averages
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    ema_20: Optional[float] = None
    ema_50: Optional[float] = None
    
    # Momentum
    rsi_14: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    
    # Trend Strength
    adx: Optional[float] = None
    plus_di: Optional[float] = None
    minus_di: Optional[float] = None
    
    # Volatility
    atr_14: Optional[float] = None
    
    # Bollinger Bands
    bb_upper: Optional[float] = None
    bb_middle: Optional[float] = None
    bb_lower: Optional[float] = None
    bb_width: Optional[float] = None
    bb_percent: Optional[float] = None
    
    # Volume
    volume_sma_20: Optional[float] = None
    
    # Rate of Change
    roc_1: Optional[float] = None
    roc_5: Optional[float] = None
    roc_10: Optional[float] = None


@dataclass
class TechnicalSignal:
    """Deterministic trading signal based on technical indicators."""
    signal: str  # BUY, SELL, HOLD
    score: float  # -10 to +10 scale
    confidence: float  # 0 to 1
    reasons: list


class TechnicalAnalysisEngine:
    """Engine for calculating technical indicators using TA-Lib."""
    
    def __init__(self, use_mock: bool = False):
        self.use_mock = use_mock or not TA_LIB_AVAILABLE
        
    def calculate_indicators(
        self,
        dataframe: pd.DataFrame,
        symbol: str = "UNKNOWN"
    ) -> TechnicalIndicators:
        """Calculate all technical indicators for a given OHLCV DataFrame.
        
        Args:
            dataframe: DataFrame with columns ['open', 'high', 'low', 'close', 'volume']
            symbol: Symbol identifier
            
        Returns:
            TechnicalIndicators with all calculated values
        """
        if dataframe.empty:
            return TechnicalIndicators(symbol=symbol)
        
        # Ensure we have the required columns
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in required_cols:
            if col not in dataframe.columns:
                return TechnicalIndicators(symbol=symbol)
        
        # Get the last row values
        last_idx = dataframe.index[-1]
        
        if self.use_mock:
            return self._calculate_mock_indicators(dataframe, symbol)
        
        return self._calculate_talib_indicators(dataframe, symbol)
    
    def _calculate_talib_indicators(
        self,
        dataframe: pd.DataFrame,
        symbol: str
    ) -> TechnicalIndicators:
        """Calculate indicators using actual TA-Lib."""
        df = dataframe.copy()
        
        # Extract arrays for TA-Lib
        open_prices = df['open'].values.astype(np.float64)
        high_prices = df['high'].values.astype(np.float64)
        low_prices = df['low'].values.astype(np.float64)
        close_prices = df['close'].values.astype(np.float64)
        volumes = df['volume'].values.astype(np.float64)
        
        indicators = TechnicalIndicators(
            symbol=symbol,
            timestamp=str(df.index[-1]) if hasattr(df.index[-1], 'isoformat') else str(df.index[-1]),
            open=float(open_prices[-1]),
            high=float(high_prices[-1]),
            low=float(low_prices[-1]),
            close=float(close_prices[-1]),
            volume=float(volumes[-1])
        )
        
        # Simple Moving Averages
        if len(close_prices) >= 20:
            sma_20 = ta.SMA(close_prices, timeperiod=20)
            indicators.sma_20 = float(sma_20[-1]) if not np.isnan(sma_20[-1]) else None
        if len(close_prices) >= 50:
            sma_50 = ta.SMA(close_prices, timeperiod=50)
            indicators.sma_50 = float(sma_50[-1]) if not np.isnan(sma_50[-1]) else None
        
        # Exponential Moving Averages
        if len(close_prices) >= 20:
            ema_20 = ta.EMA(close_prices, timeperiod=20)
            indicators.ema_20 = float(ema_20[-1]) if not np.isnan(ema_20[-1]) else None
        if len(close_prices) >= 50:
            ema_50 = ta.EMA(close_prices, timeperiod=50)
            indicators.ema_50 = float(ema_50[-1]) if not np.isnan(ema_50[-1]) else None
        
        # RSI
        if len(close_prices) >= 14:
            rsi = ta.RSI(close_prices, timeperiod=14)
            indicators.rsi_14 = float(rsi[-1]) if not np.isnan(rsi[-1]) else None
        
        # MACD (default: fast=12, slow=26, signal=9)
        if len(close_prices) >= 26:
            macd, macd_signal, macd_hist = ta.MACD(
                close_prices,
                fastperiod=12,
                slowperiod=26,
                signalperiod=9
            )
            indicators.macd = float(macd[-1]) if not np.isnan(macd[-1]) else None
            indicators.macd_signal = float(macd_signal[-1]) if not np.isnan(macd_signal[-1]) else None
            indicators.macd_histogram = float(macd_hist[-1]) if not np.isnan(macd_hist[-1]) else None
        
        # ADX
        if len(high_prices) >= 14 and len(low_prices) >= 14 and len(close_prices) >= 14:
            adx = ta.ADX(high_prices, low_prices, close_prices, timeperiod=14)
            plus_di = ta.PLUS_DI(high_prices, low_prices, close_prices, timeperiod=14)
            minus_di = ta.MINUS_DI(high_prices, low_prices, close_prices, timeperiod=14)
            indicators.adx = float(adx[-1]) if not np.isnan(adx[-1]) else None
            indicators.plus_di = float(plus_di[-1]) if not np.isnan(plus_di[-1]) else None
            indicators.minus_di = float(minus_di[-1]) if not np.isnan(minus_di[-1]) else None
        
        # ATR
        if len(high_prices) >= 14 and len(low_prices) >= 14 and len(close_prices) >= 14:
            atr = ta.ATR(high_prices, low_prices, close_prices, timeperiod=14)
            indicators.atr_14 = float(atr[-1]) if not np.isnan(atr[-1]) else None
        
        # Bollinger Bands
        if len(close_prices) >= 20:
            upper, middle, lower = ta.BBANDS(
                close_prices,
                timeperiod=20,
                nbdevup=2,
                nbdevdn=2,
                matype=0
            )
            indicators.bb_upper = float(upper[-1]) if not np.isnan(upper[-1]) else None
            indicators.bb_middle = float(middle[-1]) if not np.isnan(middle[-1]) else None
            indicators.bb_lower = float(lower[-1]) if not np.isnan(lower[-1]) else None
            
            current_close = float(close_prices[-1])
            if indicators.bb_upper and indicators.bb_lower and current_close > 0:
                indicators.bb_width = indicators.bb_upper - indicators.bb_lower
                indicators.bb_percent = (
                    (current_close - indicators.bb_lower) / 
                    (indicators.bb_upper - indicators.bb_lower) 
                    if (indicators.bb_upper - indicators.bb_lower) > 0 else None
                )
        
        # Volume SMA
        if len(volumes) >= 20:
            vol_sma = ta.SMA(volumes, timeperiod=20)
            indicators.volume_sma_20 = float(vol_sma[-1]) if not np.isnan(vol_sma[-1]) else None
        
        # Rate of Change
        if len(close_prices) >= 1:
            roc_1 = ta.ROC(close_prices, timeperiod=1)
            indicators.roc_1 = float(roc_1[-1]) if not np.isnan(roc_1[-1]) else None
        if len(close_prices) >= 5:
            roc_5 = ta.ROC(close_prices, timeperiod=5)
            indicators.roc_5 = float(roc_5[-1]) if not np.isnan(roc_5[-1]) else None
        if len(close_prices) >= 10:
            roc_10 = ta.ROC(close_prices, timeperiod=10)
            indicators.roc_10 = float(roc_10[-1]) if not np.isnan(roc_10[-1]) else None
        
        return indicators
    
    def _calculate_mock_indicators(
        self,
        dataframe: pd.DataFrame,
        symbol: str
    ) -> TechnicalIndicators:
        """Calculate mock indicators when TA-Lib is not available."""
        df = dataframe.copy()
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        open_p = df['open'].values
        volume = df['volume'].values
        
        n = len(close)
        
        def safe_sma(period):
            if n >= period:
                return float(np.mean(close[-period:]))
            return None
        
        def safe_ema(period):
            if n >= period:
                weights = np.exp(np.linspace(-1, 0, period))
                weights /= weights.sum()
                return float(np.sum(weights * close[-period:]))
            return None
        
        def safe_rsi(period=14):
            if n >= period + 1:
                deltas = np.diff(close[-period-1:])
                gains = np.maximum(deltas, 0)
                losses = np.abs(np.minimum(deltas, 0))
                avg_gain = np.mean(gains[-period:])
                avg_loss = np.mean(losses[-period:])
                if avg_loss > 0:
                    rs = avg_gain / avg_loss
                    return float(100 - (100 / (1 + rs)))
            return None
        
        def safe_macd():
            if n >= 26:
                ema_12 = safe_ema(12)
                ema_26 = safe_ema(26)
                if ema_12 is not None and ema_26 is not None:
                    macd = ema_12 - ema_26
                    # Simple signal line
                    macd_values = []
                    for i in range(-26, 0):
                        if i + 12 >= -26:
                            ema_12_v = safe_ema(12) if i == -1 else None
                        else:
                            ema_12_v = None
                    # Just use current macd and simple signal
                    signal = macd * 0.5  # Simple approximation
                    return macd, signal, macd - signal
            return None, None, None
        
        def safe_atr(period=14):
            if n >= period:
                tr = np.zeros(n)
                for i in range(1, n):
                    tr[i] = max(
                        high[i] - low[i],
                        abs(high[i] - close[i-1]),
                        abs(low[i] - close[i-1])
                    )
                return float(np.mean(tr[-period:]))
            return None
        
        def safe_bb(period=20):
            if n >= period:
                sma = safe_sma(period)
                if sma is not None:
                    std = float(np.std(close[-period:]))
                    return sma + 2 * std, sma, sma - 2 * std
            return None, None, None
        
        indicators = TechnicalIndicators(
            symbol=symbol,
            timestamp=str(df.index[-1]) if hasattr(df.index[-1], 'isoformat') else str(df.index[-1]),
            open=float(open_p[-1]),
            high=float(high[-1]),
            low=float(low[-1]),
            close=float(close[-1]),
            volume=float(volume[-1]),
            sma_20=safe_sma(20),
            sma_50=safe_sma(50),
            ema_20=safe_ema(20),
            ema_50=safe_ema(50),
            rsi_14=safe_rsi(14),
        )
        
        macd, signal, hist = safe_macd()
        indicators.macd = macd
        indicators.macd_signal = signal
        indicators.macd_histogram = hist
        
        indicators.atr_14 = safe_atr(14)
        
        upper, middle, lower = safe_bb(20)
        indicators.bb_upper = upper
        indicators.bb_middle = middle
        indicators.bb_lower = lower
        
        if upper and lower and middle:
            current_close = float(close[-1])
            indicators.bb_width = upper - lower
            indicators.bb_percent = (current_close - lower) / (upper - lower) if (upper - lower) > 0 else None
        
        if n >= 20:
            indicators.volume_sma_20 = float(np.mean(volume[-20:]))
        
        # Rate of Change
        if n >= 1:
            indicators.roc_1 = float((close[-1] - close[-2]) / close[-2] * 100) if n >= 2 else 0.0
        if n >= 5:
            indicators.roc_5 = float((close[-1] - close[-6]) / close[-6] * 100) if n >= 6 else 0.0
        if n >= 10:
            indicators.roc_10 = float((close[-1] - close[-11]) / close[-11] * 100) if n >= 11 else 0.0
        
        return indicators
    
    def generate_signal(
        self,
        indicators: TechnicalIndicators,
        weights: Optional[Dict[str, float]] = None
    ) -> TechnicalSignal:
        """Generate a deterministic trading signal from technical indicators.
        
        Args:
            indicators: Calculated technical indicators
            weights: Optional custom weights for signal components
            
        Returns:
            TechnicalSignal with BUY/SELL/HOLD decision
        """
        if not indicators.close:
            return TechnicalSignal(signal="HOLD", score=0.0, confidence=0.0, reasons=["No price data"])
        
        default_weights = {
            'rsi': 1.0,
            'macd': 1.0,
            'ema_trend': 1.0,
            'adx': 0.8,
            'bollinger': 0.8,
            'volume': 0.5,
            'roc': 0.7
        }
        
        if weights:
            default_weights.update(weights)
        
        score = 0.0
        reasons = []
        confidence_factors = []
        
        # RSI Signal
        if indicators.rsi_14 is not None:
            if indicators.rsi_14 < 30:
                score += default_weights['rsi'] * 2.0
                reasons.append(f"RSI oversold ({indicators.rsi_14:.1f})")
                confidence_factors.append(1.0 - indicators.rsi_14 / 100)
            elif indicators.rsi_14 > 70:
                score -= default_weights['rsi'] * 2.0
                reasons.append(f"RSI overbought ({indicators.rsi_14:.1f})")
                confidence_factors.append(indicators.rsi_14 / 100)
            else:
                # Neutral RSI
                confidence_factors.append(0.5)
        
        # MACD Signal
        if indicators.macd is not None and indicators.macd_signal is not None:
            if indicators.macd > indicators.macd_signal:
                score += default_weights['macd'] * 1.5
                reasons.append("MACD bullish crossover")
                confidence_factors.append(0.8)
            elif indicators.macd < indicators.macd_signal:
                score -= default_weights['macd'] * 1.5
                reasons.append("MACD bearish crossover")
                confidence_factors.append(0.8)
            else:
                confidence_factors.append(0.4)
        
        # EMA Trend
        if indicators.ema_20 is not None and indicators.ema_50 is not None:
            if indicators.ema_20 > indicators.ema_50:
                score += default_weights['ema_trend'] * 1.5
                reasons.append("EMA 20 above EMA 50 (bullish)")
                confidence_factors.append(0.75)
            elif indicators.ema_20 < indicators.ema_50:
                score -= default_weights['ema_trend'] * 1.5
                reasons.append("EMA 20 below EMA 50 (bearish)")
                confidence_factors.append(0.75)
            else:
                confidence_factors.append(0.3)
        
        # ADX Trend Strength
        if indicators.adx is not None:
            if indicators.adx > 25:
                # Strong trend
                if indicators.plus_di and indicators.minus_di:
                    if indicators.plus_di > indicators.minus_di:
                        score += default_weights['adx'] * 1.0
                        reasons.append(f"Strong uptrend (ADX={indicators.adx:.1f}, +DI>{indicators.plus_di:.1f})")
                    else:
                        score -= default_weights['adx'] * 1.0
                        reasons.append(f"Strong downtrend (ADX={indicators.adx:.1f}, -DI>{indicators.minus_di:.1f})")
                confidence_factors.append(min(1.0, indicators.adx / 40))
            else:
                reasons.append(f"Weak trend (ADX={indicators.adx:.1f})")
                confidence_factors.append(0.3)
        
        # Bollinger Bands
        if indicators.bb_percent is not None:
            if indicators.bb_percent < 0.2:
                score += default_weights['bollinger'] * 1.5
                reasons.append(f"Price near lower Bollinger Band ({indicators.bb_percent:.2f})")
                confidence_factors.append(1.0 - indicators.bb_percent)
            elif indicators.bb_percent > 0.8:
                score -= default_weights['bollinger'] * 1.5
                reasons.append(f"Price near upper Bollinger Band ({indicators.bb_percent:.2f})")
                confidence_factors.append(indicators.bb_percent)
            else:
                confidence_factors.append(0.5)
        
        # Volume confirmation
        if indicators.volume is not None and indicators.volume_sma_20 is not None:
            volume_ratio = indicators.volume / indicators.volume_sma_20 if indicators.volume_sma_20 > 0 else 1.0
            if volume_ratio > 1.5:
                # High volume confirms price move
                confidence_factors.append(0.9)
            else:
                confidence_factors.append(0.5)
        
        # ROC
        if indicators.roc_1 is not None:
            if indicators.roc_1 > 1:
                score += default_weights['roc'] * 0.5
                confidence_factors.append(min(0.9, abs(indicators.roc_1) / 10))
            elif indicators.roc_1 < -1:
                score -= default_weights['roc'] * 0.5
                confidence_factors.append(min(0.9, abs(indicators.roc_1) / 10))
        
        # Determine signal
        if score >= 1.5:
            signal = "BUY"
        elif score <= -1.5:
            signal = "SELL"
        else:
            signal = "HOLD"
        
        # Calculate confidence (0 to 1)
        avg_confidence = np.mean(confidence_factors) if confidence_factors else 0.5
        # Normalize score to 0-10 range and calculate final confidence
        normalized_score = max(0, min(10, abs(score) * 2))
        confidence = round(float(np.clip(avg_confidence * (0.5 + normalized_score / 20), 0, 1)), 4)
        
        if not reasons:
            reasons.append("No strong technical signals")
        
        return TechnicalSignal(
            signal=signal,
            score=round(float(score), 4),
            confidence=confidence,
            reasons=reasons
        )


# Singleton instance
TECHNICAL_ENGINE = TechnicalAnalysisEngine()


def calculate_indicators(
    dataframe: pd.DataFrame,
    symbol: str = "UNKNOWN"
) -> TechnicalIndicators:
    """Convenience function to calculate indicators."""
    return TECHNICAL_ENGINE.calculate_indicators(dataframe, symbol)


def generate_signal(
    indicators: TechnicalIndicators,
    weights: Optional[Dict[str, float]] = None
) -> TechnicalSignal:
    """Convenience function to generate signal from indicators."""
    return TECHNICAL_ENGINE.generate_signal(indicators, weights)
