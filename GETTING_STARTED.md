# Getting Started

## 1. Environment

```bash
# Install Python dependencies (uv or pip)
uv sync
# Or: pip install -e .

# Install frontend dependencies
cd web_fused && npm install && cd ..

# Setup environment variables
copy .env.example .env   # fill keys if you need Copilot / Tavily / Discord
```

`web_fused/.env.local`:

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## 2. Run

```bash
# Shell A: Start API
set MARKET_DATA_ENABLED=1
python server/api_server.py

# Shell B: Start Next.js Web UI
cd web_fused
npm run dev -- -p 3000
```

Shortcut: `run_ui.bat` (API + Next + terminal).  
Terminal only: `start.bat`.

| URL | App |
|-----|-----|
| http://localhost:3000 | CongressInvests UI |
| http://localhost:8000/terminal/ | CI://TERMINAL |
| http://localhost:8000/docs | OpenAPI |

## 3. Data

If SQLite already exists on disk, the API uses it.  
To refresh: `scripts/update_official.py` and `scripts/update_senate.py`.

Fill sectors, photo URLs, options rows, and rescore (fast, no yfinance):

```bash
python scripts/enrich_all.py
```

## 4. Terminal — First use

1. Open `/terminal/`
2. If an old layout hides **RETURNS**, click **RESET**
3. Pick a month on the wire → member cards with photos
4. Click a trade → candles + TX marker
5. **RETURNS LEADERBOARD** may be slow on the first load (yfinance)
6. **F2** opens CI://COPILOT (English reports)

## 5. Do not commit

- `.env`, `*.db`, `data/`, price caches, secrets
