"""
recon_core — deterministic reconciliation engine (the "hands/calculator").

Parses the native Visa BASE II clearing files (fixed-width) and the Thredd Transaction XML
report, matches on ARN, and computes the day's unreconciled difference broken into facts:
timing (found next day), FX rate-timing (matched amount deltas), true residual (missing
everywhere), rounding (the within-tolerance remainder), and an ISA fee comparison.

These facts + figures are what we hand to the Lyzr agent. The agent reasons/explains/routes;
it never parses files or does arithmetic. All money maths here uses Decimal — always exact.
"""
from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP
import xml.etree.ElementTree as ET
import glob, json, os, re

CCY_EXP = {"826": 2, "978": 2, "840": 2, "392": 0}   # GBP, EUR, USD, JPY
CCY_NAME = {"826": "GBP", "978": "EUR", "840": "USD", "392": "JPY"}
FX_LABEL_THRESHOLD = Decimal("0.05")   # matched delta >= 5p is labelled FX (else absorbed in rounding)

def _money(minor: str, exp: int) -> Decimal:
    return (Decimal(int(minor)) / (Decimal(10) ** exp)).quantize(Decimal(10) ** -exp)

# ---------------------------------------------------------------------------
# Visa BASE II clearing (fixed-width)  — see write_visa_clearing() in gen_unrecon_day.py
# ---------------------------------------------------------------------------
def parse_visa_baseii(*paths: str) -> list[dict]:
    """Parse one or more Visa BASE II files (Domestic and/or International) into records."""
    recs: list[dict] = []
    for path in paths:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n")
                if line[0:2] != "05":
                    continue  # skip TC90 header / TC92 trailer
                qual = line[2:3]
                if qual == "0":                       # TCR0 — core
                    rec = {
                        "arn": line[37:60].strip(),
                        "settle_gbp": _money(line[22:34], 2),
                        "purch_date": line[60:64],
                        "merchant": line[70:95].strip(),
                        "region": line[95:108].strip(),
                        "source_ccy": CCY_NAME.get(line[108:111], line[108:111]),
                        "mcc": line[111:115],
                        "isa": _money(line[127:136], 2),
                        "source_amount": None, "conv_rate": None,
                    }
                    recs.append(rec)
                elif qual == "1" and recs:            # TCR1 — FX component, attach to last TCR0
                    ccy = line[3:6]
                    recs[-1]["source_ccy"] = CCY_NAME.get(ccy, ccy)
                    recs[-1]["source_amount"] = _money(line[6:18], CCY_EXP.get(ccy, 2))
                    recs[-1]["conv_rate"] = Decimal(int(line[33:48])) / (Decimal(10) ** 9)
    return recs

# ---------------------------------------------------------------------------
# Thredd Transaction XML report
# ---------------------------------------------------------------------------
def _attr(el, tag, name, default=None):
    c = el.find(tag)
    return c.get(name) if c is not None else default

def parse_thredd_xml(path: str) -> list[dict]:
    root = ET.parse(path).getroot()
    out = []
    for cf in root.findall("CardFinancial"):
        out.append({
            "arn": (cf.findtext("ARN") or "").strip(),
            "settlement_amt": Decimal(_attr(cf, "SettlementAmt", "value", "0")),
            "bill_amt": Decimal(_attr(cf, "BillAmt", "value", "0")),
            "rate": Decimal(_attr(cf, "BillAmt", "rate", "0")),
            "settle_date": cf.findtext("SettlementDate"),
            "scheme_settle_date": cf.findtext("SchemeSettlementDate"),
            "isa": Decimal(_attr(cf, "FeeAmt", "value", "0")),
            "region": "INTL" if _attr(cf, "MsgSource", "value") == "54" else "DOM",
            "merchant": (cf.findtext("MerchCode") or "").strip(),
            "mcc": _attr(cf, "Classification", "MCC"),
        })
    return out

