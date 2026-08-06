# Data definitions — GMT://TERMINAL

## LIVE (yfinance)

| Field / asset | Definition | Source |
|---------------|------------|--------|
| US equities (heatmap) | Daily auto-adjusted OHLCV; last vs prior close for chg% | Yahoo via yfinance |
| AAPL 60 | Last 60 **weekday trading bars** (not calendar days); weekends omitted | AAPL |
| Indices SPX/IXIC/DJI… | Yahoo index symbols (`^GSPC`, `^IXIC`, …) — **levels**, not ETFs | Yahoo |
| SSE | `000001.SS` | Yahoo |
| Gold XAU | `GC=F` COMEX continuous futures | Yahoo |
| Silver XAG | `SI=F` | Yahoo |
| Platinum XPT | `PL=F` | Yahoo |
| Palladium XPD | `PA=F` | Yahoo |
| WTI | `CL=F` | Yahoo |
| DXY | `DX-Y.NYB` | Yahoo |

**Ratios / spreads (metals):** computed only across the same futures-proxy family so Gold/Silver ratio and Gold–Platinum spread stay definitionally consistent. Not LBMA spot.

**Adjustment:** `auto_adjust=True` (splits/dividends folded into price). Disclosed in Inspector / DATA STATUS.

**Currency:** listing currency as labeled (USD for US names; index ccy on tape).

**as-of:** server wall-clock ISO when the payload was built; bar dates are exchange session dates.

## DEMO fixtures

Bundled in `js/data/fixtures.js`, version stamped in `meta.fixturesVersion`. Deterministic, reproducible, **not** random. Every news item has `demo: true` and source `DEMO WIRE`.

## News policy

No fabricated “live” headlines. Without a licensed wire, news remains DEMO-labeled. LIVE mode may still show a single system notice with `demo: true`.

## Session clock

Client-side IANA timezones. States: OPEN / PRE / LUNCH / CLOSED / UNKNOWN. Without a holiday calendar, holidays are never asserted as normal open — UI may show **HOLIDAY STATUS UNVERIFIED**.
