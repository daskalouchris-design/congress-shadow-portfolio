"""
bargo_client.py — shared wrapper around the free Bargo Congress Trades API
(https://www.bargo.ai/free-apis/congress).

In the web-app version, the API key comes from the BARGO_API_KEY
environment variable (set as a GitHub Actions secret) instead of a local
config file — GitHub Actions injects it at run time, it's never committed
to the repo.
"""

import os
import requests

BASE = "https://www.bargo.ai/free-apis/congress/v1"


class RateLimitReached(Exception):
    pass


def _api_key():
    return os.environ.get("BARGO_API_KEY") or None


def _headers():
    key = _api_key()
    return {"X-Api-Key": key} if key else {}


def get(path, params=None):
    resp = requests.get(f"{BASE}{path}", headers=_headers(), params=params or {}, timeout=20)
    if resp.status_code == 429:
        raise RateLimitReached(resp.text)
    resp.raise_for_status()
    return resp.json()


def list_members(limit=500):
    return get("/members", {"limit": limit}).get("members", [])


def get_member(member_slug, trade_limit=1):
    """trade_limit is small by default: this endpoint also returns that
    many of the member's individual trade rows alongside `stats`, and
    each one counts against the daily row budget."""
    return get(f"/members/{member_slug}", {"limit": trade_limit})


def list_trades(**filters):
    """filters: ticker, member, chamber, type, from, to, limit, page"""
    return get("/trades", filters)


def list_trades_for_ticker(ticker, **filters):
    return get(f"/trades/{ticker}", filters)
