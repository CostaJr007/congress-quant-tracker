# CongressQuantTracker

**Congressional trading intelligence + CI://TERMINAL market desk**

Track House and Senate periodic transaction reports (PTRs), score them, estimate post-trade performance with **yfinance**, and explore the book in a Next.js app plus **CI://TERMINAL** — a dense Bloomberg-style ASCII desk (no Bloomberg marks or logos).

Product name: **CongressInvests** / **CI**.  
Private repository. Do not commit `.env`, API keys, or the SQLite database.

---

## What it does

| Area | Capability |
|------|------------|
| **Disclosures** | House Clerk FD (zip/PDF) + Senate eFD with fallbacks |
| **Scoring** | 0–100 suspicion score and tags (`routine` → `high_alert`) |
| **Market** | Price since trade date, estimated shares/PnL, charts (yfinance + cache) |
| **Web UI** | Dashboard, politicians, monthly trades, stocks, signals, leaderboard, analyze |
| **CI://TERMINAL** | Monthly wire, member photos, co-holders, sectors, candles, returns board, **CI://COPILOT** (English) |
| **Copilot** | Tool-calling analyst (Groq / OpenAI / local). Always answers in English. |

---

## Architecture

```
┌─────────────────────┐     ┌──────────────────────────┐
│  web_fused (Next.js)│────▶│  FastAPI :8000           │
│  :3000              │     │  SQLite + pipelines      │
└─────────────────────┘     │  yfinance market data    │
                            │  /terminal/  (static)    │
┌─────────────────────┐     │  /politicians/*.jpg      │
│  CI://TERMINAL      │────▶│  /api/terminal/*         │
│  ci_terminal/       │     └──────────────────────────┘
└─────────────────────┘
```

| Component | Path | Port |
|-----------|------|------|
| API | `server/api_server.py` | **8000** |
| Web UI | `web_fused/` | **3000** |
| Terminal | `ci_terminal/` served at `/terminal/` | via 8000 |
| Domain | `src/congress_quant_tracker/` | — |
| Photos | `data/politicians/{bioguide}.jpg` | `/politicians/{bioguide}.jpg` |

---

## Quick start

### Prerequisites

