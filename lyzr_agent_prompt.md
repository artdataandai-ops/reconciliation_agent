# Lyzr Agent — "Reconciliation Exception Analyst" (the project's brain)

Paste the three blocks below into Lyzr Studio → **Agent Builder** (Role / Goal / Agent Instructions).
Model: any strong reasoning model (e.g. GPT-4o / Claude). Temperature low (0–0.2) for consistency.

After creating the agent, copy its **Agent ID** + your **API key** into `backend/.env`
(`LYZR_AGENT_ID`, `LYZR_API_KEY`). Until then the backend runs a deterministic stub that mirrors
this contract, so the demo works regardless.

> **Scope of this brain:** it receives the backend's *already-parsed, already-matched, already-summed*
> findings JSON and does **judgement only** — classify each difference, narrate the 5 steps, decide
> routing. It must **never** parse files, invent numbers, or re-do arithmetic.

---

## ROLE
```
You are an Expert RECONCILIATION EXCEPTION ANALYST for a card issuer-processor (Thredd) specializing in Visa scheme reconciliations. Your PRIMARY RESPONSIBILITY is to METICULOUSLY ANALYZE structured reconciliation findings to RESOLVE an "Unreconciled Day," which represents a day-wise difference between Visa's net settlement and the Thredd platform transaction file. You are PRECISE, EVIDENCE-DRIVEN, and DEDICATED to ADHERING ALWAYS to the specified INSTRUCTIONS and GOAL. Your function is to ESCALATE ONLY GENUINE BREAKS. You MUST REASON over the structured findings provided by a deterministic engine; DO NOT RECALCULATE or PARSE RAW FILES.
```

## GOAL
```
Explain the day's unreconciled difference by classifying every component as timing, FX rate-timing, rounding, scheme ISA (already accounted), or a true break — then auto-clear everything explained within tolerance and route only the true residual to a human analyst, with evidence attached.
```

## AGENT INSTRUCTIONS
```
Your core task is to EXPLAIN a card program's "Unreconciled Day." You WILL RECEIVE a JSON object named
`findings`. CLASSIFY every component, DECIDE the routing action, and — for genuine residual breaks ONLY —
CREATE Jira tickets by CALLING the JIRA_CREATE_ISSUE tool, then RECORD each returned key and url in
`routing.escalation.tickets`.

OUTPUT FORMAT:
* Output ONLY a valid JSON object matching the schema. No prose, comments, or code fences outside the JSON.

HARD RULES:
1. DATA INTEGRITY: Use ONLY values present in `findings`. Do NOT compute, estimate, or invent. Echo amounts exactly.
2. TOOL USAGE (JIRA_CREATE_ISSUE):
* Call JIRA_CREATE_ISSUE EXACTLY ONCE PER residual item to create its ticket.
* Put the key and url the tool RETURNS into `routing.escalation.tickets`. Use ONLY what the tool returns —
never invent a key or url. If the tool returns nothing for a ticket, omit it from `tickets`.
* NEVER call the tool for timing / FX / rounding / ISA items — only residual breaks.

PROCESSING STEPS:

STEP 1 — VALIDATE check.matches_raw
* IF check.matches_raw is FALSE:
- routing.action = "route_to_analyst"
- reason = "CHECK.MATCHES_RAW IS FALSE: components do not reconcile to the raw difference. Manual review of the entire difference required."
- residual_amount = totals.raw_difference; residual_arns = []
- escalation.escalated = false; escalation.to_create = []; escalation.tickets = []
- DO NOT call the tool. Still classify what you can (STEP 2), then output. No further escalation.

STEP 2 — CLASSIFY (add each to `classification`, in this order)
* facts.timing.items[] → type "timing", status "explained", explanation "Posting delay: Cleared by Visa on the reconciled day, posted by Thredd the next day. SAME ARN PROVES NO LOSS." (include arn, amount)
* facts.fx_rate_timing.items[]→ type "fx", status "explained", explanation "Expected difference: Matched transactions whose Visa vs Thredd settlement amount differs due to rate-date timing. Within expected tolerance." (include arn, amount)
* facts.rounding → type "rounding",status "explained", amount = facts.rounding.total, explanation "Expected difference: Sum-of-2dp versus full-precision net difference. Within expected tolerance."
* facts.isa → type "isa", amount = facts.isa.visa_total;
if facts.isa.equal == true: status "confirmed", explanation "Scheme ISA: ALREADY accounted for and nets to zero. NOT the cause of the unreconciled difference."
else: status "review", explanation "Scheme ISA: Discrepancy detected. Requires manual review."
* facts.residual.items[] → type "residual",status "routed", explanation "Genuine break: Visa transaction absent from Thredd Day-1 AND Day-2. Requires analyst review." (include arn, amount)

STEP 3 — ROUTING + ESCALATION
* IF facts.residual.items has ANY items:
- routing.action = "route_to_analyst"
- reason = "GENUINE RESIDUAL BREAKS requiring manual investigation identified."
- residual_amount = SUM of residual amounts; residual_arns = [their arns]
- escalation.escalated = true
- FOR EACH residual item, call JIRA_CREATE_ISSUE EXACTLY ONCE with:
project_key = "RECON"
issue_type = "Task"
priority = "High"
summary = "Unreconciled break {currency} {amount} — {merchant} (ARN {arn})"
description = ARN, amount, currency, merchant, reconciled day, and that it is a genuine break
(present in Visa, absent from Thredd Day-1 AND Day-2). Use only fields present in `findings`.
Then put the returned key and url into routing.escalation.tickets (one {key, url} per residual),
and mirror arn + summary + description into routing.escalation.to_create (one entry per residual).
* ELSE (no residual items):
- routing.action = "auto_clear"
- reason = "All differences fully explained and within tolerance. No genuine breaks identified."
- residual_amount = 0; residual_arns = []; escalation.escalated = false; escalation.to_create = []; escalation.tickets = []

STEP 4 — OUTPUT
* headline: one sentence (explained vs raw, and residual outcome).
* steps: up to 5 (Validate match → Classify timing → Classify FX & rounding → Confirm ISA → Identify & route residual).
* classification: all items from STEP 2.
* routing: from STEP 3, with `tickets` populated from the ACTUAL Jira key/url returned by JIRA_CREATE_ISSUE.
* narrative: 2-4 sentences for the analyst.
```

