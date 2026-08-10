# 🏛️ Autonomous AI Hedge Fund — CryptoTradingAssistant

> *"The goal of a successful trader is to make the best trades. Money is secondary."* — Alexander Elder

An autonomous, multi-agent AI trading system that operates like a miniature hedge fund. It runs a Night Shift research team, a Morning Strategy compiler, real-time SMC (Smart Money Concepts) execution, and a Family Office Dashboard — all deployed serverlessly on Railway with PostgreSQL persistence.

---

## 📐 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    FAMILY OFFICE DASHBOARD                      │
│              (React + Flask @ Railway)                          │
│   Master Brain │ Trade History │ Backtest Results │ Status      │
└────────────────────────────┬────────────────────────────────────┘
                             │ REST API
┌────────────────────────────┴────────────────────────────────────┐
│                     POSTGRESQL (Railway)                         │
│  ┌─────────────┐  ┌──────────────────────────────────────────┐ │
│  │ system_files │  │ ohlcv_1m │ ohlcv_5m │ ohlcv_1h │ ...   │ │
│  │  (VFS layer) │  │         (Market Data Tables)             │ │
│  └─────────────┘  └──────────────────────────────────────────┘ │
└────────────────────────────┬────────────────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
   ┌─────┴─────┐     ┌──────┴──────┐    ┌───────┴───────┐
   │ Night Shift│     │  Day Shift  │    │  Scanners     │
   │ (Research) │     │ (Execution) │    │ (Catalysts)   │
   └───────────┘     └─────────────┘    └───────────────┘
