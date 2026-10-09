"""
refresh_ranking.py

Run by the "Refresh ranking" GitHub Actions workflow (weekly). Ranks
members of Congress by their average disclosed-purchase performance
(Bargo's `avg_buy_perf_pct`) and writes docs/data/top_30.json, which both
check_trades.py and the dashboard read from.

Resumable: progress is cached in docs/data/_member_profile_cache.json so
a run that hits the daily rate limit partway through finishes on the next
scheduled run instead of starting over.
"""

import json
import os
import time
from pathlib import Path

from bargo_client import list_members, get_member, RateLimitReached

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "docs" / "data"
OUT_PATH = DATA_DIR / "top_30.json"
CACHE_PATH = DATA_DIR / "_member_profile_cache.json"

MIN_TRADES_TO_QUALIFY = int(os.environ.get("MIN_TRADES_TO_QUALIFY", "3"))
MAX_MEMBERS_TO_PROFILE = int(os.environ.get("MAX_MEMBERS_TO_PROFILE", "90"))
TOP_N = int(os.environ.get("TOP_N", "30"))


def load_cache():
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text())
    return {}


def save_cache(cache):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache))


def main():
    print("Fetching member list...")
    members = list_members(limit=500)
    print(f"{len(members)} members total.")

    candidates = [m for m in members if m.get("trades", 0) >= MIN_TRADES_TO_QUALIFY]
    candidates.sort(key=lambda m: m["trades"], reverse=True)
    candidates = candidates[:MAX_MEMBERS_TO_PROFILE]
    print(f"{len(candidates)} candidates with >= {MIN_TRADES_TO_QUALIFY} trades.")

    cache = load_cache()
    profiled = []

    for m in candidates:
        slug = m["member_slug"]
        if slug in cache:
            profiled.append(cache[slug])
            continue
        try:
            detail = get_member(slug)
        except RateLimitReached:
            print("Hit today's rate limit — will finish on the next scheduled run.")
            break
        except Exception as e:
            print(f"Skipping {slug}: {e}")
            continue

        stats = detail.get("stats", {})
        row = {
            "member": detail.get("member"),
            "member_slug": slug,
            "chamber": detail.get("chamber"),
            "state": detail.get("state"),
            "trades": stats.get("trades"),
            "buys": stats.get("buys"),
            "avg_buy_perf_pct": stats.get("avg_buy_perf_pct"),
        }
        cache[slug] = row
        profiled.append(row)
        time.sleep(0.2)

    save_cache(cache)

    ranked = [r for r in profiled if r.get("avg_buy_perf_pct") is not None and r.get("buys", 0) > 0]
    ranked.sort(key=lambda r: r["avg_buy_perf_pct"], reverse=True)
    top = ranked[:TOP_N]

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(top, indent=2))
    print(f"Saved top {len(top)} to {OUT_PATH}")


if __name__ == "__main__":
    main()
