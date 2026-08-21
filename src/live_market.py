from __future__ import annotations

import sys

from .market_data import MarketDataProvider


def main() -> None:
    symbols = sys.argv[1:] or ["AAPL", "MSFT", "GOOGL"]
    provider = MarketDataProvider()
    for symbol in symbols:
        snapshot = provider.fetch(symbol)
        previous_close = snapshot.previous_close if snapshot.previous_close is not None else None
        if previous_close is None:
            previous_close_value = "n/a"
        else:
            previous_close_value = f"{previous_close:.2f}"
        print(
            f"{snapshot.symbol}: price={snapshot.price:.2f}, "
            f"previous_close={previous_close_value}, "
            f"change_pct={snapshot.change_pct:.2f}%, "
            f"volatility={snapshot.volatility:.4f}, source={snapshot.source}, confidence={snapshot.confidence:.3f}"
        )


if __name__ == "__main__":
    main()