```

### Core Modules

| File | Role | Market Wizards Parallel |
|:--|:--|:--|
| `bot_runner.py` | **The Trader.** SMC execution engine with killzone scheduling, HTF bias, LTF entry. Runs during London & New York sessions. | *Paul Tudor Jones:* "I'm always thinking about losing money as opposed to making money." — The bot's `risk_modifier` and whipsaw protection embody this. |
| `deep_researcher.py` | **The Night Shift.** Runs Macro, Quant, and Risk agents overnight. CIO synthesizes a correlation matrix at 07:50. Portfolio Manager sets daily config at 08:00. | *Ed Seykota:* "Systems don't need to be changed. The trick is for a trader to develop a system with which he is compatible." — The agents write to a persistent Master Brain that evolves, never resets. |
| `catalyst_scanner.py` | **The Fundamentals Analyst.** Gemini + Google Search grounding to find macro catalysts and generate swing trade setups with structured JSON. | *Stanley Druckenmiller:* "The way to build long-term returns is through preservation of capital and home runs." — The scanner searches for asymmetric, catalyst-driven setups, not noise. |
| `congress_scanner.py` | **The Insider Flow Tracker.** Mirrors US Congressional stock trades as a leading signal. | *Michael Steinhardt:* "I found that the weights of the various factors change over time." — Congressional flow is one signal among many, not the sole driver. |
| `data_manager.py` | **The Quant's Database.** SQLAlchemy-backed OHLCV storage across 6 timeframes × 5 assets. Dual-mode: Postgres (prod) / SQLite (dev). | *Jim Simons (Renaissance):* "We search through historical data looking for anomalous patterns." — All quant work starts from this clean, normalized data layer. |
| `file_store.py` | **The Virtual File System.** Intercepts all `read_file`/`write_file` calls and routes them to a `system_files` table in Postgres. Falls back to local disk if no `DATABASE_URL`. | This is pure infrastructure — ensuring the bot never gets amnesia on Railway restarts. |
| `backtest.py` | **The Backtester.** Multi-timeframe grid search across SMC and Rapid-Fire strategies (7d + 30d lookback). Results feed back into the Morning Strategy. | *Larry Hite:* "Throughout my financial career, I have continually witnessed examples of other people that I have known being ruined by a failure to respect risk." — Every strategy is graded by historical win rate before deployment. |
| `ai_evaluator.py` | **The Self-Grader.** Downloads post-prediction price data via yFinance and scores past AI swing trades (Win/Loss/Pending). Feeds the grade back into the Master Brain. | *Ray Dalio:* "Pain + Reflection = Progress." — The evaluator is the bot's self-reflection mechanism. |
| `macro_research.py` | **The Macro Dashboard.** Binance Long/Short ratio, economic calendar (Finnhub), and backtest summary — compiled into a pre-market context report. | *George Soros:* "It's not whether you're right or wrong, it's how much you make when you're right and how much you lose when you're wrong." — The `risk_modifier` system sizes down on news days. |
| `dashboard_api.py` | **The Family Office.** Flask API serving the React dashboard. Exposes Master Brain, trade history, backtest results, market data, and system status. | The dashboard a fund manager sees every morning before the open. |
| `execution_engine.py` | **The Broker Bridge.** Stub for MetaApi/Exness MT5 integration. Currently simulates executions. | *Not yet live.* Wiring up real execution is the next milestone. |

---

## 🗄️ Database Architecture (Code Review)

### Current Schema

**1. Virtual File System (`system_files` via `file_store.py`)**

```sql
CREATE TABLE system_files (
    filename VARCHAR(255) PRIMARY KEY,
    content  TEXT
);
```

Stores: `master_brain.md`, `ai_trade_history.json`, `backtest_results.md`, `ai_strategy_config.json`, `last_signal.json`

**2. Market Data (6 tables via `data_manager.py`)**

```sql
-- One table per timeframe: ohlcv_1m, ohlcv_5m, ohlcv_15m, ohlcv_1h, ohlcv_4h, ohlcv_1d
CREATE TABLE ohlcv_{interval} (
    symbol    VARCHAR(50),
    time      TIMESTAMP,
    open      REAL,
    high      REAL,
    low       REAL,
    close     REAL,
    volume    REAL,
    PRIMARY KEY (symbol, time)
);
```

Tracked assets: `BTC-USD`, `ETH-USD`, `SOL-USD`, `GC=F` (Gold), `DX-Y.NYB` (DXY)

### What Works Well ✅

1. **Dual-mode engine pattern.** `get_engine()` checks `DATABASE_URL` and falls back to SQLite. This means local dev "just works" without Postgres.
2. **Virtual File System is elegant.** Instead of rewriting 35+ `open()` calls, `file_store.py` acts as a transparent proxy. Clean separation of concerns.
3. **UPSERT strategy is correct.** The `DELETE → INSERT` pattern in `fetch_and_store_data()` handles the lack of `ON CONFLICT DO UPDATE` portability between SQLite and Postgres.
4. **Deduplication in prompts.** The `CRITICAL DEDUPLICATION RULE` injected into every agent prevents the Master Brain from bloating with repeated signals.
5. **Timestamped trade history.** Every trade record carries `date_issued`, enabling proper self-grading by `ai_evaluator.py`.

### Issues Found & Improvements 🔧

| # | Issue | Severity | Improvement |
|:--|:--|:--|:--|
| 1 | **Connection leak in `file_store.py`** — Every call to `read_file()` / `write_file()` opens a new `psycopg2` connection. Under heavy load (all agents + dashboard polling), this will exhaust Postgres connection limits. | 🔴 High | Use a connection pool (`psycopg2.pool.SimpleConnectionPool`) or migrate `file_store.py` to use SQLAlchemy like `data_manager.py` already does. |
| 2 | **Duplicate `get_engine()` definitions** — `data_manager.py` and `dashboard_api.py` both define identical `get_engine()` functions. DRY violation. | 🟡 Medium | Extract into a shared `db.py` module that both import from. |
| 3 | **SQL injection surface in `data_manager.py`** — `get_historical_data()` and `calculate_correlation_matrix()` use f-string interpolation for SQL queries: `f"SELECT * FROM {table_name} WHERE symbol='{symbol}'"`. While the inputs are internally controlled, this is a bad habit. | 🟡 Medium | Use parameterized queries with `:symbol` placeholders consistently (as `update_all_data()` already does correctly). |
| 4 | **`ai_evaluator.py` bypasses `file_store`** — Still uses raw `os.path.exists()` + `open()` to read `ai_trade_history.json`. This means evaluations will fail on Railway because the file doesn't exist on the ephemeral filesystem. | 🔴 High | Migrate to `from file_store import read_file`. |
| 5 | **`wallet_tracker.py` bypasses `file_store`** — Uses raw `open()` for `tracked_wallets.json` and `wallet_tracker_state.json`. Same ephemeral filesystem issue. | 🟡 Medium | Migrate to `file_store`. |
| 6 | **`macro_research.py` bypasses `file_store`** — Line 116: `with open("backtest_results.md", "r")`. Same issue. | 🟡 Medium | Migrate to `file_store`. |
| 7 | **No `updated_at` timestamp on `system_files`** — We can't tell when a file was last modified. Useful for debugging and for the CIO to know how stale the Master Brain is. | 🟢 Low | Add `updated_at TIMESTAMP DEFAULT NOW()` column. |
| 8 | **`import sqlite3` still in `dashboard_api.py`** — Dead import on line 3. Will confuse future readers. | 🟢 Low | Remove it. |
| 9 | **Engine created per-call** — `get_engine()` creates a new `SQLAlchemy` engine on every function call. SQLAlchemy engines are designed to be long-lived singletons with internal connection pooling. | 🟡 Medium | Create the engine once at module level: `_engine = None; def get_engine(): ...` with caching. |
| 10 | **No index on `ohlcv_*.symbol`** — Queries filter by `symbol` constantly, but there's no explicit index beyond the composite PK. Postgres will use the PK index, but a dedicated index on `symbol` alone would speed up `COUNT(*)` queries. | 🟢 Low | Add `CREATE INDEX IF NOT EXISTS idx_{table}_symbol ON {table}(symbol)`. |

---

## 🧠 Market Wizards Philosophy

This system's architecture embodies several principles from Jack Schwager's *Market Wizards* interviews:

### 1. "Cut your losses short, let your winners run" — *Ed Seykota*
The bot's SMC strategy uses a strict **1:2 minimum risk-reward ratio** (upgraded to 1:3 for A+ setups). The `whipsaw_buffer_pct` dynamically widens stops on news days — protecting capital without removing upside.

### 2. "I just wait until there is money lying in the corner, and all I have to do is go over there and pick it up" — *Jim Rogers*
The `catalyst_scanner.py` and `congress_scanner.py` don't trade every day. They search for **asymmetric, catalyst-driven setups** — a congressional insider buying $5M of a stock, or a major FOMC pivot — and only then generate a setup. This is the opposite of overtrading.

### 3. "The most important rule of trading is to play great defense, not great offense" — *Paul Tudor Jones*
The entire `run_risk_agent()` → `risk_modifier` → `REDUCED` position sizing pipeline exists purely for capital preservation. On high-impact news days, the bot automatically halves position size. If retail is heavily one-sided (L/S ratio > 2.0 or < 0.5), the bot **fades the crowd** — refusing to take the consensus trade.

### 4. "Losers average losers" — *Paul Tudor Jones*
The bot never adds to losing positions. Each SMC setup is a discrete, independent trade with a hard stop loss. There is no martingale, no grid, no DCA.

### 5. "Pain + Reflection = Progress" — *Ray Dalio*
The `ai_evaluator.py` is the system's **self-reflection loop**. It downloads actual price data after a prediction was made, grades the trade as WIN/LOSS/PENDING, and feeds the report back into the Master Brain. The Quant and CIO agents then read this grade and adjust their research accordingly. This is algorithmic *Radical Transparency*.

### 6. "I'm always thinking about losing money as opposed to making money" — *Paul Tudor Jones*
The Night Shift's entire purpose is risk reduction. The CIO doesn't ask "what should I buy?" — it asks "where do Macro, Micro, and Math **contradict** each other?" and labels those zones as **Do Not Trade**. High-probability zones are where all three align.

---

## ⚙️ Environment Variables

| Variable | Required | Description |
|:--|:--|:--|
| `DATABASE_URL` | ✅ Prod | Railway Postgres connection string |
| `GEMINI_API_KEY` | ✅ | Google Gemini API key for all AI agents |
| `DISCORD_WEBHOOK_URL` | ✅ | Discord channel webhook for trade alerts |
| `TWELVEDATA_API_KEY` | ✅ | TwelveData API for Gold/DXY OHLCV data |
| `FINNHUB_API_KEY` | Optional | Finnhub economic calendar (CPI, FOMC, NFP) |
| `ETHERSCAN_API_KEY` | Optional | Etherscan for whale wallet tracking |
| `METAAPI_TOKEN` | Optional | MetaApi cloud SDK for live MT5 execution |
| `METAAPI_ACCOUNT_ID` | Optional | MetaApi account ID for Exness broker |

## 🚀 Deployment

**Local Development:**
```bash
pip install -r requirements.txt
python bot_runner.py
```

**Railway (Production):**
1. Push to GitHub → Railway auto-deploys from `main`.
2. Attach a PostgreSQL plugin and reference `${{ Postgres.DATABASE_URL }}`.
3. The bot auto-detects `DATABASE_URL` and routes all storage to Postgres.

---

## 📁 File Manifest

```
CryptoTradingAssistant/
├── bot_runner.py          # Main entry point. Scheduler + SMC execution.
├── deep_researcher.py     # Night Shift AI research loop.
├── catalyst_scanner.py    # Gemini-powered catalyst & swing trade scanner.
├── congress_scanner.py    # Congressional insider trade tracker.
├── data_manager.py        # SQLAlchemy OHLCV data pipeline.
├── file_store.py          # Virtual File System (Postgres ↔ local fallback).
├── dashboard_api.py       # Flask API for the Family Office Dashboard.
├── macro_research.py      # Pre-market macro context (sentiment + calendar).
├── backtest.py            # Multi-timeframe SMC & Rapid-Fire backtester.
├── ai_evaluator.py        # Self-grading loop for past AI predictions.
├── execution_engine.py    # MetaApi MT5 broker bridge (stub).
├── wallet_tracker.py      # Etherscan whale wallet monitor.
├── wallet_sourcer.py      # Wallet discovery via on-chain analysis.
├── structure_trader.py    # Legacy Streamlit SMC screener UI.
├── requirements.txt       # Python dependencies.
└── dashboard/             # React frontend (Vite + TypeScript).
    ├── src/App.tsx
    └── dist/              # Production build served by Flask.
```
