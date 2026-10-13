"""Pay text seen on real onlinejobs.ph postings."""

import pytest

from ojagent.pay import usd_per_month

H = 52 / 12  # weeks per month


@pytest.mark.parametrize("text, hours, expected", [
    ("$1,000 – $2,200/month", None, (1000, 2200)),
    ("$1,600", None, (1600, 1600)),
    ("$20/hr", "20", (round(20 * 20 * H), round(20 * 20 * H))),
    ("$4-9.00/hour", None, (round(4 * 40 * H), round(9 * 40 * H))),
    ("$3.75", None, (round(3.75 * 40 * H),) * 2),  # no period, small number: hourly
    ("6-8 Euros per hour", "40", (round(6 * 1.08 * 40 * H), round(8 * 1.08 * 40 * H))),
    ("$1150 AUD per month", None, (round(1150 * 0.66),) * 2),
    ("PHP 60,000/month", None, (round(60000 / 58),) * 2),
    ("₱60k/mo", None, (round(60000 / 58),) * 2),
    ("$520 - $693 per month", None, (520, 693)),
    ("$60,000/year", None, (5000, 5000)),
    ("$500/week", None, (round(500 * H),) * 2),
    ("49,000 per Month", None, (round(49000 / 58),) * 2),  # unmarked large amount: PHP
    ("8 SGD/hour", "40", (round(8 * 0.77 * 40 * H),) * 2),
    ("$60,000 per year", None, (5000, 5000)),  # dollar sign wins over the PHP guess
])
def test_known_formats(text, hours, expected):
    assert tuple(usd_per_month(text, hours).values()) == expected


@pytest.mark.parametrize("text", [
    None, "", "Negotiable (Depending on Experience)", "TBD", "N/A",
    "$50–90 per video (up to $150 for high-end)", "$30CAD per map",
])
def test_unknown_or_per_project_pay(text):
    assert usd_per_month(text) is None
