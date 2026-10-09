"""
check_trades.py

Run by the "Check for new trades" GitHub Actions workflow (every 2 hours
by default). Checks the newest disclosed purchases against your top-30
list, logs a simulated buy for any new one, and sends a phone
notification via ntfy.

Nothing here touches real money — docs/data/portfolio.json is a paper
ledger, committed back to the repo by the workflow so it persists between
runs (Actions runs are stateless containers; the git repo is the state).
"""

import json
import os
from datetime import datetime
from pathlib import Path

import requests

from bargo_client import list_trades, RateLimitReached

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "docs" / "data"
TOP30_PATH = DATA_DIR / "top_30.json"
SEEN_PATH = DATA_DIR / "seen_trades.json"
PORTFOLIO_PATH = DATA_DIR / "portfolio.json"

BUY_AMOUNT_EUR = float(os.environ.get("BUY_AMOUNT_EUR", "50"))
EUR_USD_FALLBACK = float(os.environ.get("EUR_USD_FALLBACK_RATE", "1.08"))
NTFY_TOPIC = os.environ.get("NTFY_TOPIC")


def load_json(path, default):
    if path.exists():
        return json.loads(path.read_text())
    return default


def save_json(path, data):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def get_eur_usd_rate():
    try:
        resp = requests.get("https://api.frankfurter.app/latest",
                             params={"from": "EUR", "to": "USD"}, timeout=10)
        resp.raise_for_status()
        return resp.json()["rates"]["USD"]
    except Exception:
        return EUR_USD_FALLBACK


def send_notification(title, message):
    if not NTFY_TOPIC:
        print("(no NTFY_TOPIC set — skipping notification)")
        return
    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers={"Title": title, "Priority": "default"},
            timeout=10,
        )
    except Exception as e:
        print(f"Notification failed (continuing anyway): {e}")


def trade_id(row):
    return f"{row.get('member_slug')}|{row.get('ticker')}|{row.get('transaction_date')}|{row.get('amount_range')}"


def main():
    if not TOP30_PATH.exists():
        print(f"Missing {TOP30_PATH} — has the ranking workflow run yet? Skipping this run.")
        return
    top30 = json.loads(TOP30_PATH.read_text())
    top30_slugs = {m["member_slug"] for m in top30}

    seen = set(load_json(SEEN_PATH, []))
    portfolio = load_json(PORTFOLIO_PATH, [])

    print("Checking for new disclosed purchases...")
    try:
        page0 = list_trades(type="purchase", limit=100, page=0)
    except RateLimitReached:
        print("Hit today's rate limit before fetching trades. Will try again next run.")
        return

    rows = page0.get("trades", [])
    if page0.get("count", 0) == page0.get("limit", 100):
        try:
            page1 = list_trades(type="purchase", limit=100, page=1)
            rows += page1.get("trades", [])
        except RateLimitReached:
            pass

    new_rows = [r for r in rows if r.get("member_slug") in top30_slugs and trade_id(r) not in seen]

    if not new_rows:
        print("No new qualifying trades this run.")
        return

    eur_usd = get_eur_usd_rate()
    budget_usd = BUY_AMOUNT_EUR * eur_usd

    for row in new_rows:
        price = row.get("recent_price")
        symbol = row.get("ticker")
        if not price or not symbol:
            print(f"Skipping a trade with no usable price/ticker: {row}")
            continue

        shares = budget_usd / price
        portfolio.append({
            "member": row.get("member"),
            "member_slug": row.get("member_slug"),
            "chamber": row.get("chamber"),
            "symbol": symbol,
            "buy_date": datetime.today().strftime("%Y-%m-%d"),
            "disclosed_transaction_date": row.get("transaction_date"),
            "disclosure_date": row.get("disclosure_date"),
            "buy_price_usd": price,
            "shares": shares,
            "cost_eur": BUY_AMOUNT_EUR,
            "cost_usd": budget_usd,
        })

        title = f"{row.get('member')} bought {symbol}"
        message = (
            f"{row.get('chamber')} — disclosed {row.get('disclosure_date')} "
            f"(traded {row.get('transaction_date')}, range {row.get('amount_range')}).\n"
            f"Simulated buy: €{BUY_AMOUNT_EUR:.0f} -> {shares:.4f} shares @ ${price:.2f}"
        )
        print(f"{title}: {message}")
        send_notification(title, message)

        seen.add(trade_id(row))

    save_json(SEEN_PATH, sorted(seen))
    save_json(PORTFOLIO_PATH, portfolio)
    print(f"Logged {len(new_rows)} new simulated buy(s). Portfolio now has {len(portfolio)} position(s).")


if __name__ == "__main__":
    main()