- Python **3.12+** and [uv](https://github.com/astral-sh/uv)
- Node.js **20+** (for `web_fused`)
- Windows / macOS / Linux

### 1. Clone and install

```bash
git clone https://github.com/CostaJr007/congress-quant-tracker.git
cd congress-quant-tracker
uv sync
cd web_fused && npm install && cd ..
```

### 2. Environment

```bash
copy .env.example .env   # Windows
# cp .env.example .env   # Unix
```

| Variable | Default | Role |
|----------|---------|------|
| `MARKET_DATA_ENABLED` | `1` | yfinance (charts, returns, enrich) |
| `NO_YF` | `0` | skip yfinance in the scorer only |
| `GROQ_API_KEY` | — | optional PDF extraction + Copilot |
| `OPENAI_API_KEY` | — | optional Copilot provider |
| `TAVILY_API_KEY` | — | optional search / ticker resolve |
| `DISCORD_WEBHOOK_URL` | — | optional alerts on new / flagged trades |
| `HTTP_PROXY` | — | HTTPS proxy if Senate eFD is blocked |
| `DATABASE_URL` | local SQLite | database URL |

### 3. Run API + UI

Windows shortcut: `run_ui.bat` (API + Next.js + terminal).  
Terminal only: `start.bat`.

```bash
# API (market data ON)
set MARKET_DATA_ENABLED=1
uv run python server/api_server.py

# another shell — Next.js
cd web_fused
echo NEXT_PUBLIC_API_URL=http://localhost:8000 > .env.local
npm run dev -- -p 3000
```

| URL | App |
|-----|-----|
| http://localhost:3000 | CongressInvests UI |
| http://localhost:8000/terminal/ | CI://TERMINAL |
| http://localhost:8000/docs | OpenAPI |

### 4. Data pipelines

```bash
uv run python scripts/update_official.py   # House Clerk
uv run python scripts/update_senate.py     # Senate (direct, then proxy)
uv run python scripts/enrich_all.py        # sectors + photos + options + rescore
uv run python scripts/rescore.py           # rescore only
```

HTTP equivalents live under `POST /api/pipeline/*`.

---

## CI://TERMINAL

Monospace black canvas, orange bars. Brand is **CI://TERMINAL**.

### Main widgets (CONGRESS preset)

| Widget | Role |
|--------|------|
| **MEMBERS · BY MONTH** | Browse by filed/traded month; photo cards; collapse heavy filers |
| **RETURNS LEADERBOARD** | Rank by Δ% / ADJ% (BUY:+Δ, SELL:−Δ) and estimated PnL$ |
| **FOCUSED ASSET** | Daily candles (or line) + TX marker on the trade date |
| **ASSET HOLDERS** | Who else traded the same ticker |
| **POLITICIAN BOOK** | Member tickers + TX/FILED dates |
| **SECTOR DESK** | House × Senate overlap by sector |
| **CI://COPILOT** | F2 — English-only desk analyst |

Presets: `CGS` (default) · `GLB` · `EQ` · `MET` · `NWS`  
Editable layout (EDIT / drag) stored in `localStorage` (`layout.v3`).

First load: if an old layout hides **RETURNS**, click **RESET**.

### Terminal API

| Endpoint | Description |
|----------|-------------|
| `GET /api/terminal/dataset?dataset=tape\|stocks\|…` | yfinance market payloads |
| `GET /api/terminal/congress/wire` | Disclosures (month, chamber, party, side, q) |
| `GET /api/terminal/congress/months` | Months with trades |
| `GET /api/terminal/congress/holders/{ticker}` | Co-holders |
| `GET /api/terminal/congress/sector` | Sector desk |
| `GET /api/terminal/congress/politician?name=` | Member book |
| `GET /api/terminal/congress/returns` | Returns leaderboard |
| `GET /api/terminal/market/{ticker}?from_date=` | Daily OHLCV |
| `POST /api/terminal/chat` | Copilot (English) |
| `GET /api/analyze/overview` | Party / sector / options / suspicious |
| `POST /api/pipeline/enrich` | Sectors + photos + rescore |

LIVE config: `ci_terminal/js/live.config.js` (same-origin).

### Data definitions

- Disclosures use **value ranges**, not exact shares → shares/PnL are **midpoint estimates**.
- `change_pct` = asset move since trade date (yfinance, `auto_adjust`).
- `return_side_adj` = BUY:+Δ% / SELL:−Δ% (side-adjusted outcome).
- Metals on the tape use Yahoo futures (`GC=F`, …) as spot proxies.
- News wire is DEMO unless a live RSS feed succeeds. Do not invent live headlines.

See `ci_terminal/DATA_DEFINITIONS.md` and `ci_terminal/README.md`.

---

## Web UI (`web_fused`)

- Dashboard, Trades (month filter + grouping), Politicians, Stocks, Signals, Leaderboard, Analyze
- Sidebar search + **CI Terminal** link

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Repository layout

```
congress-quant-tracker/
├── server/api_server.py          # FastAPI
├── src/congress_quant_tracker/   # fetchers, parsers, scoring, analyzers
│   ├── enrichers/                # market, terminal, sectors
│   └── agent/                    # CI://COPILOT
├── ci_terminal/                  # CI://TERMINAL static desk
├── web_fused/                    # Next.js UI
├── scripts/                      # update, enrich, rescore
├── dashboard/                    # optional Streamlit
├── tests/
├── pyproject.toml
└── README.md
```

---

## Security

Do **not** commit: `.env`, `*.db`, `data/`, API keys, proxies with credentials.  
`.gitignore` already covers secrets, price cache, `node_modules`, and PDFs.

Photos are served from `data/politicians/` at `/politicians/{bioguide}.jpg`.

Keep the repo **private** if it holds operational data.

```bash
gh repo edit CostaJr007/congress-quant-tracker --visibility private
```

---

## Useful commands

| Command | Action |
|---------|--------|
| `uv run python server/api_server.py` | API :8000 + `/terminal/` |
| `start.bat` | API + open terminal |
| `run_ui.bat` | API + web UI + terminal |
| `cd web_fused && npm run dev` | UI :3000 |
| `uv run python scripts/update_official.py` | House |
| `uv run python scripts/update_senate.py` | Senate |
| `uv run python scripts/enrich_all.py` | Sectors + photos + options + rescore |
| `uv run pytest` | Unit tests |

---

## Known limits

- Yahoo/yfinance: delay and rate limits; first returns-leaderboard load can be slow.
- Senate eFD: Akamai/403 — try a working HTTPS proxy; the pipeline falls back to CongressInvests and retries direct if the proxy is dead.
- Some obscure tickers still have no sector; the desk uses a static ticker→sector map plus yfinance when enabled.
- Exchange holiday calendar is not applied; the session clock may show OPEN on holidays.
- Share and PnL figures are **not** official positions.

---

## License / use

Internal research. Official House/Senate disclosures and unofficial Yahoo quotes.  
Not investment advice. Do not copy Bloomberg trademarks or logos.