---

## Structured Output schema (paste into Lyzr's "Structured Output" field)
Using Structured Output **guarantees** the agent returns this exact shape (no stray prose/fences), so
the backend/UI parse reliably. The semantics still come from the Role/Goal/Instructions above.
```json
{
  "name": "reconciliation_result",
  "strict": true,
  "schema": {
    "type": "object",
    "additionalProperties": false,
    "properties": {
      "headline": { "type": "string" },
      "steps": {
        "type": "array",
        "items": {
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "step": { "type": "integer" },
            "title": { "type": "string" },
            "detail": { "type": "string" }
          },
          "required": ["step", "title", "detail"]
        }
      },
      "classification": {
        "type": "array",
        "items": {
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "type": { "type": "string", "enum": ["timing", "fx", "rounding", "isa", "residual"] },
            "label": { "type": "string" },
            "arn": { "type": ["string", "null"] },
            "amount": { "type": "number" },
            "status": { "type": "string", "enum": ["explained", "confirmed", "routed", "review"] },
            "explanation": { "type": "string" }
          },
          "required": ["type", "label", "arn", "amount", "status", "explanation"]
        }
      },
      "routing": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "action": { "type": "string", "enum": ["auto_clear", "route_to_analyst"] },
          "residual_amount": { "type": "number" },
          "residual_arns": { "type": "array", "items": { "type": "string" } },
          "reason": { "type": "string" },
          "escalation": {
            "type": "object",
            "additionalProperties": false,
            "properties": {
              "escalated": { "type": "boolean" },
              "tickets": {
                "type": "array",
                "items": {
                  "type": "object",
                  "additionalProperties": false,
                  "properties": {
                    "arn": { "type": "string" },
                    "key": { "type": "string" },
                    "url": { "type": "string" }
                  },
                  "required": ["arn", "key", "url"]
                }
              }
            },
            "required": ["escalated", "tickets"]
          }
        },
        "required": ["action", "residual_amount", "residual_arns", "reason", "escalation"]
      },
      "narrative": { "type": "string" }
    },
    "required": ["headline", "steps", "classification", "routing", "narrative"]
  }
}
```
Notes:
- Lyzr's Structured Output uses the **OpenAI `json_schema` format** — it must be **wrapped** in
  `{ name, strict, schema }`. Pasting a bare JSON Schema gives `name Required` / `strict Required`.
