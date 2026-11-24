"""
Market price insight helpers for KisanSetu AI.

Data source: Agmarknet daily mandi prices via data.gov.in
Set your free API key as an environment variable:
    Windows (cmd):  set DATA_GOV_API_KEY=your_key_here
    Mac/Linux:      export DATA_GOV_API_KEY=your_key_here

Mandi prices are in Rs per quintal (100 kg).
"""

import os
import time
import requests

from database.database import get_db_connection

# Resource id of "Current daily price of various commodities from
# various markets (Mandi)" - please confirm on data.gov.in
RESOURCE_ID = "9ef84268-d588-465a-a308-a864a43d0070"
API_URL = f"https://api.data.gov.in/resource/{RESOURCE_ID}"

CACHE_TTL_SECONDS = 6 * 60 * 60  # refresh at most every 6 hours
_cache = {}


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

SAMPLE_BASE_PRICES = {
    "wheat": 2400,
    "rice": 3100,
    "tomato": 1800,
    "onion": 1500,
    "potato": 1200,
    "maize": 2100,
}


def _sample_rows(commodity, state):
    """Demo prices, used only when the live API does not answer."""
    base = SAMPLE_BASE_PRICES.get(commodity.lower(), 2000)
    markets = [
        ("Karnal", 1.04), ("Ambala", 1.02), ("Hisar", 1.00),
        ("Rohtak", 0.98), ("Kurukshetra", 0.96),
    ]
    rows = []
    for name, factor in markets:
        modal = round(base * factor)
        rows.append({
            "state": state or "Haryana",
            "district": name,
            "market": name,
            "variety": "Sample",
            "date": "SAMPLE DATA (live API is slow)",
            "min": round(modal * 0.95),
            "max": round(modal * 1.05),
            "modal": modal,
        })
    return rows


def fetch_mandi_prices(commodity, state=None):
    """Return a list of mandi price rows for a commodity (cached)."""
    api_key = os.environ.get("DATA_GOV_API_KEY")
    if not api_key:
        raise RuntimeError("DATA_GOV_API_KEY is not set.")

    cache_key = (commodity.lower(), (state or "").lower())
    cached = _cache.get(cache_key)
    if cached and time.time() - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]

    params = {
        "api-key": api_key,
        "format": "json",
        "limit": 100,
        "filters[commodity]": commodity,
    }
    if state:
        params["filters[state]"] = state

    try:
        response = requests.get(API_URL, params=params, timeout=(5, 15))
        response.raise_for_status()
    except requests.exceptions.RequestException:
        return _sample_rows(commodity, state)

    rows = []
    for record in response.json().get("records", []):
        modal = _to_float(record.get("modal_price"))
        if modal is None:
            continue
        rows.append({
            "state": record.get("state"),
            "district": record.get("district"),
            "market": record.get("market"),
            "variety": record.get("variety"),
            "date": record.get("arrival_date"),
            "min": _to_float(record.get("min_price")),
            "max": _to_float(record.get("max_price")),
            "modal": modal,
        })

    _cache[cache_key] = (time.time(), rows)
    return rows


def build_insight(rows):
    """Turn raw rows into simple numbers a farmer can read."""
    if not rows:
        return None

    modal_prices = [r["modal"] for r in rows]
    best_markets = sorted(rows, key=lambda r: r["modal"], reverse=True)[:5]

    return {
        "average": round(sum(modal_prices) / len(modal_prices), 2),
        "lowest": min(modal_prices),
        "highest": max(modal_prices),
        "market_count": len(rows),
        "date": rows[0]["date"],
        "best_markets": best_markets,
    }


def marketplace_average(crop_name):
    """Average price farmers have listed for this crop on KisanSetu."""
    connection = get_db_connection()
    try:
        row = connection.execute(
            """
            SELECT AVG(price) AS avg_price, COUNT(*) AS listings
            FROM products
            WHERE LOWER(crop_name) = LOWER(?)
            """,
            (crop_name,),
        ).fetchone()
    finally:
        connection.close()

    if row is None or row["listings"] == 0:
        return None

    return {
        "average": round(row["avg_price"], 2),
        "listings": row["listings"],
    }
