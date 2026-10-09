"""
snapshot_portfolio.py

Run by the "Snapshot portfolio" GitHub Actions workflow (hourly by
default). Prices every symbol currently in docs/data/portfolio.json using
Yahoo Finance (via yfinance — free, no API key, no daily cap that matters
here), computes total invested vs. total current value, and appends one
timestamped row to docs/data/history.json.

This is deliberately a separate script/workflow from check_trades.py so
that frequent price snapshots never eat into the Bargo API's daily
request budget, which is needed for detecting new trades.

docs/data/history.json is a simple growing list — old rows are thinned
out over time (see prune_history) so the file doesn't grow without bound
while still keeping enough resolution for the 1Y/YTD views.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import yfinance as yf

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "docs" / "data"
PORTFOLIO_PATH = DATA_DIR / "portfolio.json"
HISTORY_PATH = DATA_DIR / "history.json"

MAX_ROWS = 6000  # generous headroom; prune_history keeps this file small in practice


def load_json(path, default):
    if path.exists():
        return json.loads(path.read_text())
    return default


def save_json(path, data):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def get_prices(symbols):
    prices = {}
    if not symbols:
        return prices
    try:
        data = yf.download(tickers=list(symbols), period="1d", interval="1m",
                            progress=False, group_by="ticker", threads=True)
        for sym in symbols:
            try:
                if len(symbols) == 1:
                    prices[sym] = float(data["Close"].dropna().iloc[-1])
                else:
                    prices[sym] = float(data[sym]["Close"].dropna().iloc[-1])
            except Exception:
                prices[sym] = None
    except Exception as e:
        print(f"Bulk price fetch failed ({e}); falling back to one-by-one.")
        for sym in symbols:
            try:
                t = yf.Ticker(sym)
                prices[sym] = float(t.fast_info["last_price"])
            except Exception:
                prices[sym] = None
    return prices


def prune_history(history):
    """Keep full resolution for the last 7 days, then thin older rows to
    roughly hourly and, past 90 days, to roughly daily — keeps the chart
    responsive over a year without the file growing forever."""
    if len(history) <= MAX_ROWS:
        return history
    # simple downsample: keep every Nth row beyond the recent window
    recent_cutoff = len(history) - (24 * 7)  # ~last 7 days at hourly cadence
    if recent_cutoff <= 0:
        return history
    older = history[:recent_cutoff]
    recent = history[recent_cutoff:]
    thinned = older[::3]  # keep roughly 1 in 3 of the older rows
    return thinned + recent


def main():
    portfolio = load_json(PORTFOLIO_PATH, [])
    if not portfolio:
        print("Portfolio is empty — nothing to snapshot yet.")
        return

    holdings = {}
    for p in portfolio:
        sym = p["symbol"]
        holdings.setdefault(sym, {"shares": 0.0, "cost_usd": 0.0})
        holdings[sym]["shares"] += p["shares"]
        holdings[sym]["cost_usd"] += p["cost_usd"]

    prices = get_prices(list(holdings.keys()))

    total_cost = 0.0
    total_value = 0.0
    positions = []
    for sym, h in holdings.items():
        price = prices.get(sym)
        value = h["shares"] * price if price else None
        total_cost += h["cost_usd"]
        if value is not None:
            total_value += value
        positions.append({
            "symbol": sym, "shares": h["shares"], "cost_usd": h["cost_usd"],
            "price_usd": price, "value_usd": value,
        })

    history = load_json(HISTORY_PATH, [])
    history.append({
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total_cost_usd": round(total_cost, 2),
        "total_value_usd": round(total_value, 2),
        "positions": positions,
    })
    history = prune_history(history)

    save_json(HISTORY_PATH, history)
    pnl = total_value - total_cost
    pnl_pct = (pnl / total_cost * 100) if total_cost else 0
    print(f"Snapshot saved: value ${total_value:,.2f} / cost ${total_cost:,.2f} "
          f"({pnl_pct:+.2f}%)")


if __name__ == "__main__":
    main()
