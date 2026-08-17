/* Deterministic DEMO congress fixtures for offline file:// CI://TERMINAL */
window.GMT_CONGRESS_FIXTURES = {
  meta: {
    fixturesVersion: "congress-1.0.0",
    demoAsOf: "2026-07-24T16:05:00-04:00",
    convention: "DEMO congressional disclosures — illustrative only, not real PTRs. Labels carry demo:true."
  },
  summary: {
    total_trades: 24,
    total_politicians: 6,
    data_age_days: 3,
    house_trades: 16,
    senate_trades: 8,
    top_tickers: [
      { ticker: "NVDA", trades: 5, volume: 250000 },
      { ticker: "AAPL", trades: 4, volume: 180000 },
      { ticker: "XOM", trades: 3, volume: 120000 },
      { ticker: "JPM", trades: 3, volume: 90000 }
    ]
  },
  wire: [
    { id: 9001, ticker: "NVDA", asset: "NVIDIA Corp", side: "BUY", trade_date: "2026-07-18", filing_date: "2026-07-22", amount: "$15,001 - $50,000", amount_min: 15001, amount_max: 50000, score: 72, tag: "noteworthy", sector: "Technology", politician: "Demo House A", party: "D", chamber: "House", state_district: "CA-12", price_change_pct: 2.1, shares_est: 180, demo: true },
    { id: 9002, ticker: "AAPL", asset: "Apple Inc", side: "BUY", trade_date: "2026-07-15", filing_date: "2026-07-21", amount: "$1,001 - $15,000", amount_min: 1001, amount_max: 15000, score: 45, tag: "routine", sector: "Technology", politician: "Demo Senate B", party: "R", chamber: "Senate", state_district: "TX", price_change_pct: 1.2, shares_est: 40, demo: true },
    { id: 9003, ticker: "XOM", asset: "Exxon Mobil", side: "SELL", trade_date: "2026-07-10", filing_date: "2026-07-20", amount: "$50,001 - $100,000", amount_min: 50001, amount_max: 100000, score: 68, tag: "noteworthy", sector: "Energy", politician: "Demo House C", party: "R", chamber: "House", state_district: "TX-02", price_change_pct: -0.4, shares_est: 650, demo: true },
    { id: 9004, ticker: "JPM", asset: "JPMorgan Chase", side: "BUY", trade_date: "2026-07-08", filing_date: "2026-07-19", amount: "$15,001 - $50,000", amount_min: 15001, amount_max: 50000, score: 55, tag: "routine", sector: "Financials", politician: "Demo Senate B", party: "R", chamber: "Senate", state_district: "TX", price_change_pct: 0.8, shares_est: 110, demo: true },
    { id: 9005, ticker: "NVDA", asset: "NVIDIA Corp", side: "BUY", trade_date: "2026-07-05", filing_date: "2026-07-18", amount: "$100,001 - $250,000", amount_min: 100001, amount_max: 250000, score: 88, tag: "high_alert", sector: "Technology", politician: "Demo Senate D", party: "D", chamber: "Senate", state_district: "NY", price_change_pct: 3.4, shares_est: 900, demo: true },
    { id: 9006, ticker: "MSFT", asset: "Microsoft", side: "BUY", trade_date: "2026-07-02", filing_date: "2026-07-17", amount: "$1,001 - $15,000", amount_min: 1001, amount_max: 15000, score: 40, tag: "routine", sector: "Technology", politician: "Demo House A", party: "D", chamber: "House", state_district: "CA-12", price_change_pct: 0.5, shares_est: 20, demo: true },
    { id: 9007, ticker: "CVX", asset: "Chevron", side: "BUY", trade_date: "2026-06-28", filing_date: "2026-07-16", amount: "$15,001 - $50,000", amount_min: 15001, amount_max: 50000, score: 61, tag: "noteworthy", sector: "Energy", politician: "Demo House C", party: "R", chamber: "House", state_district: "TX-02", price_change_pct: -1.1, shares_est: 200, demo: true },
    { id: 9008, ticker: "AAPL", asset: "Apple Inc", side: "SELL", trade_date: "2026-06-25", filing_date: "2026-07-15", amount: "$1,001 - $15,000", amount_min: 1001, amount_max: 15000, score: 38, tag: "routine", sector: "Technology", politician: "Demo House E", party: "D", chamber: "House", state_district: "FL-07", price_change_pct: 0.9, shares_est: 35, demo: true },
    { id: 9009, ticker: "BAC", asset: "Bank of America", side: "BUY", trade_date: "2026-06-20", filing_date: "2026-07-14", amount: "$1,001 - $15,000", amount_min: 1001, amount_max: 15000, score: 42, tag: "routine", sector: "Financials", politician: "Demo Senate F", party: "R", chamber: "Senate", state_district: "OH", price_change_pct: 0.3, shares_est: 180, demo: true },
    { id: 9010, ticker: "XOM", asset: "Exxon Mobil", side: "BUY", trade_date: "2026-06-18", filing_date: "2026-07-12", amount: "$15,001 - $50,000", amount_min: 15001, amount_max: 50000, score: 70, tag: "noteworthy", sector: "Energy", politician: "Demo Senate D", party: "D", chamber: "Senate", state_district: "NY", price_change_pct: 0.2, shares_est: 300, demo: true }
  ],
  holders: {
    NVDA: {
      ticker: "NVDA", name: "NVIDIA Corp", sector: "Technology",
      unique_politicians: 2, house_count: 1, senate_count: 1, total_trades: 5, total_volume: 250000,
      holders: [
        { name: "Demo Senate D", party: "D", chamber: "Senate", state_district: "NY", trades: 3, buys: 3, sells: 0, volume: 200000, last_side: "BUY", last_date: "2026-07-05", last_score: 88 },
        { name: "Demo House A", party: "D", chamber: "House", state_district: "CA-12", trades: 2, buys: 2, sells: 0, volume: 50000, last_side: "BUY", last_date: "2026-07-18", last_score: 72 }
      ]
    },
    AAPL: {
      ticker: "AAPL", name: "Apple Inc", sector: "Technology",
      unique_politicians: 2, house_count: 1, senate_count: 1, total_trades: 4, total_volume: 180000,
      holders: [
        { name: "Demo Senate B", party: "R", chamber: "Senate", state_district: "TX", trades: 2, buys: 2, sells: 0, volume: 100000, last_side: "BUY", last_date: "2026-07-15", last_score: 45 },
        { name: "Demo House E", party: "D", chamber: "House", state_district: "FL-07", trades: 2, buys: 0, sells: 2, volume: 80000, last_side: "SELL", last_date: "2026-06-25", last_score: 38 }
      ]
    },
    XOM: {
      ticker: "XOM", name: "Exxon Mobil", sector: "Energy",
      unique_politicians: 2, house_count: 1, senate_count: 1, total_trades: 3, total_volume: 120000,
      holders: [
        { name: "Demo House C", party: "R", chamber: "House", state_district: "TX-02", trades: 2, buys: 0, sells: 1, volume: 80000, last_side: "SELL", last_date: "2026-07-10", last_score: 68 },
        { name: "Demo Senate D", party: "D", chamber: "Senate", state_district: "NY", trades: 1, buys: 1, sells: 0, volume: 40000, last_side: "BUY", last_date: "2026-06-18", last_score: 70 }
      ]
    }
  },
  sectors: [
    { sector: "Technology", n: 12 },
    { sector: "Energy", n: 6 },
    { sector: "Financials", n: 6 }
  ],
  sectorDesk: {
    Technology: {
      sector: "Technology", house_count: 2, senate_count: 2, unique_politicians: 4, unique_tickers: 3, total_trades: 12,
      politicians: [
        { name: "Demo Senate D", party: "D", chamber: "Senate", state_district: "NY", trades: 4, volume: 220000, unique_tickers: 2, ticker_list: ["NVDA", "AAPL"] },
        { name: "Demo House A", party: "D", chamber: "House", state_district: "CA-12", trades: 3, volume: 65000, unique_tickers: 2, ticker_list: ["NVDA", "MSFT"] },
        { name: "Demo Senate B", party: "R", chamber: "Senate", state_district: "TX", trades: 2, volume: 100000, unique_tickers: 1, ticker_list: ["AAPL"] },
        { name: "Demo House E", party: "D", chamber: "House", state_district: "FL-07", trades: 2, volume: 80000, unique_tickers: 1, ticker_list: ["AAPL"] }
      ],
      tickers: [
        { ticker: "NVDA", trades: 5, volume: 250000, unique_politicians: 2 },
        { ticker: "AAPL", trades: 4, volume: 180000, unique_politicians: 2 },
        { ticker: "MSFT", trades: 1, volume: 15000, unique_politicians: 1 }
      ]
    },
    Energy: {
      sector: "Energy", house_count: 1, senate_count: 1, unique_politicians: 2, unique_tickers: 2, total_trades: 6,
      politicians: [
        { name: "Demo House C", party: "R", chamber: "House", state_district: "TX-02", trades: 4, volume: 150000, unique_tickers: 2, ticker_list: ["XOM", "CVX"] },
        { name: "Demo Senate D", party: "D", chamber: "Senate", state_district: "NY", trades: 1, volume: 40000, unique_tickers: 1, ticker_list: ["XOM"] }
      ],
      tickers: [
        { ticker: "XOM", trades: 3, volume: 120000, unique_politicians: 2 },
        { ticker: "CVX", trades: 1, volume: 50000, unique_politicians: 1 }
      ]
    },
    Financials: {
      sector: "Financials", house_count: 0, senate_count: 2, unique_politicians: 2, unique_tickers: 2, total_trades: 6,
      politicians: [
        { name: "Demo Senate B", party: "R", chamber: "Senate", state_district: "TX", trades: 2, volume: 50000, unique_tickers: 1, ticker_list: ["JPM"] },
        { name: "Demo Senate F", party: "R", chamber: "Senate", state_district: "OH", trades: 1, volume: 15000, unique_tickers: 1, ticker_list: ["BAC"] }
      ],
      tickers: [
        { ticker: "JPM", trades: 3, volume: 90000, unique_politicians: 1 },
        { ticker: "BAC", trades: 1, volume: 15000, unique_politicians: 1 }
      ]
    }
  },
  politicians: {
    "Demo House A": {
      name: "Demo House A", party: "D", chamber: "House", state_district: "CA-12", trades_total: 5, unique_tickers: 2,
      tickers: [
        { ticker: "NVDA", trades: 2, buys: 2, sells: 0, volume: 50000, sector: "Technology" },
        { ticker: "MSFT", trades: 1, buys: 1, sells: 0, volume: 15000, sector: "Technology" }
      ],
      recent_trades: []
    },
    "Demo Senate B": {
      name: "Demo Senate B", party: "R", chamber: "Senate", state_district: "TX", trades_total: 4, unique_tickers: 2,
      tickers: [
        { ticker: "AAPL", trades: 2, buys: 2, sells: 0, volume: 100000, sector: "Technology" },
        { ticker: "JPM", trades: 2, buys: 2, sells: 0, volume: 50000, sector: "Financials" }
      ],
      recent_trades: []
    },
    "Demo House C": {
      name: "Demo House C", party: "R", chamber: "House", state_district: "TX-02", trades_total: 4, unique_tickers: 2,
      tickers: [
        { ticker: "XOM", trades: 2, buys: 0, sells: 1, volume: 80000, sector: "Energy" },
        { ticker: "CVX", trades: 1, buys: 1, sells: 0, volume: 50000, sector: "Energy" }
      ],
      recent_trades: []
    },
    "Demo Senate D": {
      name: "Demo Senate D", party: "D", chamber: "Senate", state_district: "NY", trades_total: 5, unique_tickers: 2,
      tickers: [
        { ticker: "NVDA", trades: 3, buys: 3, sells: 0, volume: 200000, sector: "Technology" },
        { ticker: "XOM", trades: 1, buys: 1, sells: 0, volume: 40000, sector: "Energy" }
      ],
      recent_trades: []
    }
  }
};
/* backfill recent_trades from wire for demos */
(function () {
  var F = window.GMT_CONGRESS_FIXTURES;
  Object.keys(F.politicians).forEach(function (name) {
    F.politicians[name].recent_trades = F.wire.filter(function (t) { return t.politician === name; });
  });
})();
