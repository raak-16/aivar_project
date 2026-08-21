"""Deterministic risk-based position sizing.

Calculates position size based on portfolio equity, volatility, and risk limits.
The LLM has NO control over quantity - only deterministic risk-based sizing is used.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class PositionSizingConfig:
    """Configuration for position sizing with hard limits."""
    # Risk limits (cannot be overridden by LLM)
    max_risk_per_trade: float = 0.02  # 2% of portfolio
    max_position_size: float = 0.25  # 25% of portfolio in single position
    max_portfolio_exposure: float = 0.80  # 80% total exposure
    max_daily_loss: float = 0.05  # 5% daily loss limit
    
    # Stop loss settings
    default_stop_distance_pct: float = 0.02  # 2% stop loss
    min_stop_distance_pct: float = 0.01  # Minimum 1% stop
    
    # Volatility scaling
    volatility_multiplier: float = 1.0
    
    # Position size limits
    min_position_size: float = 0.01  # Minimum 1% of portfolio
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "PositionSizingConfig":
        """Create config from dictionary with defaults."""
        return cls(
            max_risk_per_trade=float(config_dict.get('max_risk_per_trade', 0.02)),
            max_position_size=float(config_dict.get('max_position_size', 0.25)),
            max_portfolio_exposure=float(config_dict.get('max_portfolio_exposure', 0.80)),
            max_daily_loss=float(config_dict.get('max_daily_loss', 0.05)),
            default_stop_distance_pct=float(config_dict.get('default_stop_distance_pct', 0.02)),
            min_stop_distance_pct=float(config_dict.get('min_stop_distance_pct', 0.01)),
            volatility_multiplier=float(config_dict.get('volatility_multiplier', 1.0)),
            min_position_size=float(config_dict.get('min_position_size', 0.01)),
        )


@dataclass
class PositionSizeResult:
    """Result of position sizing calculation."""
    symbol: str
    action: str  # BUY, SELL, HOLD
    price: float
    quantity: float
    notional: float
    position_size_pct: float  # Percentage of portfolio
    risk_amount: float
    stop_loss_price: float
    stop_distance: float
    stop_distance_pct: float
    leverage: float
    limits_hit: list = field(default_factory=list)
    rationale: str = ""


class PositionSizer:
    """Deterministic position sizer with hard risk limits.
    
    The autonomous agent determines HOW MUCH to buy/sell, but the LLM has
    NO unrestricted control over quantity. All limits are enforced.
    """
    
    def __init__(self, config: Optional[PositionSizingConfig] = None):
        self.config = config or PositionSizingConfig()
    
    def size_position(
        self,
        symbol: str,
        action: str,
        price: float,
        portfolio_equity: float,
        current_cash: float,
        current_position: Optional[Dict[str, Any]] = None,
        atr: Optional[float] = None,
        volatility: Optional[float] = None,
        confidence: Optional[float] = None,
        stop_distance_pct: Optional[float] = None,
    ) -> PositionSizeResult:
        """Calculate position size with hard risk limits.
        
        Args:
            symbol: Trading symbol
            action: BUY, SELL, or HOLD
            price: Current market price
            portfolio_equity: Total portfolio equity (cash + holdings value)
            current_cash: Available cash
            current_position: Current position dict with 'quantity' and 'average_price'
            atr: Average True Range (14-period)
            volatility: Price volatility (standard deviation or similar)
            confidence: Agent confidence score (0-1)
            stop_distance_pct: Custom stop loss distance percentage
            
        Returns:
            PositionSizeResult with calculated size
        """
        action = action.upper()
        
        if action == "HOLD":
            return PositionSizeResult(
                symbol=symbol,
                action=action,
                price=price,
                quantity=0.0,
                notional=0.0,
                position_size_pct=0.0,
                risk_amount=0.0,
                stop_loss_price=price,
                stop_distance=0.0,
                stop_distance_pct=0.0,
                leverage=0.0,
                rationale="Hold action - no position change"
            )
        
        if action == "SELL":
            # For SELL, we sell the existing position
            if current_position:
                quantity = float(current_position.get('quantity', 0))
                notional = quantity * price
                return PositionSizeResult(
                    symbol=symbol,
                    action=action,
                    price=price,
                    quantity=quantity,
                    notional=notional,
                    position_size_pct=0.0,  # Selling reduces position
                    risk_amount=0.0,
                    stop_loss_price=0.0,
                    stop_distance=0.0,
                    stop_distance_pct=0.0,
                    leverage=0.0,
                    rationale=f"Sell all {quantity} {symbol} at ${price:.2f}"
                )
            else:
                return PositionSizeResult(
                    symbol=symbol,
                    action=action,
                    price=price,
                    quantity=0.0,
                    notional=0.0,
                    position_size_pct=0.0,
                    risk_amount=0.0,
                    stop_loss_price=price,
                    stop_distance=0.0,
                    stop_distance_pct=0.0,
                    leverage=0.0,
                    rationale="No position to sell"
                )
        
        # For BUY actions
        if portfolio_equity <= 0 or price <= 0:
            return PositionSizeResult(
                symbol=symbol,
                action=action,
                price=price,
                quantity=0.0,
                notional=0.0,
                position_size_pct=0.0,
                risk_amount=0.0,
                stop_loss_price=price,
                stop_distance=0.0,
                stop_distance_pct=0.0,
                leverage=0.0,
                rationale="Invalid portfolio equity or price"
            )
        
        # Determine stop loss distance
        stop_pct = stop_distance_pct or self.config.default_stop_distance_pct
        stop_pct = max(stop_pct, self.config.min_stop_distance_pct)
        stop_distance = price * stop_pct
        stop_loss_price = price - stop_distance
        
        # Adjust stop distance based on volatility
        if atr is not None and atr > 0:
            # Higher volatility -> wider stop
            vol_adjustment = min(3.0, max(0.5, atr / (price * 0.01)))  # Normalize ATR to %
            adjusted_stop_pct = stop_pct * vol_adjustment * self.config.volatility_multiplier
            stop_distance = price * adjusted_stop_pct
            stop_loss_price = price - stop_distance
        
        # Calculate risk amount (2% of portfolio max)
        risk_amount = portfolio_equity * self.config.max_risk_per_trade
        
        # Position size based on risk
        # position_size = risk_amount / stop_distance
        position_size = risk_amount / stop_distance if stop_distance > 0 else 0
        
        # Calculate notional and quantity
        notional = position_size * price
        quantity = position_size  # For forex/crypto, quantity is the amount
        
        # Apply hard limits
        limits_hit = []
        
        # Limit 1: Max position size as % of portfolio
        max_position_notional = portfolio_equity * self.config.max_position_size
        if notional > max_position_notional:
            notional = max_position_notional
            quantity = notional / price
            position_size = quantity
            limits_hit.append(f"max_position_size ({self.config.max_position_size * 100}%)")
        
        # Limit 2: Available cash
        if notional > current_cash:
            notional = current_cash
            quantity = notional / price
            position_size = quantity
            limits_hit.append("available_cash")
        
        # Limit 3: Min position size
        min_notional = portfolio_equity * self.config.min_position_size
        if notional < min_notional and notional > 0:
            # Skip if below minimum
            return PositionSizeResult(
                symbol=symbol,
                action=action,
                price=price,
                quantity=0.0,
                notional=0.0,
                position_size_pct=0.0,
                risk_amount=0.0,
                stop_loss_price=stop_loss_price,
                stop_distance=stop_distance,
                stop_distance_pct=stop_pct,
                leverage=0.0,
                rationale=f"Position too small (${notional:.2f} < ${min_notional:.2f})"
            )
        
        # Calculate actual position size percentage
        position_size_pct = (notional / portfolio_equity) * 100 if portfolio_equity > 0 else 0
        
        # Calculate leverage (for margin trading, but we're doing paper trading)
        leverage = 1.0  # No leverage in paper trading
        
        # Build rationale
        rationale_parts = [
            f"Risk: ${risk_amount:.2f} ({self.config.max_risk_per_trade * 100}% of ${portfolio_equity:.2f})",
            f"Stop: ${stop_distance:.4f} ({stop_pct * 100:.2f}%)",
            f"Position: ${notional:.2f} ({position_size_pct:.2f}% of portfolio)",
        ]
        
        if limits_hit:
            rationale_parts.append(f"Limits hit: {', '.join(limits_hit)}")
        
        return PositionSizeResult(
            symbol=symbol,
            action=action,
            price=price,
            quantity=round(quantity, 8),
            notional=round(notional, 2),
            position_size_pct=round(position_size_pct, 4),
            risk_amount=round(risk_amount, 2),
            stop_loss_price=round(stop_loss_price, 4),
            stop_distance=round(stop_distance, 4),
            stop_distance_pct=round(stop_pct, 6),
            leverage=round(leverage, 2),
            limits_hit=limits_hit,
            rationale=" | ".join(rationale_parts)
        )
    
    def calculate_max_trade_size(
        self,
        portfolio_equity: float,
        price: float,
        risk_per_trade: float,
        stop_pct: float = 0.02
    ) -> float:
        """Quick calculation of max trade quantity.
        
        Args:
            portfolio_equity: Total portfolio value
            price: Asset price
            risk_per_trade: Risk percentage (0.01 = 1%)
            stop_pct: Stop loss percentage
            
        Returns:
            Maximum quantity that can be traded
        """
        if portfolio_equity <= 0 or price <= 0 or stop_pct <= 0:
            return 0.0
        
        risk_amount = portfolio_equity * risk_per_trade
        stop_distance = price * stop_pct
        position_size = risk_amount / stop_distance
        return position_size


# Singleton instance with default config
DEFAULT_SIZING_CONFIG = PositionSizingConfig()
POSITION_SIZER = PositionSizer(DEFAULT_SIZING_CONFIG)


def size_position(
    symbol: str,
    action: str,
    price: float,
    portfolio_equity: float,
    current_cash: float,
    current_position: Optional[Dict[str, Any]] = None,
    atr: Optional[float] = None,
    volatility: Optional[float] = None,
    confidence: Optional[float] = None,
    stop_distance_pct: Optional[float] = None,
) -> PositionSizeResult:
    """Convenience function to size a position."""
    return POSITION_SIZER.size_position(
        symbol=symbol,
        action=action,
        price=price,
        portfolio_equity=portfolio_equity,
        current_cash=current_cash,
        current_position=current_position,
        atr=atr,
        volatility=volatility,
        confidence=confidence,
        stop_distance_pct=stop_distance_pct
    )
