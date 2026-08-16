import httpx

r = httpx.get("http://localhost:8000/api/terminal/congress/returns?mode=member&limit=40", timeout=15)
data = r.json().get("data", {})
print("Scored Trades:", data.get("scored"))
print("Politicians Count:", len(data.get("rows", [])))
print("\nTop 15 Ranked Politicians in ALL MONTHS:")
for i, row in enumerate(data.get("rows", [])[:15], 1):
    print(f" {i:2d}. {row['politician']} ({row.get('party')}): {row['trades']} tx | Avg: {row['avg_return_adj']}% | PnL: ${row['sum_pnl_mid_est']} | Best: {row.get('best_trade', {}).get('ticker')} {row.get('best_trade', {}).get('return_side_adj')}%")
