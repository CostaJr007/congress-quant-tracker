/* Copy to live.config.js and adjust base URL if API is not same-origin.
   Example for a separate host:
     quotes: "http://localhost:8000/api/terminal/dataset"
*/
window.GMT_LIVE_CONFIG = {
  sourceName: "your-proxy / yfinance",
  timeoutMs: 8000,
  endpoints: {
    quotes: "/api/terminal/dataset",
    tape: "/api/terminal/dataset",
    stocks: "/api/terminal/dataset",
    aapl60: "/api/terminal/dataset",
    metals: "/api/terminal/dataset",
    sectors: "/api/terminal/dataset",
    news: "/api/terminal/dataset"
  }
};
