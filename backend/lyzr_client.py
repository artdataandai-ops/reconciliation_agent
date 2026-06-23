"""
lyzr_client — calls the Lyzr agent (the reasoning "brain").

NO fallback: the agent IS the intelligence. If it isn't configured, explain() returns None and the
backend exposes only the deterministic findings (the numbers + where the differences are). The
interpretation — classifying timing / FX / rounding / ISA / true break, the narrative, and the
routing decision — comes solely from the agent.

Agent input  = the backend's structured findings JSON.
Agent output = { headline, steps[], classification[], routing{}, narrative } (strict JSON).
"""
from __future__ import annotations
import os, json

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except Exception:
    pass

LYZR_API_KEY = os.getenv("LYZR_API_KEY", "").strip()
LYZR_AGENT_ID = os.getenv("LYZR_AGENT_ID", "").strip()
LYZR_API_URL = os.getenv("LYZR_API_URL", "https://agent.api.lyzr.app/v2/chat/").strip()
LYZR_USER_ID = os.getenv("LYZR_USER_ID", "recon-poc@thredd.demo").strip()


def is_configured() -> bool:
    return bool(LYZR_API_KEY and LYZR_AGENT_ID)


def explain(findings: dict):
    """Return the Lyzr agent's reasoning, or None if the agent isn't configured.
    No deterministic fallback — without the agent there is no explanation. May raise on
    network/parse errors so the caller can surface them honestly."""
    if not is_configured():
        return None
    return _call_lyzr(findings)


def _call_lyzr(findings: dict) -> dict:
    import requests
    msg = ("Reconcile this Unreconciled Day. Findings JSON follows. Classify every difference, "
           "produce the 5-step explanation, and decide routing. Respond with ONLY the JSON contract. "
           "In timing explanations use each item's actual scheme_settle_date (Visa) and thredd_settle_date "
           "(processor) formatted 'DD Mon YYYY' (e.g. '18 Jun 2026') — never 'Day 1'/'Day 2' or 'the next day'.\n\n"
           + json.dumps(findings))
    r = requests.post(
        LYZR_API_URL,
        headers={"x-api-key": LYZR_API_KEY, "Content-Type": "application/json"},
        json={"user_id": LYZR_USER_ID, "agent_id": LYZR_AGENT_ID,
              "session_id": f"recon-{findings.get('dates', {}).get('reconciled_day', '')}",
              "message": msg},
        timeout=60,
    )
    r.raise_for_status()
    data = r.json()
    resp = data.get("response", data.get("message", data))
    if isinstance(resp, dict):     # Lyzr Structured Output → already a JSON object
        return resp
    text = str(resp).strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(text, strict=False)  # strict=False: tolerate literal newlines/tabs the agent emits inside narrative/explanation strings