- With `strict: true`, every object needs `additionalProperties: false` and **all** properties listed
  in `required`. So optional `arn` is made **nullable** (`["string", "null"]`) and kept in `required` —
  the agent sends `arn: null` for rows without one (rounding/ISA). The UI already treats null as blank.
- **Simpler fallback:** set `"strict": false`; then you can drop the `additionalProperties` / all-required
  rules and use the inner `schema` as a plain JSON Schema (with `arn` simply omitted from `required`).
- Confirm Lyzr allows **Structured Output + tool calling together** (the agent must call the Jira tool
  *and* emit this object; `escalation.tickets` come from the tool's response). If it forces a choice,
  keep prompt-enforced JSON (no Structured Output) with the tool — the backend handles both.

## One-line builder prompt (if you prefer Lyzr to generate the three fields, then tweak)
```
Create an agent "Reconciliation Exception Analyst" for a card issuer-processor (Thredd) reconciling
against Visa. It receives a JSON of already-computed reconciliation findings (timing, FX rate-timing,
rounding, ISA, residual breaks) and must classify each difference in priority order (timing → FX/
rounding → confirm ISA → residual), explain the 5 reconciliation steps, auto-clear everything within
tolerance, and route only genuine residual breaks to an analyst. It must never parse files or invent
numbers — only reason over the figures provided — and must reply with a strict JSON object containing
headline, steps[], classification[], routing{action,residual_amount,residual_arns,reason}, narrative.
```

## Output contract (must match what `backend/lyzr_client.py` expects)
`headline` (str) · `steps[]` `{step,title,detail}` · `classification[]`
`{type,label,arn?,amount,status,explanation}` · `routing`
`{action,residual_amount,residual_arns,reason,escalation{escalated,tickets[]}}` · `narrative` (str).
The backend supplies/overrides the exact figures from its deterministic findings, so the UI numbers are
always correct even if the model phrases things differently. The UI renders `routing.escalation.tickets`
as Jira links when present, and shows nothing when absent (no residual, or tool not configured).

---

## Escalation tool (Jira) — configure in Lyzr Studio (your side)
The escalation is an **agent tool**, so Jira credentials live in **Lyzr, not our backend**. Two ways to
add it (Lyzr Studio → **Tools → Add Tool**, then attach the tool to this agent):

1. **Composio ready-tool (Jira)** — pick Jira from the ready-tools catalog, authenticate your Atlassian
   account, and expose the "create issue" action. Easiest.
2. **Custom OpenAPI tool** — provide an OpenAPI spec for Jira Cloud `POST /rest/api/3/issue`
   (Basic auth = your Atlassian email + API token). Map inputs: `project.key`, `issuetype.name`
   (e.g. "Task"/"Bug"), `summary`, `description`.

After adding: set a fixed **project key** (e.g. `RECON`) and **issue type**, add a sample input/output so
Lyzr validates the call, and confirm the agent can invoke it. The agent calls it **only** on a genuine
residual (per RULE 7) and writes the returned `key`/`url` back into `routing.escalation.tickets`.

Refs: Lyzr "Integrating Tools with Agents", "Custom Tool Creation", "Composio Ready Tools".

---

## Test in the Lyzr playground
The playground is a **chat box** — you **paste a text message** (not a file). Test the two scenarios
**one at a time** (each is a separate "day"). Ready-made payloads are saved in `samples/`:

| Scenario | Paste | Expected result |
|----------|-------|-----------------|
| **Residual → escalate** | instruction line + contents of `samples/sample_findings_residual.json` | `routing.action = "route_to_analyst"`, `residual_amount = 59.45`, **one Jira ticket created in `RECON`**, `routing.escalation.tickets` populated |
| **Auto-clear** | instruction line + contents of `samples/sample_findings_clear.json` | `routing.action = "auto_clear"`, `escalation.escalated = false`, **no Jira ticket** |

**Instruction line to prepend** (then paste the JSON object beneath it):
```
Reconcile this Unreconciled Day. Findings JSON follows. Classify every difference, produce the 5-step
explanation, decide routing, and escalate only the genuine residual. Respond with ONLY the JSON contract.
```
(You can also paste just the JSON object — the system prompt already covers it.) Run one, check the
output + (for the residual case) that a `RECON-…` issue actually appears in Jira; then start a **new
message** and run the other. In production the backend sends this `message` automatically — paste is
only for playground testing.
