# Graduated Autonomy Engine

A local-first stock trading autonomy framework that scores trade risk, routes actions to autonomous execution, user confirmation, or human review, and logs every decision for auditability.

## Features

- Yahoo Finance market data integration with mock fallback
- Risk scoring across reversibility, data scope, regulatory exposure, and confidence
- Autonomy routing with autonomous / confirm / review levels
- SQLite-backed local persistence
- CLI confirmation flow and webhook simulation
- Optional AWS deployment hooks for future migration
- Unit and integration tests for all required scenarios

## Local-first philosophy

The engine is designed to run completely without AWS. All critical logic remains local-first, while AWS-specific implementations are isolated behind storage and config abstractions.

## Quick start

```bash
cd graduated-autonomy
python -m venv .venv
# Windows:
# .venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
cp .env.example .env
pytest tests/ -v
python cli/test_client.py
python -m src.demo
```

## Risk model

The risk score is computed as:

```text
risk_score = 0.2 * reversibility + 0.3 * data_scope + 0.3 * regulatory + 0.2 * confidence
```

Routing thresholds:

- Below 0.3 → autonomous
- 0.3 to 0.7 → confirmation required
- Above 0.7 → review queue

## Yahoo Finance usage

This project prefers Yahoo Finance for live market context. When live market data is unavailable, the engine automatically falls back to generated mock market data to keep tests deterministic and local development reliable.

## Example scenarios

- HOLD action → low risk
- BUY 100 AAPL → medium risk confirmation
- SELL 1000 AAPL → high risk review
- REBALANCE portfolio → high risk review

## Web frontend

A lightweight Flask dashboard is included for local monitoring and approval workflows.

```bash
cd graduated-autonomy
python -m src.web_app
```

Then open http://127.0.0.1:5000 in the browser to see:

- action overview
- confirmation queue
- human review queue
- audit log panel

## Multi-agent financial research

The dashboard can run the checked-out local `tradingagents` project as a
read-only research engine. It uses Mistral as the shared LLM provider and
combines technical, market, news, and fundamentals analysts with bull/bear
research and risk debate. Its final recommendation is returned to the caller;
it never submits a paper or live trade automatically.

Set `MISTRAL_API_KEY` in `.env`, then install dependencies (the requirements
file installs `../tradingagents` in editable mode). Optionally select models
available to your Mistral account with `MISTRAL_DEEP_THINK_MODEL` and
`MISTRAL_QUICK_THINK_MODEL`.

```bash
curl -X POST http://127.0.0.1:5000/api/financial-analysis \
  -H "Content-Type: application/json" \
  -d '{"symbol":"BTC-USD"}'
```

The response contains the analyst reports, proposed decision, and saved report
directory. To execute any recommended action, submit it separately through the
existing risk-scored approval workflow.

### Resilience configuration

The TradingAgents adapter is configured to balance reliability with data coverage:

- Uses **only yfinance** for market/fundamental/news data
- **Disables FRED** (macro data - requires separate API key)
- **Disables Polymarket** (prediction markets - unreliable connections)
- **Disables Reddit** (social/sentiment analysts not included)
- **Includes only**: market, news, and fundamentals analysts
- Reduced news article limits to minimize API calls
- Increased LLM retry budget to handle temporary rate limits

This configuration avoids all Reddit, Polymarket, and FRED dependencies per requirements.

## Predictive model layer

The project now supports an optional real Kronos model backend when the cloned Kronos repository is available next to this project at:

```text
D:\aivar_project\Kronos
```

If the model is available, the system automatically loads the Kronos predictor and uses it to inform market confidence. If not, it falls back to a lightweight local heuristic so the app remains runnable without the large model dependency.

## Optional AWS deployment

The project includes stub AWS configuration and DynamoDB abstraction, but local execution does not require AWS credentials or services.
