"""Read-only bridge from the dashboard to the local TradingAgents package.

TradingAgents produces research and a proposed trade decision.  This adapter
does not execute it; the platform's existing risk and confirmation workflow
remains responsible for all actions.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Any, Callable


class TradingAgentsUnavailableError(RuntimeError):
    """Raised when the optional local TradingAgents dependency is unavailable."""


def _load_graph_type() -> type:
    try:
        from tradingagents.graph.trading_graph import TradingAgentsGraph
    except ImportError as exc:
        raise TradingAgentsUnavailableError(
            "TradingAgents is not installed. Run `pip install -r requirements.txt` "
            "from the graduated-autonomy directory."
        ) from exc
    return TradingAgentsGraph


class TradingAgentsAdapter:
    """Create a Mistral-backed TradingAgents graph for one analysis request."""

    def __init__(
        self,
        project_dir: Path,
        graph_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.project_dir = Path(project_dir)
        self._graph_factory = graph_factory

    @staticmethod
    def _asset_type(symbol: str) -> str:
        return "crypto" if symbol.upper().endswith("-USD") else "stock"

    def _config(self) -> dict[str, Any]:
        if not os.environ.get("MISTRAL_API_KEY"):
            raise TradingAgentsUnavailableError("MISTRAL_API_KEY is not configured.")

        try:
            from tradingagents.default_config import DEFAULT_CONFIG
        except ImportError as exc:
            raise TradingAgentsUnavailableError(
                "TradingAgents is not installed. Run `pip install -r requirements.txt` "
                "from the graduated-autonomy directory."
            ) from exc

        config = DEFAULT_CONFIG.copy()
        integration_dir = self.project_dir / "data" / "tradingagents"
        
        # Use yfinance for market/fundamental/news data to ensure reliability
        # FRED, Polymarket, and Reddit are disabled as requested
        # Only yfinance-based analysts are used: market, news, fundamentals
        config.update(
            {
                "llm_provider": "mistral",
                # Mistral model IDs are intentionally configurable because account
                # availability changes. This can be overridden in .env.
                "deep_think_llm": os.getenv("MISTRAL_DEEP_THINK_MODEL", "mistral-small-latest"),
                "quick_think_llm": os.getenv("MISTRAL_QUICK_THINK_MODEL", "mistral-small-latest"),
                "data_cache_dir": str(integration_dir / "cache"),
                "results_dir": str(integration_dir / "results"),
                "memory_log_path": str(integration_dir / "memory" / "trading_memory.md"),
                "max_debate_rounds": int(os.getenv("TRADINGAGENTS_MAX_DEBATE_ROUNDS", "1")),
                "max_risk_discuss_rounds": int(os.getenv("TRADINGAGENTS_MAX_RISK_ROUNDS", "1")),
                # Use yfinance for all data vendor categories
                # FRED, Polymarket, and Reddit are explicitly disabled per requirements
                # Setting to "none" causes route_to_vendor to raise ValueError which is caught by LangChain
                # and returned as an error to the LLM, preventing these vendors from being used
                "data_vendors": {
                    "core_stock_apis": "yfinance",
                    "technical_indicators": "yfinance",
                    "fundamental_data": "yfinance",
                    "news_data": "yfinance",
                    "macro_data": "none",  # Disable FRED (requires API key)
                    "prediction_markets": "none",  # Disable Polymarket (unreliable)
                },
                # Reduce news fetching to minimize API calls and rate limits
                "news_article_limit": 10,
                "global_news_article_limit": 5,
                # Increase retry budget for LLM calls
                "llm_max_retries": 3,
            }
        )
        return config

    def analyze(self, symbol: str, trade_date: str | None = None) -> dict[str, Any]:
        symbol = symbol.strip().upper()
        if not symbol:
            raise ValueError("A symbol is required.")
        trade_date = trade_date or date.today().isoformat()

        graph_type = self._graph_factory or _load_graph_type()
        # Use only yfinance-based analysts (market, news, fundamentals)
        # Social analyst (Reddit) is disabled per requirements
        graph = graph_type(
            selected_analysts=("market", "news", "fundamentals"),
            config=self._config(),
            debug=False
        )
        final_state, signal = graph.propagate(symbol, trade_date, asset_type=self._asset_type(symbol))
        report_path = graph.save_reports(final_state, symbol)
        return {
            "symbol": symbol,
            "trade_date": trade_date,
            "asset_type": self._asset_type(symbol),
            "signal": signal,
            "final_trade_decision": final_state.get("final_trade_decision", ""),
            "trader_plan": final_state.get("trader_investment_plan", ""),
            "reports": {
                "market": final_state.get("market_report", ""),
                "fundamentals": final_state.get("fundamentals_report", ""),
                "news": final_state.get("news_report", ""),
                # sentiment report removed - social/Reddit analyst disabled
            },
            "report_path": str(report_path),
        }
