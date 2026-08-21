"""VectorBT-based backtesting engine.

Evaluates strategy performance with realistic transaction costs and slippage.
Avoids look-ahead bias.
The exact same strategy logic is used for both backtesting and live decisions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple, TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    import vectorbt as vbt


@dataclass
class BacktestMetrics:
    """Performance metrics from a backtest."""
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    num_trades: int
    profit_factor: Optional[float] = None
    avg_trade_return: Optional[float] = None
    avg_win: Optional[float] = None
    avg_loss: Optional[float] = None
    best_trade: Optional[float] = None
    worst_trade: Optional[float] = None
    
    # Additional metadata
    strategy: str = ""
    symbol: str = ""
    period: str = ""
    transaction_costs: float = 0.0
    slippage: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            'total_return': round(self.total_return, 6),
            'sharpe_ratio': round(self.sharpe_ratio, 4) if self.sharpe_ratio else None,
            'max_drawdown': round(self.max_drawdown, 6),
            'win_rate': round(self.win_rate, 4),
            'num_trades': self.num_trades,
            'profit_factor': round(self.profit_factor, 4) if self.profit_factor else None,
            'avg_trade_return': round(self.avg_trade_return, 6) if self.avg_trade_return else None,
            'avg_win': round(self.avg_win, 6) if self.avg_win else None,
            'avg_loss': round(self.avg_loss, 6) if self.avg_loss else None,
            'best_trade': round(self.best_trade, 6) if self.best_trade else None,
            'worst_trade': round(self.worst_trade, 6) if self.worst_trade else None,
            'strategy': self.strategy,
            'symbol': self.symbol,
            'period': self.period,
            'transaction_costs': self.transaction_costs,
            'slippage': self.slippage,
        }


@dataclass
class BacktestResult:
    """Complete backtest result with metrics and trade log."""
    metrics: BacktestMetrics
    trades: List[Dict[str, Any]]
    portfolio_value: List[float]
    timestamps: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            'metrics': self.metrics.to_dict(),
            'trades': self.trades,
            'portfolio_value': [round(v, 2) for v in self.portfolio_value],
            'timestamps': self.timestamps,
        }


class Backtester:
    """VectorBT-based backtesting engine.
    
    Evaluates strategies with realistic transaction costs and slippage.
    Uses the exact same strategy logic for backtesting and live decisions.
    """
    
    VECTORBT_AVAILABLE = True
    
    def __init__(
        self,
        transaction_costs: float = 0.001,  # 0.1% per trade
        slippage: float = 0.0005,  # 0.05% slippage
        initial_cash: float = 10000.0,
        fee_method: str = "percent",
    ):
        """Initialize backtester.
        
        Args:
            transaction_costs: Transaction cost as decimal (0.001 = 0.1%)
            slippage: Slippage as decimal (0.0005 = 0.05%)
            initial_cash: Starting cash
            fee_method: How to apply fees ("percent", "fixed")
        """
        self.transaction_costs = transaction_costs
        self.slippage = slippage
        self.initial_cash = initial_cash
        self.fee_method = fee_method
        
        # Try to import VectorBT
        try:
            import vectorbt as vbt
            self.vbt = vbt
        except ImportError:
            self.VECTORBT_AVAILABLE = False
            self.vbt = None
    
    def backtest(
        self,
        strategy_func: Callable[[pd.DataFrame], pd.Series],
        history: pd.DataFrame,
        symbol: str = "UNKNOWN",
        strategy_name: str = "custom",
        lookback: Optional[int] = None,
    ) -> BacktestResult:
        """Run a backtest on historical data.
        
        Args:
            strategy_func: Function that takes OHLCV DataFrame and returns Series of signals (-1, 0, 1)
            history: Historical OHLCV DataFrame
            symbol: Symbol identifier
            strategy_name: Name of the strategy
            lookback: Number of periods to use for signal calculation (avoids look-ahead)
            
        Returns:
            BacktestResult with metrics and trade log
        """
        if not self.VECTORBT_AVAILABLE:
            return self._backtest_mock(strategy_func, history, symbol, strategy_name)
        
        # Ensure we have the required columns
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in required_cols:
            if col not in history.columns:
                return self._backtest_mock(strategy_func, history, symbol, strategy_name)
        
        # Prepare data - ensure proper index
        data = history.copy()
        data.index = pd.to_datetime(data.index)
        
        # Apply lookback to avoid look-ahead bias
        if lookback and len(data) > lookback:
            signals = self._calculate_signals_with_lookback(data, strategy_func, lookback)
        else:
            signals = strategy_func(data)
        
        # Run VectorBT backtest
        try:
            portfolio = self.vbt.Portfolio.from_signals(
                data['close'],
                signals,
                fees=self.transaction_costs,
                slippage=self.slippage,
                freq='1D',
                init_cash=self.initial_cash,
            )
            
            # Extract metrics
            metrics = self._extract_metrics(portfolio, strategy_name, symbol)
            
            # Extract trades
            trades = self._extract_trades(portfolio)
            
            # Extract portfolio value
            portfolio_value = portfolio.value().tolist()
            timestamps = [str(ts) for ts in portfolio.value().index]
            
            return BacktestResult(
                metrics=metrics,
                trades=trades,
                portfolio_value=portfolio_value,
                timestamps=timestamps
            )
            
        except Exception as e:
            print(f"VectorBT backtest failed: {e}")
            return self._backtest_mock(strategy_func, history, symbol, strategy_name)
    
    def _calculate_signals_with_lookback(
        self,
        data: pd.DataFrame,
        strategy_func: Callable[[pd.DataFrame], pd.Series],
        lookback: int
    ) -> pd.Series:
        """Calculate signals with lookback to avoid look-ahead bias."""
        signals = pd.Series(np.nan, index=data.index)
        
        for i in range(lookback, len(data)):
            window = data.iloc[i-lookback:i]
            window_signals = strategy_func(window)
            signals.iloc[i] = window_signals.iloc[-1]
        
        return signals
    
    def _extract_metrics(
        self,
        portfolio: "vbt.Portfolio",
        strategy_name: str,
        symbol: str
    ) -> BacktestMetrics:
        """Extract performance metrics from VectorBT portfolio."""
        stats = portfolio.stats()
        
        total_return = float(stats.get('Return [%]') or 0) / 100
        sharpe_ratio = float(stats.get('Sharpe Ratio') or 0)
        max_drawdown = float(stats.get('Max Drawdown [%]') or 0) / 100
        win_rate = float(stats.get('Win Rate [%]') or 0) / 100
        num_trades = int(stats.get('Total Trades') or 0)
        
        # Calculate additional metrics
        profit_factor = float(stats.get('Profit Factor') or 0)
        avg_trade_return = float(stats.get('Avg Trade Return [%]') or 0) / 100
        
        # Get trade returns for additional stats
        trades = portfolio.trades()
        if trades is not None and 'Returns' in trades.columns:
            trade_returns = trades['Returns'].dropna()
            winning_trades = trade_returns[trade_returns > 0]
            losing_trades = trade_returns[trade_returns < 0]
            
            avg_win = float(winning_trades.mean()) if len(winning_trades) > 0 else 0
            avg_loss = float(losing_trades.mean()) if len(losing_trades) > 0 else 0
            best_trade = float(trade_returns.max()) if len(trade_returns) > 0 else 0
            worst_trade = float(trade_returns.min()) if len(trade_returns) > 0 else 0
        else:
            avg_win = avg_loss = best_trade = worst_trade = 0.0
        
        return BacktestMetrics(
            total_return=total_return,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            num_trades=num_trades,
            profit_factor=profit_factor,
            avg_trade_return=avg_trade_return,
            avg_win=avg_win,
            avg_loss=avg_loss,
            best_trade=best_trade,
            worst_trade=worst_trade,
            strategy=strategy_name,
            symbol=symbol,
            period=f"{portfolio.index[0]} to {portfolio.index[-1]}" if len(portfolio.index) > 0 else "",
            transaction_costs=self.transaction_costs,
            slippage=self.slippage,
        )
    
    def _extract_trades(self, portfolio: "vbt.Portfolio") -> List[Dict[str, Any]]:
        """Extract trade information from portfolio."""
        trades = portfolio.trades()
        if trades is None or len(trades) == 0:
            return []
        
        trade_list = []
        for _, row in trades.iterrows():
            trade_list.append({
                'entry_time': str(row.get('Entry Time', '')),
                'exit_time': str(row.get('Exit Time', '')),
                'entry_price': float(row.get('Entry Price', 0)),
                'exit_price': float(row.get('Exit Price', 0)),
                'quantity': float(row.get('Size', 0)),
                'return': float(row.get('Return [%]', 0)),
                'return_abs': float(row.get('Return', 0)),
                'direction': str(row.get('Direction', '')),
                'fees': float(row.get('Fees', 0)),
            })
        return trade_list
    
    def _backtest_mock(
        self,
        strategy_func: Callable[[pd.DataFrame], pd.Series],
        history: pd.DataFrame,
        symbol: str,
        strategy_name: str
    ) -> BacktestResult:
        """Mock backtest when VectorBT is not available."""
        if history.empty:
            return BacktestResult(
                metrics=BacktestMetrics(
                    total_return=0.0,
                    sharpe_ratio=0.0,
                    max_drawdown=0.0,
                    win_rate=0.0,
                    num_trades=0,
                    strategy=strategy_name,
                    symbol=symbol,
                    transaction_costs=self.transaction_costs,
                    slippage=self.slippage,
                ),
                trades=[],
                portfolio_value=[self.initial_cash],
                timestamps=[datetime.now(timezone.utc).isoformat()]
            )
        
        # Generate signals
        try:
            signals = strategy_func(history)
        except Exception:
            signals = pd.Series(0, index=history.index)
        
        # Simulate simple backtest
        initial_price = float(history['close'].iloc[0])
        prices = history['close'].values
        
        cash = self.initial_cash
        position = 0.0
        portfolio_values = [cash]
        
        trades = []
        trade_count = 0
        winning_trades = 0
        
        for i in range(1, len(signals)):
            signal = signals.iloc[i]
            price = float(prices[i])
            
            # Apply transaction costs
            effective_price = price * (1 + self.transaction_costs + self.slippage)
            
            if signal > 0 and cash > 0:  # BUY
                # Buy with 25% of cash
                notional = cash * 0.25
                quantity = notional / effective_price
                position += quantity
                cash -= notional
                trade_count += 1
                trades.append({
                    'entry_time': str(history.index[i]),
                    'exit_time': '',
                    'entry_price': price,
                    'exit_price': 0,
                    'quantity': quantity,
                    'return': 0,
                    'return_abs': 0,
                    'direction': 'long',
                    'fees': notional * self.transaction_costs
                })
            elif signal < 0 and position > 0:  # SELL
                notional = position * price
                cash += notional * (1 - self.transaction_costs - self.slippage)
                winning_trades += 1 if notional > (position * initial_price) else 0
                position = 0.0
                trade_count += 1
                if len(trades) > 0:
                    trades[-1]['exit_time'] = str(history.index[i])
                    trades[-1]['exit_price'] = price
                    trades[-1]['return'] = ((price - trades[-1]['entry_price']) / trades[-1]['entry_price']) * 100
                    trades[-1]['return_abs'] = notional - (trades[-1]['quantity'] * trades[-1]['entry_price'])
            
            portfolio_value = cash + (position * price)
            portfolio_values.append(portfolio_value)
        
        final_value = portfolio_values[-1]
        total_return = (final_value - self.initial_cash) / self.initial_cash
        win_rate = winning_trades / trade_count if trade_count > 0 else 0
        
        # Calculate max drawdown
        peak = max(portfolio_values)
        drawdowns = [(peak - v) / peak for v in portfolio_values]
        max_drawdown = max(drawdowns) if drawdowns else 0
        
        metrics = BacktestMetrics(
            total_return=total_return,
            sharpe_ratio=0.0,  # Can't calculate without returns
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            num_trades=trade_count,
            strategy=strategy_name,
            symbol=symbol,
            transaction_costs=self.transaction_costs,
            slippage=self.slippage,
        )
        
        return BacktestResult(
            metrics=metrics,
            trades=trades,
            portfolio_value=portfolio_values,
            timestamps=[str(ts) for ts in history.index]
        )


class SimpleStrategyGenerator:
    """Generates simple strategy signals for testing."""
    
    @staticmethod
    def rsi_strategy(history: pd.DataFrame, rsi_period: int = 14, oversold: float = 30, overbought: float = 70) -> pd.Series:
        """Generate RSI-based signals."""
        close = history['close']
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        signals = pd.Series(0, index=history.index)
        signals[rsi < oversold] = 1  # BUY
        signals[rsi > overbought] = -1  # SELL
        return signals
    
    @staticmethod
    def sma_crossover(history: pd.DataFrame, fast: int = 20, slow: int = 50) -> pd.Series:
        """Generate SMA crossover signals."""
        close = history['close']
        sma_fast = close.rolling(window=fast).mean()
        sma_slow = close.rolling(window=slow).mean()
        
        signals = pd.Series(0, index=history.index)
        signals[sma_fast > sma_slow] = 1  # BUY
        signals[sma_fast < sma_slow] = -1  # SELL
        return signals
    
    @staticmethod
    def ema_crossover(history: pd.DataFrame, fast: int = 20, slow: int = 50) -> pd.Series:
        """Generate EMA crossover signals."""
        close = history['close']
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()
        
        signals = pd.Series(0, index=history.index)
        signals[ema_fast > ema_slow] = 1  # BUY
        signals[ema_fast < ema_slow] = -1  # SELL
        return signals
    
    @staticmethod
    def combined_strategy(history: pd.DataFrame) -> pd.Series:
        """Generate combined multi-indicator signals."""
        rsi_signals = SimpleStrategyGenerator.rsi_strategy(history)
        sma_signals = SimpleStrategyGenerator.sma_crossover(history)
        
        # Combine signals
        signals = pd.Series(0, index=history.index)
        signals[(rsi_signals == 1) & (sma_signals == 1)] = 1  # BUY when both agree
        signals[(rsi_signals == -1) & (sma_signals == -1)] = -1  # SELL when both agree
        return signals


# Singleton instances
BACKTESTER = Backtester()
SIMPLE_STRATEGIES = SimpleStrategyGenerator()


def backtest_strategy(
    strategy_func: Callable[[pd.DataFrame], pd.Series],
    history: pd.DataFrame,
    symbol: str = "UNKNOWN",
    strategy_name: str = "custom"
) -> BacktestResult:
    """Run a backtest on a strategy function."""
    return BACKTESTER.backtest(strategy_func, history, symbol, strategy_name)


def run_simple_backtest(
    history: pd.DataFrame,
    symbol: str = "UNKNOWN",
    strategy_type: str = "combined"
) -> BacktestResult:
    """Run a simple backtest with built-in strategies."""
    if strategy_type == "rsi":
        strategy_func = SimpleStrategyGenerator.rsi_strategy
    elif strategy_type == "sma":
        strategy_func = SimpleStrategyGenerator.sma_crossover
    elif strategy_type == "ema":
        strategy_func = SimpleStrategyGenerator.ema_crossover
    else:
        strategy_func = SimpleStrategyGenerator.combined_strategy
    
    return backtest_strategy(strategy_func, history, symbol, strategy_type)
