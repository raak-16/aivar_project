"""Strategy engine with deterministic technical signal generation.

This engine generates BUY/SELL/HOLD signals using TA-Lib technical indicators.
The exact same strategy logic is used for both backtesting and live decisions.
No look-ahead bias is introduced.

The LLM does NOT invent technical rules - only deterministic signals are used.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from .technical_analysis import TechnicalIndicators, TechnicalSignal, calculate_indicators, generate_signal, TECHNICAL_ENGINE


@dataclass
class StrategySignal:
    """Deterministic trading signal with confidence."""
    signal: str  # BUY, SELL, HOLD
    score: float  # -10 to +10 scale
    confidence: float  # 0 to 1
    strategy: str
    reasons: List[str]
    indicators: Optional[TechnicalIndicators] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'signal': self.signal,
            'score': self.score,
            'confidence': self.confidence,
            'strategy': self.strategy,
            'reasons': self.reasons,
        }


@dataclass
class StrategyConfig:
    """Configuration for a trading strategy."""
    name: str
    description: str
    signal_weights: Dict[str, float] = field(default_factory=dict)
    
    # Strategy parameters
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0
    rsi_buy_threshold: float = 40.0
    rsi_sell_threshold: float = 60.0
    
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    
    ema_fast: int = 20
    ema_slow: int = 50
    
    adx_strong_trend: float = 25.0
    adx_very_strong_trend: float = 50.0
    
    bb_period: int = 20
    bb_std_dev: float = 2.0
    
    volume_confirmation_ratio: float = 1.5
    
    stop_loss_pct: float = 0.02
    take_profit_pct: float = 0.04
    
    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> "StrategyConfig":
        """Create config from dictionary."""
        return cls(
            name=config.get('name', 'technical'),
            description=config.get('description', 'Multi-indicator technical strategy'),
            signal_weights=config.get('signal_weights', {}),
            rsi_oversold=config.get('rsi_oversold', 30.0),
            rsi_overbought=config.get('rsi_overbought', 70.0),
            rsi_buy_threshold=config.get('rsi_buy_threshold', 40.0),
            rsi_sell_threshold=config.get('rsi_sell_threshold', 60.0),
            macd_fast=config.get('macd_fast', 12),
            macd_slow=config.get('macd_slow', 26),
            macd_signal=config.get('macd_signal', 9),
            ema_fast=config.get('ema_fast', 20),
            ema_slow=config.get('ema_slow', 50),
            adx_strong_trend=config.get('adx_strong_trend', 25.0),
            adx_very_strong_trend=config.get('adx_very_strong_trend', 50.0),
            bb_period=config.get('bb_period', 20),
            bb_std_dev=config.get('bb_std_dev', 2.0),
            volume_confirmation_ratio=config.get('volume_confirmation_ratio', 1.5),
            stop_loss_pct=config.get('stop_loss_pct', 0.02),
            take_profit_pct=config.get('take_profit_pct', 0.04),
        )


class StrategyEngine:
    """Engine for generating deterministic technical signals.
    
    Uses TA-Lib indicators to generate BUY/SELL/HOLD signals.
    The exact same strategy logic is used for backtesting and live decisions.
    """
    
    # Built-in strategy configurations
    STRATEGIES: Dict[str, StrategyConfig] = {}
    
    def __init__(self, config: Optional[StrategyConfig] = None):
        self.config = config or self._default_config()
    
    @classmethod
    def _default_config(cls) -> StrategyConfig:
        """Create default strategy configuration."""
        return StrategyConfig(
            name="multi_indicator",
            description="Multi-indicator technical strategy using RSI, MACD, EMA, ADX, and Bollinger Bands",
            signal_weights={
                'rsi': 1.5,
                'macd': 1.5,
                'ema_trend': 1.5,
                'adx': 1.0,
                'bollinger': 1.0,
                'volume': 0.5,
            }
        )
    
    @classmethod
    def register_strategy(cls, name: str, config: StrategyConfig) -> None:
        """Register a named strategy."""
        cls.STRATEGIES[name] = config
    
    @classmethod
    def get_strategy(cls, name: str) -> "StrategyEngine":
        """Get a named strategy engine."""
        if name in cls.STRATEGIES:
            return cls(cls.STRATEGIES[name])
        return cls(cls._default_config())
    
    def generate_signal(
        self,
        history: pd.DataFrame,
        symbol: str = "UNKNOWN"
    ) -> StrategySignal:
        """Generate a deterministic trading signal from OHLCV history.
        
        Args:
            history: DataFrame with OHLCV data
            symbol: Symbol identifier
            
        Returns:
            StrategySignal with BUY/SELL/HOLD and confidence
        """
        if history.empty or len(history) < 50:
            return StrategySignal(
                signal="HOLD",
                score=0.0,
                confidence=0.0,
                strategy=self.config.name,
                reasons=["Insufficient history data"]
            )
        
        # Calculate indicators
        indicators = TECHNICAL_ENGINE.calculate_indicators(history, symbol)
        
        # Generate technical signal
        technical_signal = TECHNICAL_ENGINE.generate_signal(indicators, self.config.signal_weights)
        
        return StrategySignal(
            signal=technical_signal.signal,
            score=technical_signal.score,
            confidence=technical_signal.confidence,
            strategy=self.config.name,
            reasons=technical_signal.reasons,
            indicators=indicators
        )
    
    def generate_signal_from_indicators(
        self,
        indicators: TechnicalIndicators
    ) -> StrategySignal:
        """Generate signal directly from pre-calculated indicators."""
        technical_signal = TECHNICAL_ENGINE.generate_signal(indicators, self.config.signal_weights)
        return StrategySignal(
            signal=technical_signal.signal,
            score=technical_signal.score,
            confidence=technical_signal.confidence,
            strategy=self.config.name,
            reasons=technical_signal.reasons,
            indicators=indicators
        )


# Register built-in strategies
StrategyEngine.register_strategy(
    "trend_following",
    StrategyConfig(
        name="trend_following",
        description="Trend following strategy using EMA crossover and MACD confirmation",
        signal_weights={'rsi': 0.5, 'macd': 2.0, 'ema_trend': 2.0, 'adx': 1.5, 'bollinger': 0.5}
    )
)

StrategyEngine.register_strategy(
    "mean_reversion",
    StrategyConfig(
        name="mean_reversion",
        description="Mean reversion strategy using RSI and Bollinger Bands",
        signal_weights={'rsi': 2.0, 'macd': 0.5, 'ema_trend': 0.5, 'adx': 0.5, 'bollinger': 2.0}
    )
)

StrategyEngine.register_strategy(
    "breakout",
    StrategyConfig(
        name="breakout",
        description="Breakout strategy using ADX and volume confirmation",
        signal_weights={'rsi': 1.0, 'macd': 1.5, 'ema_trend': 1.0, 'adx': 2.0, 'bollinger': 1.0, 'volume': 1.5}
    )
)

# Singleton instance
STRATEGY_ENGINE = StrategyEngine()


def get_strategy_engine(name: str = "multi_indicator") -> StrategyEngine:
    """Get a named strategy engine."""
    return StrategyEngine.get_strategy(name)


def generate_strategy_signal(
    history: pd.DataFrame,
    symbol: str = "UNKNOWN",
    strategy: str = "multi_indicator"
) -> StrategySignal:
    """Generate a strategy signal for given history."""
    engine = get_strategy_engine(strategy)
    return engine.generate_signal(history, symbol)