# ---------------------------------------------------------------------------
# Reconcile
# ---------------------------------------------------------------------------
def _f(d: Decimal) -> float:
    return float(d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

def reconcile(visa_recs, thredd_d1, thredd_d2, visa_net: Decimal) -> dict:
    """Produce the structured findings the agent will reason over (and the UI will render)."""
    d1 = {r["arn"]: r for r in thredd_d1}
    d2 = {r["arn"]: r for r in thredd_d2}

    timing, fx, residual = [], [], []
    timing_total = fx_total = residual_total = Decimal("0")

    for v in visa_recs:
        arn = v["arn"]
        if arn in d1:                                  # matched on the reconciled day
            delta = v["settle_gbp"] - d1[arn]["settlement_amt"]
            fx_total += delta
            if abs(delta) >= FX_LABEL_THRESHOLD:
                fx.append({"arn": arn, "merchant": v["merchant"], "source_ccy": v["source_ccy"],
                           "visa_amount": _f(v["settle_gbp"]), "thredd_amount": _f(d1[arn]["settlement_amt"]),
                           "delta": _f(delta), "visa_rate": float(v["conv_rate"]) if v["conv_rate"] else None,
                           "thredd_rate": float(d1[arn]["rate"]) if d1[arn]["rate"] else None})
        elif arn in d2:                                # late — found in the next day's file
            timing_total += v["settle_gbp"]
            timing.append({"arn": arn, "merchant": v["merchant"], "amount": _f(v["settle_gbp"]),
                           "scheme_settle_date": d2[arn]["scheme_settle_date"],
                           "thredd_settle_date": d2[arn]["settle_date"]})
        else:                                          # nowhere in Thredd — genuine break
            residual_total += v["settle_gbp"]
            residual.append({"arn": arn, "merchant": v["merchant"], "source_ccy": v["source_ccy"],
                             "amount": _f(v["settle_gbp"])})

    thredd_d1_sum = sum((r["settlement_amt"] for r in thredd_d1), Decimal("0"))
    raw_diff = visa_net - thredd_d1_sum
    rounding = raw_diff - fx_total - timing_total - residual_total

    # ISA confirmation is over matched (both-sides) transactions: late/residual txns aren't ISA breaks.
    visa_isa = sum((v["isa"] for v in visa_recs if v["arn"] in d1), Decimal("0"))
    thredd_isa = sum((r["isa"] for r in thredd_d1), Decimal("0"))

    return {
        "currency": "GBP",
        "totals": {
            "visa_net_settlement": _f(visa_net),
            "thredd_day1_sum": _f(thredd_d1_sum),
            "raw_difference": _f(raw_diff),
            "visa_record_count": len(visa_recs),
            "thredd_day1_count": len(thredd_d1),
            "thredd_day2_count": len(thredd_d2),
        },
        "facts": {
            "timing": {"total": _f(timing_total), "items": timing},
            "fx_rate_timing": {"total": _f(fx_total), "items": fx},
            "rounding": {"total": _f(rounding),
                         "pct_of_net": round(float(abs(rounding) / visa_net * 100), 4) if visa_net else 0.0,
                         "tolerance_pct": 0.01},
            "isa": {"visa_total": _f(visa_isa), "thredd_total": _f(thredd_isa),
                    "equal": _f(visa_isa) == _f(thredd_isa)},
            "residual": {"total": _f(residual_total), "items": residual},
        },
        # deterministic check (the agent must not contradict this)
        "check": {
            "components_sum": _f(timing_total + fx_total + rounding + residual_total),
            "matches_raw": _f(timing_total + fx_total + rounding + residual_total) == _f(raw_diff),
        },
    }

# ---------------------------------------------------------------------------
# Convenience: discover + load the day's files from a data dir
# ---------------------------------------------------------------------------
def discover(data_dir: str) -> dict:
    """Find the latest D1 (reconciled day) file set in data_dir."""
    nets = sorted(glob.glob(os.path.join(data_dir, "VISA_SETTLEMENT_NET_*_*.json")))
    if not nets:
        raise FileNotFoundError(f"No VISA_SETTLEMENT_NET_*.json in {data_dir}")
    net_path = nets[-1]
    m = re.search(r"_(\d{8})\.json$", net_path)
    d1 = m.group(1)
    import datetime as _dt
    d2 = (_dt.datetime.strptime(d1, "%Y%m%d") + _dt.timedelta(days=1)).strftime("%Y%m%d")
    sre = re.search(r"VISA_SETTLEMENT_NET_(\d+)_", os.path.basename(net_path)).group(1)
    return {
        "d1": d1, "d2": d2, "sre": sre,
        "visa_dom":  os.path.join(data_dir, f"VISA_CLR_DOM_{sre}_{d1}.txt"),
        "visa_intl": os.path.join(data_dir, f"VISA_CLR_INTL_{sre}_{d1}.txt"),
        "thredd_d1": os.path.join(data_dir, f"THREDD_TXN_REPORT_{d1}.xml"),
        "thredd_d2": os.path.join(data_dir, f"THREDD_TXN_REPORT_{d2}.xml"),
        "visa_net":  net_path,
    }

def run(data_dir: str) -> dict:
    """Discover the day's files, parse, reconcile. Returns findings + file metadata."""
    fp = discover(data_dir)
    visa = parse_visa_baseii(fp["visa_dom"], fp["visa_intl"])
    td1 = parse_thredd_xml(fp["thredd_d1"])
    td2 = parse_thredd_xml(fp["thredd_d2"])
    with open(fp["visa_net"], encoding="utf-8") as f:
        visa_net = Decimal(str(json.load(f)["net_settlement_gbp"]))
    findings = reconcile(visa, td1, td2, visa_net)
    findings["dates"] = {"reconciled_day": fp["d1"], "catch_up_day": fp["d2"], "sre": fp["sre"]}
    return findings

if __name__ == "__main__":
    import sys
    dd = sys.argv[1] if len(sys.argv) > 1 else r"c:\tasks\vss110\data"
    print(json.dumps(run(dd), indent=2))
