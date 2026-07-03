"""
FastAPI backend for the Reconciliation Exception Agent POC.

Holds the Lyzr API key (never exposed to the frontend). Endpoints:
  GET  /api/files                 — the day's "received" files + metadata
  GET  /api/file/{name}/preview   — decoded preview (BASE II decoded; XML key-fields; CSV/JSON)
  POST /api/reconcile             — parse + match + compute (deterministic) → call Lyzr → merged result
"""
from __future__ import annotations
import os, json, glob, csv as _csv, sys, re, subprocess, datetime as _dt
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except Exception:
    pass

import recon_core
import lyzr_client
import demo_history

DATA_DIR = os.getenv("DATA_DIR", r"c:\tasks\vss110\data")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN_PATH = os.getenv("GEN_PATH", os.path.join(ROOT, "gen_unrecon_day.py"))
DEMO_AS_OF = os.getenv("DEMO_AS_OF", "").strip()          # pin a date (YYYY-MM-DD) for repeatable demos
AUTO_REGEN = os.getenv("AUTO_REGEN", "1").strip().lower() not in ("0", "false", "no")


def _target_dates():
    """The dates this startup will generate — computed the same way as the generator."""
    asof = _dt.date.fromisoformat(DEMO_AS_OF) if DEMO_AS_OF else _dt.date.today()
    d1 = (asof - _dt.timedelta(days=1)).strftime("%Y%m%d")   # reconciled day
    d2 = asof.strftime("%Y%m%d")                              # catch-up day
    return d1, d2


def _regenerate():
    """On startup, regenerate the dataset for today's date (or DEMO_AS_OF). Numbers are fixed; only
    dates move. Best-effort: on any failure we keep serving whatever data already exists."""
    if not AUTO_REGEN:
        print("[startup] AUTO_REGEN off — serving existing data."); return
    if not os.path.isfile(GEN_PATH):
        print(f"[startup] generator not found at {GEN_PATH} — serving existing data."); return
    cmd = [sys.executable, GEN_PATH, "--out", DATA_DIR] + (["--as-of", DEMO_AS_OF] if DEMO_AS_OF else [])
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        _clear_generated()   # wipe any prior dataset first, so a stale SRE/extension can't linger
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=60)
    except Exception as e:
        print(f"[startup] regenerate failed ({e}) — serving existing data."); return
    d1, _ = _target_dates()
    print(f"[startup] dataset regenerated for D1={d1}" + (f" (pinned DEMO_AS_OF={DEMO_AS_OF})" if DEMO_AS_OF else " (today)"))


def _clear_generated():
    """Remove all previously generated dataset files (any SRE/date) so only the freshly generated set
    remains. Prevents a stale SRE or extension — e.g. after a rename, or in a mounted volume — from
    lingering and making discover() build a path to files that don't exist."""
    prefixes = ("VISA_CLR_", "VISA_SETTLEMENT_NET_", "THREDD_TXN_REPORT_", "clearing_detail_")
    for p in glob.glob(os.path.join(DATA_DIR, "*")):
        if os.path.basename(p).startswith(prefixes):
            try: os.remove(p)
            except OSError: pass


def _ensure_fresh():
    """Regenerate if the on-disk dataset isn't for today's target D1 — keeps a long-running host current
    without a restart. No-op when already current (or AUTO_REGEN off). Called on each data request."""
    if not AUTO_REGEN:
        return
    d1, _ = _target_dates()
    nets = sorted(glob.glob(os.path.join(DATA_DIR, "VISA_SETTLEMENT_NET_*_*.json")))
    current = None
    if nets:
        m = re.search(r"_(\d{8})\.json$", nets[-1])
        current = m.group(1) if m else None
    if current != d1:
        _regenerate()


@asynccontextmanager
async def lifespan(app):
    _regenerate()
    yield


app = FastAPI(title="Reconciliation Exception Agent — POC", version="1.0", lifespan=lifespan)

# CORS — the React frontend is deployed on a different origin (Cloudflare Pages), so the
# browser needs our Access-Control-Allow-Origin header. CORS_ALLOWED_ORIGINS is a
# comma-separated env var (set in backend/.env); the localhost dev hosts are always allowed.
_DEFAULT_FRONTEND = "https://reconciliation-agent-arttechgroup.pages.dev"
_extra_origins = [o.strip() for o in os.getenv("CORS_ALLOWED_ORIGINS", _DEFAULT_FRONTEND).split(",") if o.strip()]
CORS_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"] + _extra_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"], allow_headers=["*"],
)

# ---- file metadata ---------------------------------------------------------
def _meta():
    fp = recon_core.discover(DATA_DIR)
    def info(path, side, kind, day):
        n = 0
        if path.endswith(".itf"):
            n = len(recon_core.parse_visa_baseii(path))
        elif path.endswith(".xml"):
            n = len(recon_core.parse_thredd_xml(path))
        return {"name": os.path.basename(path), "side": side, "kind": kind, "day": day,
                "records": n, "bytes": os.path.getsize(path), "status": "received"}
    return fp, [
        info(fp["visa_nat"],  "Visa",   "National clearing (BASE II — ITF)",      fp["d1"]),
        info(fp["visa_intl"], "Visa",   "International clearing (BASE II — ITF)",  fp["d1"]),
        info(fp["thredd_d1"], "Processor", "Transaction XML report",   fp["d1"]),
        info(fp["thredd_d2"], "Processor", "Transaction XML report",   fp["d2"]),
    ]

