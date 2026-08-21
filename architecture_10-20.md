# Graduated Autonomy Engine - System Architecture

*Document created: 10:20 PM | Last updated: August 19, 2026*

---

## Overview

The **Graduated Autonomy Engine** is a local-first financial trading autonomy framework that scores trade risk, routes actions to autonomous execution, user confirmation, or human review, and logs every decision for auditability. It integrates **TradingAgents** as a read-only multi-agent financial research engine.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Graduated Autonomy Engine                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────┐ │
│  │   Flask Backend     │───▶│   TradingAgents     │───▶│   Frontend   │ │
│  │   (web_app.py)      │    │   (Research Engine) │    │  (index.html)│ │
│  └─────────────────────┘    └─────────────────────┘    └─────────────┘ │
│           │                        │                         │           │
│           ▼                        ▼                         ▼           │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                        Data Layer (yfinance)                        │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌──────────────────────┐  │  │
│  │  │ Prices  │  │  News   │  │Fundamentals│  │Company Info/Analyst │  │  │
│  │  │ History │  │         │  │Statements  │  │     Recommendations   │  │  │
│  │  └─────────┘  └─────────┘  └─────────┘  └──────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Component Architecture

### 1. Frontend Layer

**File:** `templates/index.html`

- **Framework:** Vanilla HTML/CSS/JavaScript (No React/Vue)
- **Styling:** Custom dark green terminal theme
- **Charting:** Chart.js for price visualization
- **Real-time:** Socket.IO for live market updates

**Panels:**
- Watchlist (live prices)
- Market Forecast Overview
- Chart Panel (OHLCV + Kronos forecast)
- Paper Portfolio ($100 simulated trading)
- **Multi-Agent Financial Research** (TradingAgents integration)
- Actions/Confirmations/Reviews/Audit Log

**JavaScript Features:**
- Auto-refreshing charts (1-second interval)
- Socket.IO event handlers
- Financial Research form with async API calls
- Dynamic chart rendering

---

### 2. Backend Layer

**File:** `src/web_app.py`

- **Framework:** Flask + Flask-SocketIO
- **Port:** 5000
- **Host:** 127.0.0.1

**Key Components:**

| Component | File | Purpose |
|-----------|------|---------|
| Market Data | `src/market_data.py` | yfinance-based price/fundamental data |
| Market Predictor | `src/predictor.py` | Kronos model integration |
| Risk Scorer | `src/risk_scorer.py` | Risk assessment (0-1 scale) |
| Autonomy Router | `src/autonomy_router.py` | Route to autonomous/confirm/review |
| Trade Executor | `src/trade_executor.py` | Paper trade execution |
| Storage | `src/storage/sqlite_storage.py` | SQLite persistence |
| TradingAgents Adapter | `src/trading_agents_adapter.py` | Bridge to TradingAgents |

---

## Data Flow Architecture

### Primary Data Source: yfinance

