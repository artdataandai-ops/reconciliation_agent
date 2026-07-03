# Reconciliation Exception Agent — POC (Thredd ⇄ Visa)

Demonstrates resolving an **"Unreconciled Day"**: a day-wise difference between Visa's net
settlement and the Thredd platform transaction file, explained in seconds and with only genuine
breaks routed to an analyst.

```
  Visa BASE II files (National + International) ┐
  + Visa net settlement (VSS)                  ├─▶  FastAPI backend  ─▶  Lyzr agent  ─▶  React dashboard
  Thredd Transaction XML (Day 1 + Day 2)       ┘    parse · match ARN     classify ·       files · waterfall ·
                                                     · compute (exact)     narrate · route   exceptions · run log
```

- **Backend = deterministic calculator** (numbers always correct). **Lyzr agent = the brain**
  (classifies / explains / routes). **Frontend** talks only to the backend; the **Lyzr key lives in
  the backend**. Files stay in their native formats; the backend converts them.

## Project layout
```
gen_unrecon_day.py        Generates the synthetic dataset (dynamic dates)
data/                     Generated files the backend reads
backend/                  FastAPI: recon_core.py (parse+match+compute), lyzr_client.py, main.py
frontend/                 React (Vite) dashboard — grey/yellow/white
lyzr_agent_prompt.md      Role/Goal/Instructions to paste into Lyzr Studio (the agent's brain)
RECON_SCENARIO_MAP.md     What each file/field is + which ARN = which scenario
SOURCES.md                Authoritative Thredd/Visa references
archive/                  Superseded earlier artifacts
```

## Run it (2 terminals)

**1 — Backend** (http://localhost:8000) — **auto-generates the dataset for today's date on startup**,
so the demo always looks current (numbers are fixed; only the dates move):
```
pip install -r backend/requirements.txt
python -m uvicorn main:app --app-dir backend --port 8000
```

**2 — Frontend** (http://localhost:5173):
```
npm --prefix frontend install
npm --prefix frontend run dev
```
Open http://localhost:5173 → the 4 files show **received** → click **Run reconciliation**.

**Dates / regeneration** (in `backend/.env`):
- `AUTO_REGEN=1` (default) — backend regenerates for **today** each startup. Set `0` to freeze.
- `DEMO_AS_OF=2026-06-18` — pin a date for a repeatable demo (D1 = as-of − 1, D2 = as-of).
- To regenerate manually for a custom date: `python gen_unrecon_day.py --as-of YYYY-MM-DD`.

## Wire the Lyzr agent (required for the explanation — no fallback)
The backend computes the numbers and **locates** the differences; the **Lyzr agent is the only thing
that interprets them** (classify → explain → route). There is **no stub fallback**: with no agent
connected, the dashboard shows the raw gap and *where* the differences are, but **not** the
classification, narrative, or routing. That's deliberate — it makes the agent's value explicit.
1. In **Lyzr Studio → Agent Builder**, create an agent and paste the Role / Goal / Agent Instructions
   from [lyzr_agent_prompt.md](lyzr_agent_prompt.md).
2. Copy `backend/.env.example` → `backend/.env` and set `LYZR_API_KEY` and `LYZR_AGENT_ID`.
3. Restart the backend. `GET /` shows `"lyzr_configured": true`; the dashboard then plays the full
   5-step classification, waterfall, exceptions, and routing.

### Escalation to Jira (agent tool, conditional)
Escalation is an **agent action**, not a backend job. Add a **Jira tool** to the agent in Lyzr Studio
(Composio ready-tool, or a Custom OpenAPI tool over `POST /rest/api/3/issue`) — Jira credentials live
in **Lyzr**, not our backend. Per the prompt, the agent calls it **only when a genuine residual
exists** (never for timing/FX/rounding/ISA), creating one ticket per break and returning
`routing.escalation.tickets[]`. The dashboard then shows **"Escalated → Jira RECON-123 ↗"**; with no
residual (or no tool configured) nothing is shown. See [lyzr_agent_prompt.md](lyzr_agent_prompt.md).

## What the demo shows (numbers tie out exactly)
| Component | Amount | Outcome |
|-----------|-------:|---------|
| Raw unreconciled difference | **£347.33** | Visa net £1,457.94 − Thredd Day-1 £1,110.61 |
| Timing (late posting) | £280.60 | explained — found in next-day file (same ARN) |
| FX rate-timing | £7.29 | explained — txn-date vs settlement-date rate |
| Rounding | −£0.01 | explained — 0.0007%, within 0.01% tolerance |
| Scheme ISA | £4.26 | confirmed equal both sides — not the cause |
| **True break → analyst** | **£59.45** | routed (UBER US TRIP, in Visa, absent from Thredd) |

`£280.60 + £7.29 − £0.01 + £59.45 = £347.33` ✓

## Notes
- All data is **synthetic** (no real PANs). Dates are **dynamic** so the demo always looks current.
- The POC simulates "files received" + a manual **Run**; in production the agent triggers
  automatically when all files land on sFTP.
- BASE II — ITF byte-offsets are *representative* (the exact layout is a proprietary Visa spec); recon
  matches on ARN / amounts / dates, so this doesn't affect results. See [SOURCES.md](SOURCES.md).
