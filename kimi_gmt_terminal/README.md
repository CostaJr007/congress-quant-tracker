# CI://TERMINAL — Congress + Global Market Desk

Bloomberg-style × ASCII workstation that **merges**:

1. **Congressional disclosures** (House + Senate PTRs from SQLite)
2. **Market data** (yfinance quotes/charts)
3. **Relationship views**: who else traded the same ticker; House/Senate overlap by sector

Product brand: **`CI://TERMINAL`** (CongressInvests). No Bloomberg trademarks or logos.

Offline DEMO works by double-clicking `index.html`. LIVE needs FastAPI + DB.

---

## Quick start

### Offline DEMO (no network, no server)

1. Unzip or open the folder `kimi_gmt_terminal/`
2. Double-click **`index.html`** (or open via `file://`)
3. All widgets load from deterministic bundled fixtures (`js/data/fixtures.js`)
4. Top bar shows **DEMO DATA** · LIVE adapter is disabled on `file://`

### LIVE mode (congress + yfinance)

1. From repo root, start the API (market data on):

   ```bat
   set MARKET_DATA_ENABLED=1
   uv run python server\api_server.py
   ```

2. Open: **http://localhost:8000/terminal/**

3. Default preset **CONGRESS**:
   - **Congress Wire** — recent PTRs (click → focus)
   - **Asset Holders** — all pols on the same ticker
   - **Focused Chart** — 60-session OHLCV + trade-date marker
   - **Politician Book** — that member’s tickers
   - **Sector Desk** — House×Senate overlap by sector
   - **Heatmap** — market context

4. Command bar shows **LIVE** / **LIVE CONGRESS** / **LIVE MKT** when adapters succeed. Failures fall back to **DEMO**/**STALE** independently for market vs congress.

Config: `js/live.config.js`

Optional env:

| Variable | Default | Meaning |
|----------|---------|---------|
| `MARKET_DATA_ENABLED` | `1` | Enable yfinance terminal + charts |
| `NO_YF` | `0` | Scorer-only flag; terminal still works if `MARKET_DATA_ENABLED=1` |

No API keys required for Yahoo quotes. Do not commit secrets.

---

## Widgets (spec A–J)

| ID | Module | Notes |
|----|--------|--------|
| A | Global Ticker tape | Indices + XAU/WTI/DXY |
| B | Stock heat matrix | AI-TECH / ENERGY / FINANCIALS |
| C | Market Breadth | From filtered universe only |
| D | Sector Intraday | Equal-weight sector avg |
| E | News Wire | DEMO-labeled unless you add a licensed wire |
| F | AAPL 60-session | Last 60 **trading** days OHLCV |
| G | Precious metals | GC/SI/PL/PA futures as spot proxies |
| H | Market Pulse clock | SSE/HKEX/TSE/LSE/NYSE states |
| I | Global Index list | Americas / Europe / APAC |
| J | Inspector | Provenance: source, as-of, LIVE/DEMO |

Layout: drag/resize in **EDIT LAYOUT**, presets GLOBAL/EQUITIES/METALS/NEWS, `localStorage` persistence.

---

## Data architecture

1. **LIVE ADAPTER** — HTTP to FastAPI → `terminal_market.py` → yfinance  
2. **DEMO ADAPTER** — `js/data/fixtures.js` deterministic fixtures  

Rules:

- `file://` → DEMO only  
- LIVE error → STALE cache or DEMO with visible labels  
- Per-widget `as-of` timestamps  
- News is **never fabricated as live**; items carry `demo: true` / DEMO WIRE  

See **DATA_DEFINITIONS.md**.

---

## API

| Endpoint | Description |
|----------|-------------|
| `GET /api/terminal/health` | yfinance installed / enabled |
| `GET /api/terminal/dataset?dataset=tape` | LIVE payload `{data,asof,convention}` |
| `GET /api/terminal/{dataset}` | Same, path form |
| `GET /terminal/` | Static terminal UI |

Datasets: `tape`, `stocks`, `aapl60`, `metals`, `sectors`, `news`, `quotes`, `meta`.

---

## Zip delivery

Build archive (from repo root):

```powershell
Compress-Archive -Path kimi_gmt_terminal\* -DestinationPath global-market-terminal-final.zip -Force
```

Contents: `index.html`, `css/`, `js/` (adapters, widgets, fixtures, live.config), `fonts/`, `README.md`, `DATA_DEFINITIONS.md`.

---

## Known limitations

- Yahoo delay / rate limits; bulk download may take several seconds cold  
- Metals = futures proxies, not LBMA fixings  
- Sector “intraday” path is linear open→close % (not true tick series)  
- Holiday calendar not applied → session clock may show OPEN on holidays; UI notes **HOLIDAY STATUS UNVERIFIED**  
- News wire is DEMO-labeled without a licensed feed  
- Mobile: stacked reorder, no freeform drag  

---

## Acceptance checklist

- [x] Black canvas, orange bars, mono terminal aesthetic  
- [x] Heatmap + breadth + AAPL 60 sessions + 4 metals  
- [x] Session clock + inspector provenance  
- [x] DEMO offline via `file://`  
- [x] LIVE via yfinance + DEMO/STALE fallback  
- [x] Layout edit / presets / localStorage  