```
┌─────────────────────────────────────────────────────────────────┐
│                         yfinance API                               │
│  (Single unified data source for reliability and simplicity)       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    MarketDataProvider                              │
│  ┌─────────────────────┐  ┌─────────────────────┐               │
│  │  fetch(symbol)       │  │  history(symbol)     │               │
│  │  -> Price           │  │  -> OHLCV Data       │               │
│  │  -> Volatility      │  │  -> Volume           │               │
│  │  -> Change %        │  │  -> Source: yfinance │               │
│  │  -> Previous Close  │  └─────────────────────┘               │
│  └─────────────────────┘                                            │
│                       │                                              │
│                       ▼                                              │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │                    5-second Cache                              │ │
│  │  (Reduces API calls while maintaining freshness)               │ │
│  └──────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Market Predictor                                │
│  ┌─────────────────────┐  ┌─────────────────────┐               │
│  │  Kronos Model       │  │  Heuristic Fallback  │               │
│  │  (if available)      │  │  (if Kronos absent)  │               │
│  └─────────────────────┘  └─────────────────────┘               │
│                        │                                          │
│                        ▼                                          │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  Signal: {direction, confidence, expected_return, summary}    │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Socket.IO Live Updates

```
┌─────────────────────┐     ┌─────────────────────┐
│  Backend            │     │  Frontend           │
│  stream_market_updates()│────▶│  socket.on('market_update')│
│  - Runs every 2 sec │     │  - Updates watchlist │
│  - Fetches all       │     │  - Updates chart    │
│    watchlist symbols │     │  - Shows live prices │
└─────────────────────┘     └─────────────────────┘
```

### TradingAgents Research Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                  POST /api/financial-analysis                       │
│                     {symbol, trade_date}                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  TradingAgentsAdapter                              │
│  Configuration:                                              │
│    - llm_provider: mistral                                  │
│    - data_vendors: yfinance (all categories)                 │
│    - macro_data: DISABLED (FRED)                            │
│    - prediction_markets: DISABLED (Polymarket)                │
│    - news_article_limit: 10                                 │
│    - global_news_article_limit: 5                           │
│    - llm_max_retries: 3                                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  TradingAgentsGraph                                          │
│  selected_analysts: (market, news, fundamentals)               │
│    ┌─────────┐  ┌─────────┐  ┌─────────┐       │
│    │ Market  │  │  News   │  │Fundamentals│      │
│    │ Analyst│  │ Analyst│  │  Analyst │       │
│    └─────────┘  └─────────┘  └─────────┘  └─────────┘       │
│           │            │            │            │            │
│           └────────────┼────────────┘            │
│                        ▼                                   │
│              ┌─────────────────────┐                           │
│              │  Researcher Team    │                           │
│              │  (Bull/Bear debate) │                           │
│              └─────────────────────┘                           │
│                        │                                   │
│                        ▼                                   │
│              ┌─────────────────────┐                           │
│              │  Risk Management    │                           │
│              │  + Portfolio Manager│                           │
│              └─────────────────────┘                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Returns:                                                   │
│    - final_trade_decision (BUY/HOLD/SELL)                      │
│    - trader_investment_plan                                │
│    - market_report                                         │
│    - fundamentals_report                                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Risk Model

### Risk Score Calculation

```
risk_score = 0.2 * reversibility + 0.3 * data_scope + 0.3 * regulatory + 0.2 * confidence
```

### Routing Thresholds

| Risk Score | Routing | Color | Action |
|------------|---------|-------|--------|
| < 0.3 | Autonomous | Green | Auto-execute |
| 0.3 - 0.7 | Confirmation | Amber | User approval |
| > 0.7 | Review | Red | Human review |

---

## File Structure

```
graduated-autonomy/
├── src/
│   ├── __init__.py
│   ├── web_app.py              # Flask backend + Socket.IO
│   ├── market_data.py          # yfinance-only data provider
│   ├── predictor.py            # Kronos forecasting
│   ├── risk_scorer.py          # Risk assessment
│   ├── autonomy_router.py      # Decision routing
│   ├── trade_executor.py       # Paper trading
│   ├── trading_agents_adapter.py # TradingAgents bridge
│   ├── strategy.py            # Trading strategies
│   ├── live_market.py
│   ├── demo.py
│   ├── confirmation_handler.py
│   ├── audit_logger.py
│   └── storage/
│       └── sqlite_storage.py
├── templates/
│   ├── index.html             # Dashboard with Financial Research panel
│   └── strategies.html
├── config/
├── cli/
├── lambda/
├── terraform/
├── data/
├── tests/
└── .env                       # MISTRAL_API_KEY
```

---

## API Endpoints

### HTTP API (http://127.0.0.1:5000)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/` | Dashboard |
| GET | `/api/market` | Market snapshots |
| GET | `/api/forecast` | Signal forecasts |
| POST | `/api/financial-analysis` | TradingAgents research |
| GET | `/api/chart?symbol=BTC-USD` | OHLCV + forecast (1s refresh) |
| POST | `/api/paper-trade` | Execute paper trade |
| GET/POST | `/api/decisions` | Trade decisions |
| POST | `/api/confirmations` | Approve/reject |
| GET/POST | `/confirmations` | Confirmation queue |
| GET | `/reviews` | Review queue |
| GET | `/audit` | Audit log |
| GET/POST | `/strategies` | Strategy management |