@app.get("/")
def health():
    return {"ok": True, "data_dir": DATA_DIR,
            "auto_regen": AUTO_REGEN, "demo_as_of": DEMO_AS_OF or "today",
            "lyzr_configured": bool(lyzr_client.LYZR_API_KEY and lyzr_client.LYZR_AGENT_ID)}

@app.get("/api/files")
def files():
    _ensure_fresh()
    fp, items = _meta()
    with open(fp["visa_net"], encoding="utf-8") as f:
        net = json.load(f)
    return {"reconciled_day": fp["d1"], "catch_up_day": fp["d2"], "sre": fp["sre"],
            "visa_net_settlement": net["net_settlement_gbp"], "files": items}

@app.get("/api/file/{name}/preview")
def preview(name: str):
    name = os.path.basename(name)  # prevent path traversal
    path = os.path.join(DATA_DIR, name)
    if not os.path.isfile(path):
        raise HTTPException(404, f"{name} not found")
    if name.endswith(".itf"):       # Visa BASE II — ITF → decoded rows (never raw-dumped)
        recs = recon_core.parse_visa_baseii(path)
        rows = [{"arn": r["arn"], "merchant": r["merchant"], "region": r["region"],
                 "source_ccy": r["source_ccy"],
                 "source_amount": (float(r["source_amount"]) if r["source_amount"] is not None else None),
                 "settle_gbp": float(r["settle_gbp"]), "conv_rate": (float(r["conv_rate"]) if r["conv_rate"] else None),
                 "isa_gbp": float(r["isa"])} for r in recs]
        with open(path, encoding="utf-8") as f:
            raw = [ln.rstrip("\n") for ln in f][:4]
        return {"type": "baseii", "columns": list(rows[0].keys()) if rows else [], "rows": rows, "raw_sample": raw}
    if name.endswith(".xml"):       # Thredd XML → key-fields table
        recs = recon_core.parse_thredd_xml(path)
        rows = [{"arn": r["arn"], "merchant": r["merchant"], "region": r["region"],
                 "settlement_amt": float(r["settlement_amt"]), "bill_amt": float(r["bill_amt"]),
                 "rate": float(r["rate"]), "settle_date": r["settle_date"],
                 "scheme_settle_date": r["scheme_settle_date"], "isa": float(r["isa"])} for r in recs]
        return {"type": "thredd_xml", "columns": list(rows[0].keys()) if rows else [], "rows": rows}
    if name.endswith(".json"):
        with open(path, encoding="utf-8") as f:
            return {"type": "json", "data": json.load(f)}
    if name.endswith(".csv"):
        with open(path, encoding="utf-8") as f:
            rows = list(_csv.DictReader(f))
        return {"type": "csv", "columns": list(rows[0].keys()) if rows else [], "rows": rows}
    raise HTTPException(415, "unsupported file type")

@app.post("/api/reconcile")
def reconcile():
    _ensure_fresh()
    findings = recon_core.run(DATA_DIR)        # deterministic: the numbers + where the differences are
    agent, agent_error = None, None
    if lyzr_client.is_configured():
        try:
            # The transactions list is for the UI only — strip it so the agent's input (and thus its
            # classification/routing/escalation) stays byte-identical to before this feature.
            agent_input = {k: v for k, v in findings.items() if k not in ("transactions", "transaction_summary")}
            agent = lyzr_client.explain(agent_input)   # the brain: classify / narrate / route
        except Exception as e:
            agent_error = f"Lyzr call failed: {e}"
    return {"findings": findings, "agent": agent,
            "agent_connected": lyzr_client.is_configured(), "agent_error": agent_error}

@app.get("/api/activity")
def activity():
    """Activity Reconciliation overview: recent settlement days per (date × currency).

    Row 0 is today's *real* GBP stream (the deterministic engine's totals) — the one with an
    exception, drilled into on the dashboard. The rest are fabricated reconciled history in other
    settlement currencies (demo_history), so the overview reflects a multi-currency program. Uses
    _ensure_fresh() like the other endpoints, so dates auto-advance; numbers stay fixed."""
    _ensure_fresh()
    findings = recon_core.run(DATA_DIR)
    t, d = findings["totals"], findings["dates"]
    current = {
        "date": d["reconciled_day"], "currency": findings["currency"], "service": "International",
        "net_settlement": t["visa_net_settlement"], "net_processed": t["thredd_day1_sum"],
        "gap": t["raw_difference"], "status": "unreconciled", "real": True,
    }
    return {"days": [current] + demo_history.build_history(d["reconciled_day"])}
