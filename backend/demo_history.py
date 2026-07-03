"""
demo_history — fabricated multi-currency reconciled settlement history for the
Activity Reconciliation overview.

This is DEMO FILLER, not the real engine. recon_core.py performs the real (GBP)
reconciliation from actual Visa/Thredd files; this module just produces plausible,
already-reconciled prior settlement days in several currencies so the overview
reflects a multi-currency program (Visa nets each settlement currency separately
per day). It reinforces the "why is only GBP live?" story: every currency
reconciles daily, and a currency only needs the agent when it has an exception —
today only the GBP stream does; the rest auto-clear.

The numbers are FIXED (a hand-authored template); only the DATES roll — the same
"numbers fixed, dates move" trick gen_unrecon_day.py uses. build_history() stamps
the template onto consecutive calendar days counting back from the reconciled day,
so the overview is a contiguous run of settlement dates ending at "today". Each
row's net_settlement/net_processed is DERIVED from the sum of its transactions, so
the overview figure always ties to the drill-down list; gap is 0 (reconciled).
"""
from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP
import datetime as _dt

ACQ_BIN = "422050"

# Fixed template of reconciled settlement streams:
#   (day_offset_from_reconciled_day, currency, service, [(merchant, amount), ...])
# day_offset 0 = the current settlement day (siblings of the real GBP row, which is
# added separately in main.py); 1..9 = the prior consecutive days. A few dates carry
# 2 currency rows for the screenshot's multi-currency look, but offsets 0..9 are all
# present, so the date backbone is 10 consecutive days.
_TEMPLATE = [
    # --- today (offset 0): other settlement currencies that reconciled clean ---
    (0, "EUR", "International", [
        ("ZARA MADRID", 84.33), ("FNAC PARIS", 212.40), ("LIDL DUBLIN", 33.33),
        ("CARREFOUR LYON", 127.49), ("MEDIAMARKT KOLN", 259.90),
    ]),
    (0, "USD", "International", [
        ("BEST BUY NYC", 198.15), ("APPLE STORE SF", 402.50), ("TARGET CHICAGO", 76.20),
        ("WALMART DALLAS", 143.90), ("AMAZON US MP", 259.99),
    ]),
    # --- prior consecutive days (offsets 1..9) ---
    (1, "AUD", "National", [
        ("WOOLWORTHS SYDNEY", 8820.10), ("COLES MELBOURNE", 5443.30),
        ("QANTAS DOM FLIGHT", 32000.00), ("BUNNINGS PERTH", 9964.03),
    ]),
    (1, "GBP", "International", [
        ("TESCO STORES 2245", 45.00), ("ARGOS RETAIL 0098", 120.50), ("JOHN LEWIS 0031", 230.00),
        ("PRET A MANGER 88", 15.75), ("SAINSBURYS 1190", 67.20), ("GREGGS 1042", 8.99),
    ]),
    (2, "NZD", "International", [
        ("COUNTDOWN AUCKLAND", 61.20), ("KMART WELLINGTON", 45.10),
        ("AIR NZ DOMESTIC", 210.46), ("NOEL LEEMING", 144.00),
    ]),
    (3, "USD", "International", [
        ("STARBUCKS SEATTLE", 18.75), ("DELTA AIR LINES", 512.30), ("MACYS NYC", 143.90),
        ("WHOLE FOODS AUSTIN", 87.20), ("HOME DEPOT MIAMI", 219.55),
    ]),
    (3, "SGD", "International", [
        ("NTUC FAIRPRICE SG", 32.80), ("CHANGI DUTY FREE", 148.90),
        ("GRAB SINGAPORE", 24.15), ("SHENG SIONG", 61.05),
    ]),
    (4, "EUR", "International", [
        ("IKEA STOCKHOLM", 340.00), ("BOOKING COM AMS", 89.90), ("ZALANDO DE", 117.47),
    ]),
    (5, "AUD", "National", [
        ("MYER BRISBANE", 8175.40), ("JB HI-FI ADELAIDE", 6299.00),
    ]),
    (6, "USD", "International", [
        ("WALGREENS LA", 44.20), ("COSTCO SAN DIEGO", 289.99), ("LYFT SF", 27.50),
    ]),
    (7, "EUR", "International", [
        ("CARREFOUR NICE", 88.10), ("SEPHORA PARIS", 129.37),
    ]),
    (7, "GBP", "International", [
        ("TESCO EXPRESS 4471", 22.40), ("WAITROSE 0210", 95.07),
    ]),
    (8, "NZD", "International", [
        ("PAK N SAVE", 78.20), ("THE WAREHOUSE", 39.56),
    ]),
    (9, "AUD", "National", [
        ("WESTFIELD SYDNEY", 8060.78),
    ]),
]


def _arn(n: int) -> str:
    """An ARN in the same shape gen_unrecon_day.py emits (distinct range → no collision)."""
    return f"7{ACQ_BIN}5101{n:010d}00"[:23].ljust(23, "0")


def build_history(reconciled_day: str, days: int = 10) -> list[dict]:
    """Reconciled multi-currency rows for the days before `reconciled_day`, newest first.

    `reconciled_day` is YYYYMMDD (the current settlement day). Dates roll with it, so the
    whole ladder advances one day whenever the dataset regenerates for a new "today".
    """
    base = _dt.datetime.strptime(reconciled_day, "%Y%m%d")
    out: list[dict] = []
    counter = 0
    for offset, ccy, service, items in _TEMPLATE:
        date = (base - _dt.timedelta(days=offset)).strftime("%Y%m%d")
        region = "INTL" if service == "International" else "NAT"
        txns = []
        total = Decimal("0")
        for merch, amt in items:
            counter += 1
            d = Decimal(str(amt))
            total += d
            txns.append({
                "arn": _arn(9000 + counter),
                "merchant": merch,
                "source_ccy": ccy,
                "region": region,
                "visa_amount": float(d),
                "thredd_amount": float(d),   # reconciled → both sides equal, gap 0
                "gap": 0.0,
                "status": "matched",
            })
        net = float(total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        out.append({
            "date": date, "currency": ccy, "service": service,
            "net_settlement": net, "net_processed": net, "gap": 0.0,
            "status": "reconciled", "real": False, "transactions": txns,
        })
    # newest first (smallest offset first) — already in that order, but be explicit
    out.sort(key=lambda r: r["date"], reverse=True)
    return out
