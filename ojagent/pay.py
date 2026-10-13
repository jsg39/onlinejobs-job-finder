"""Turn free-text onlinejobs.ph pay ("$4-9.00/hour", "6-8 Euros per hour", "₱60k/mo")
into an approximate USD/month range so the UI can filter on it.

Rates are rough constants, good enough to filter on and not exact pay. Text with no
period is read by size: under 100 is hourly, otherwise monthly. Per-video or
per-project pay can't become a monthly figure, so it returns None.
"""

from __future__ import annotations

import re

USD_PER = {"USD": 1.0, "EUR": 1.08, "GBP": 1.27, "AUD": 0.66, "CAD": 0.73, "SGD": 0.77, "NZD": 0.6, "PHP": 1 / 58}
WEEKS_PER_MONTH = 52 / 12

_CURRENCY = [
    ("PHP", r"php|₱|peso"),
    ("EUR", r"€|eur(o|os)?\b"),
    ("GBP", r"£|gbp"),
    ("AUD", r"aud|a\$"),
    ("CAD", r"cad|c\$"),
    ("SGD", r"sgd|s\$"),
    ("NZD", r"nzd|nz\$"),
]
_PERIOD = [
    ("project", r"per\s+(video|project|task|article|post|piece|map)|/\s*(video|project)|fixed"),
    ("hour", r"hour|\bhr\b|/\s*h\b|hourly|\bph\b"),
    ("week", r"week|\bwk\b|weekly"),
    ("year", r"year|\byr\b|annual|annum"),
    ("month", r"month|\bmo\b|monthly|/\s*m\b"),
]
_NUMBER = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(k)?\b", re.I)


def _hours_per_week(hours: str | None) -> float:
    if hours:
        nums = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", hours)]
        if nums and 0 < nums[0] <= 80:
            return nums[0]
    return 40.0


def usd_per_month(pay: str | None, hours: str | None = None) -> dict | None:
    """{"min": int, "max": int} in approximate USD per month, or None if unknown."""
    if not pay:
        return None
    text = pay.lower()
    amounts = []
    for num, k in _NUMBER.findall(text):
        value = float(num.replace(",", ""))
        amounts.append(value * 1000 if k else value)
    amounts = [a for a in amounts if a > 0][:2]
    if not amounts:
        return None

    currency = next((c for c, pat in _CURRENCY if re.search(pat, text)), None)
    if currency is None:
        # Unmarked five-figure monthly pay on a Philippine job board is pesos, not dollars.
        currency = "PHP" if max(amounts) >= 10_000 and "$" not in text else "USD"
    period = next((p for p, pat in _PERIOD if re.search(pat, text)), None)
    if period == "project":
        return None
    if period is None:
        period = "hour" if max(amounts) < 100 else "month"

    per_month = {
        "hour": _hours_per_week(hours) * WEEKS_PER_MONTH,
        "week": WEEKS_PER_MONTH,
        "month": 1.0,
        "year": 1 / 12,
    }[period]
    low, high = min(amounts), max(amounts)
    rate = USD_PER[currency] * per_month
    return {"min": round(low * rate), "max": round(high * rate)}