### WebSocket Events

| Event | Direction | Purpose |
|-------|-----------|---------|
| `connect` | Server -> Client | Initial connection |
| `request_market` | Client -> Server | Request fresh data |
| `market_update` | Server -> Client | Live market broadcast (every 2s) |

---

## Key Design Decisions

### 1. yfinance as Unified Data Source
- **Why:** Single dependency, reliable, comprehensive
- **What it provides:** Prices, news, fundamentals, earnings, analyst data
- **What it replaces:** Binance API, FRED, Polymarket
- **Fallback:** Mock data for offline testing
- **Note:** Reddit is disabled per requirements

### 2. Local-First Philosophy
- No AWS required for core functionality
- SQLite for persistence
- All critical logic runs locally
- AWS abstractions isolated for future migration

### 3. Read-Only Research Integration
- TradingAgents provides analysis only
- No automatic trade execution
- Results feed into existing risk/approval workflow
- User maintains full control

### 4. Progressive Autonomy
- Low risk -> Autonomous execution
- Medium risk -> User confirmation
- High risk -> Human review
- All decisions logged for audit

---

## Data Sources Summary

| Data Type | Source | Status |
|-----------|--------|--------|
| Price History | yfinance | Active |
| Live Quotes | yfinance | Active |
| News | yfinance | Active |
| Fundamentals | yfinance | Active |
| Company Info | yfinance | Active |
| Analyst Data | yfinance | Active |
| Sentiment | Reddit (via social analyst) | **DISABLED** |
| Macro Data | FRED | Disabled |
| Prediction Markets | Polymarket | Disabled |
| LLM | Mistral | Active |

---

## Flow Diagram

```
User
  |
  ▼
Browser (127.0.0.1:5000)
  |
  ├─ GET / -> Dashboard
  |     |
  |     ├─ Socket.IO -> Live market (2s)
  |     |
  |     ├─ setInterval -> Chart refresh (1s)
  |     |
  |     └─ POST /api/financial-analysis -> TradingAgents
  |
  └─ POST /api/paper-trade -> Paper Portfolio
        |
        ▼
Flask Backend
  |
  ├─ MarketDataProvider -> yfinance
  |       |
  |       └─ Cache (5s) -> Reduce API calls
  |
  ├─ MarketPredictor -> Kronos/Fallback
  |
  ├─ RiskScorer -> Calculate risk (0-1)
  |
  ├─ AutonomyRouter -> Route decision
  |
  └─ TradingAgentsAdapter -> Research pipeline
        |
        └─ TradingAgentsGraph -> Multi-agent analysis
              |
              ├─ Market Analyst
              ├─ News Analyst
              ├─ Fundamentals Analyst
              |
              └─ Researcher + Risk Manager
                    |
                    └─ Decision + Reports
```

---

## Configuration

### Environment Variables (.env)

```bash
# Required for TradingAgents
MISTRAL_API_KEY=your_api_key_here

# Optional: Model selection
MISTRAL_DEEP_THINK_MODEL=mistral-small-latest
MISTRAL_QUICK_THINK_MODEL=mistral-small-latest

# Optional: TradingAgents settings
TRADINGAGENTS_MAX_DEBATE_ROUNDS=1
TRADINGAGENTS_MAX_RISK_ROUNDS=1
```

### Requirements (requirements.txt)

```
yfinance>=0.2.54
pandas>=2.0.0
python-dotenv>=1.0.0
Flask>=3.0.0
Flask-SocketIO>=5.3.0
-e ../tradingagents  # Local TradingAgents package
```

---

## Summary

The Graduated Autonomy Engine architecture is built on:

1. **Simplicity:** yfinance as the single data source
2. **Reliability:** Caching, fallbacks, and error handling
3. **Control:** Read-only research with user-driven execution
4. **Transparency:** All decisions logged and auditable
5. **Extensibility:** Clean separation of components

The system provides a production-ready framework for testing trading autonomy concepts while maintaining safety through graduated risk controls.
