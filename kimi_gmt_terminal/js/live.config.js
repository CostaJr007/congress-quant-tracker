/* LIVE configuration for CI://TERMINAL — same-origin FastAPI */
window.GMT_LIVE_CONFIG = {
  sourceName: "congress-quant-tracker / yfinance + sqlite",
  timeoutMs: 20000,
  endpoints: {
    quotes:  "/api/terminal/dataset",
    tape:    "/api/terminal/dataset",
    stocks:  "/api/terminal/dataset",
    aapl60:  "/api/terminal/dataset",
    metals:  "/api/terminal/dataset",
    sectors: "/api/terminal/dataset",
    news:    "/api/terminal/dataset",
    meta:    "/api/terminal/dataset",
    congressWire:    "/api/terminal/congress/wire",
    congressMonths:  "/api/terminal/congress/months",
    congressHolders: "/api/terminal/congress/holders",
    congressSectors: "/api/terminal/congress/sectors",
    congressSector:  "/api/terminal/congress/sector",
    congressPol:     "/api/terminal/congress/politician",
    congressSummary: "/api/terminal/congress/summary",
    congressReturns: "/api/terminal/congress/returns",
    marketChart:     "/api/terminal/market"
  },
  note: "LIVE only — SQLite PTRs + yfinance. Serve via FastAPI /terminal/"
};
