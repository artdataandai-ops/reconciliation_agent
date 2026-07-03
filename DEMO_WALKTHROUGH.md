# Reconciliation Exception Agent — Demo Walkthrough (Read-Aloud Script)

> **Who this is for:** the person delivering the demo. You do **not** need to be a
> payments expert or a developer to run this. Read the sections in order. Everything
> you need to *say* is here, and every technical term and abbreviation is spelled out
> the first time it appears.
>
> **What this describes:** the version published on the `main` branch. All money figures
> below come straight out of the running system. The **numbers are fixed** so the demo
> always ties out; only the **dates move** (they auto-advance so the demo always looks
> like "today"). Wherever this script says *"Day 1"* and *"Day 2"*, the screen will show
> two real, consecutive calendar dates.

---

## 0. Glossary — say these correctly (read this once before demoing)

| Term / abbreviation | Full name | What it means in plain English |
|---|---|---|
| **POC** | Proof of Concept | A small working demo to prove the idea, not the final product |
| **Issuer** | Card issuer | The bank / card program that gives cardholders their cards and must reconcile the money |
| **Visa** | — | The card **scheme** (network). It tells us what it settled (the "truth" side) |
| **Thredd** | — | The card **processor / platform** that runs the program and records every transaction (our "platform" side) |
| **Reconciliation** | — | Proving two records of the same money agree. Here: Visa's total vs Thredd's total |
| **Unreconciled Day** | — | A day where Visa's total and Thredd's total **don't** match, and the gap must be explained |
| **Settlement** | — | The actual movement/netting of money for a day |
| **VSS** | Visa Settlement Service | Visa's official document stating the single **net** amount for the day — the definitive figure |
| **Net settlement** | — | One bottom-line number for the whole day (not a list) |
| **Clearing** | — | The detailed, transaction-by-transaction file Visa sends (the line items behind the net) |
| **BASE II — ITF** | — | The format of Visa's clearing files — a fixed-width text layout delivered as `.itf` (ITF) files (each field sits at fixed character positions) |
| **ARN** | Acquirer Reference Number | The **unique ID** that follows a single transaction across both Visa and Thredd. This is how we match the two sides |
| **FX** | Foreign Exchange | Currency conversion (e.g. euros → pounds) |
| **Rate-timing** | — | Visa and Thredd apply the exchange rate on **different dates**, so the converted pound amount differs slightly |
| **ISA** | International Service Assessment | A Visa **fee** charged on cross-border transactions |
| **Residual / true break** | — | A real, unexplained difference that a human must investigate |
| **Timing / late posting** | — | A transaction Visa cleared on one day but the platform recorded the **next** day — not lost, just late |
| **Rounding** | — | Tiny drift from adding up amounts rounded to the penny vs one full-precision total |
| **Tolerance** | — | A small allowed limit below which a difference is treated as harmless |
| **GBP / EUR / USD / JPY** | — | Pounds / Euros / US Dollars / Japanese Yen |
| **XML** | eXtensible Markup Language | A structured text file format — Thredd's report comes as XML |
| **JSON** | JavaScript Object Notation | A structured data format — used for Visa's net figure and inside the app |
| **CSV** | Comma-Separated Values | A spreadsheet-style file — a readable decode of the Visa clearing files |
| **sFTP** | secure File Transfer Protocol | The secure channel banks use to drop these files each day |
| **PAN** | Primary Account Number | The card number (all synthetic/fake here — no real cards) |
| **MCC** | Merchant Category Code | A code for the merchant's business type |
| **API** | Application Programming Interface | How two programs talk to each other |
| **FastAPI** | — | The Python framework our backend is built with |
| **React / Vite** | — | The tools the dashboard (frontend) is built with |
| **CORS** | Cross-Origin Resource Sharing | A browser security rule; only relevant because the dashboard and backend live on different web addresses |
| **Lyzr** | — | The platform hosting our **AI agent** (the reasoning "brain") |
| **Agent** | — | The AI that interprets the numbers and decides what to do |
| **Jira** | — | The ticketing system where a real break gets logged for a human analyst |
| **Decimal** | — | A way of doing money math that is always exact (never the tiny errors normal computer decimals make) |

**Two-line pronunciation cheat:** *Thredd* = "thred". *Lyzr* = "lizard" without the "-ard" → "LY-zer". *ARN* = say the letters, "A-R-N".

---

## 1. The story in one breath (your opening line)

> "Every single day, a card program has to prove that the money **Visa** says it settled
> matches the transactions our platform, **Thredd**, actually recorded. When the two don't
> match — we call that an **Unreconciled Day** — someone today has to dig through raw files
> by hand to explain the gap. This tool explains the whole gap in seconds, and sends a human
> **only** the one difference that's a genuine problem."

---

## 2. The business problem (say this slowly, no tech yet)

- Visa sends us one official number for the day — *"your net settlement is **£1,457.94**."* That's the **VSS** figure, and it's treated as the truth.
- Our own platform, Thredd, recorded transactions for that same day that add up to **£1,110.61**.
- Those don't match. The gap is **£347.33**.
- On a real program this happens **every day**. Most of that gap is completely harmless — money that's just a day late, small currency-rate differences, rounding to the penny. But today a human analyst still has to open every file and prove, line by line, which pennies are harmless and which one is a real break.
- **That manual triage is the pain. This tool automates it.**

> **Say:** "The magic isn't that it finds a difference — anyone can subtract. The magic is that
> it *explains* the difference and only escalates the part that's genuinely wrong."

---

## 3. The three players

```
   VISA  ── sends clearing files + a net figure ─▶  THREDD  ── sends its transaction report ─▶  ISSUER
 (the scheme:                                     (the processor/                            (the bank:
  what Visa settled — the "truth")                 platform record)                           must reconcile)
```

- **Visa (scheme side)** = what Visa cleared. We get it two ways: detailed **clearing** files (**BASE II** format) *and* one official **net** number (**VSS**).
- **Thredd (platform side)** = what our processor recorded, as an **XML** report, one file per day.
- **Reconcile** = match the two sides on the **ARN** and explain every penny of any gap.

---

## 4. The architecture — three parts, one key idea

```
  Visa BASE II clearing files (National + International) ┐
  + Visa VSS net settlement number                      ├─▶  Backend (calculator) ─▶ Lyzr AI agent (brain) ─▶ React dashboard (story)
  Thredd Transaction XML report (Day 1 + Day 2)         ┘     parses · matches · computes   classifies · explains · routes   shows it
```

**The single most important design idea — say this to the client:**

> **"The math is done by a deterministic engine. The judgement is done by AI. We deliberately
> kept them separate — so you never have to trust the AI with the numbers."**

**Part 1 — The backend = the calculator (the "hands").**
It reads the raw files, matches every transaction on its ARN, and computes the numbers. It is **always exact** — all money math uses **Decimal** arithmetic, so there are never rounding errors. It never guesses. Its only job is to produce **facts**: here is the gap, and here is exactly where each piece of it comes from.

**Part 2 — The Lyzr agent = the brain.**
It receives those facts and does **judgement only**: classify each piece of the gap (is it timing? FX? rounding? a real break?), write the plain-English explanation, and decide what to route to a human. It is explicitly instructed to **never do arithmetic and never invent a number** — it only reasons about numbers the engine already proved.

**Part 3 — The frontend = the story.**
A dashboard (built with React) that shows the files arriving, plays the agent's step-by-step reasoning, draws a chart of the gap being explained away, and shows the final escalation.

**The proof that the AI is doing real work:** if the agent is switched off, the dashboard still shows the raw gap and *where* the differences are — but **no explanation, no classification, no routing**. That's on purpose. It makes the agent's value impossible to miss: *the numbers come from the engine; the intelligence comes from the agent.*

> **Security point to mention:** the AI's secret key lives only in the backend, never in the
> browser. And because the AI never touches money figures, it literally cannot get a number wrong.

---

## 5. The files in the demo (four "received" files)

| File you'll see | Side | Format | What it is |
|---|---|---|---|
| `VISA_CLR_NAT_…` | Visa | BASE II — ITF (fixed-width text) | **Nat**ional (UK, GBP) clearing for Day 1 |
| `VISA_CLR_INTL_…` | Visa | BASE II — ITF (fixed-width text) | **Int**ernationa**l** clearing for Day 1 (has currency conversion + ISA fees) |
| `THREDD_TXN_REPORT_…(Day 1)` | Thredd | XML | Our platform's Day-1 report — it is **short** by the late transactions |
| `THREDD_TXN_REPORT_…(Day 2)` | Thredd | XML | Our platform's **next-day** report — the late transactions land here |

Plus, behind the scenes, Visa's **VSS** net figure arrives as a small JSON file (`£1,457.94`).

> **Why two Thredd files?** Because the biggest cause of the gap is **timing** — a transaction
> Visa cleared on Day 1 that our platform only posted on Day 2. You need **both** days to prove
> it was *delayed, not lost*. Say this out loud when you point at the two Thredd files.

**A note you can give if asked about BASE II internals:** inside a BASE II file, records are tagged — `TC90` is the file header, `TC05` is a sale (with a `TCR0` core part and a `TCR1` currency-conversion part), and `TC92` is the file trailer. Our engine reads these and matches on the ARN, amounts and dates — so the exact byte positions don't affect the result.

---

## 6. The live demo — click by click, with what to say

### Screen 1 — "Files received"

**Do:** Open the dashboard. Four files show a **received** status, each with its record count and size.

**Say:**
> "Here are the four files that land each morning: two from Visa — domestic and international
> clearing — and two from our platform Thredd, for Day 1 and the following day. Notice they're
> in their real, native formats. Nothing has been cleaned up or pre-processed. The backend
> decodes Visa's fixed-width **BASE II** layout and reads Thredd's **XML** directly."

**Optional flourish:** Click a file to preview it. The Visa file shows decoded, readable rows next to a sample of the raw fixed-width text — good proof we're parsing the genuine article.

### Screen 2 — Click **"Run reconciliation"**

**Say as you click:**
> "In this demo I click Run. In production there's no button — the agent fires automatically
> the moment all the files land on the secure **sFTP** drop. Watch what happens."

**What happens behind the scenes (you can narrate this):**
> "The engine matches every transaction on its **ARN** — that unique reference that follows a
> transaction across both Visa and Thredd — computes the gap, and hands the facts to the AI
> agent. The agent now walks its reasoning steps live on screen."

### Screen 3 — The result

Point at each part as it appears:

1. **The waterfall chart** — *"Here's the £347.33 gap, and watch it get chipped away as each piece is explained, until only the real break is left standing."*
2. **The exceptions list** — *"Every transaction, tagged: reconciled, timing, FX, or break."*
3. **The agent run-log** — *"These are the agent's reasoning steps, ticking off one by one."*
4. **The escalation line** — *"And here — the one genuine break has been logged to **Jira** automatically as a ticket for a human analyst."*

**Your closing line for the walkthrough:**
> "Fourteen transactions came in. Thirteen are explained and cleared automatically. **One** — a
> £59.45 charge — is a genuine break, and it's the only thing a human ever has to look at."

---

## 7. The five scenarios — explained with the actual transactions (ARNs)

Every transaction carries an **ARN**. In this dataset they all share a long common prefix and
differ only in the last few digits, so below we show just the **last digits** to keep it readable.

**The full roster — 14 transactions:**

| ARN (last digits) | Merchant | Currency | Amount (GBP) | Scenario |
|---|---|---|---:|---|
| …0100 | TESCO STORES | GBP | 45.00 | Normal (matches cleanly) |
| …0200 | ARGOS RETAIL | GBP | 120.50 | Normal |
| …0300 | GREGGS | GBP | 8.99 | Normal |
| …0400 | JOHN LEWIS | GBP | 230.00 | **A — Timing** |
| …0500 | PRET A MANGER | GBP | 15.75 | Normal |
| …0600 | SAINSBURYS | GBP | 67.20 | Normal |
| …0700 | ZARA MADRID | EUR | 84.33 | Normal |
| …0800 | BEST BUY NYC | USD | 198.15 | Normal |
| …0900 | FNAC PARIS | EUR | 68.56 | **B — FX** |
| …1000 | APPLE STORE SF | USD | 402.50 | **B — FX** |
| …1100 | BIC CAMERA TOKYO | JPY | 78.81 | Normal |
| …1200 | H&M BERLIN | EUR | 50.60 | **A — Timing** |
| …1300 | UBER US TRIP | USD | 59.45 | **E — True break** |
| …1400 | LIDL DUBLIN | EUR | 28.11 | Normal |

The "Normal" ones match cleanly on both sides — they're what makes this look like a realistic
day. The five scenarios below are the interesting part.

---

### Scenario A — Timing (late posting) → £280.60 → cleared automatically

**Plain English:** two transactions Visa cleared on **Day 1**, but our platform only recorded on **Day 2**. The money isn't lost — it's a day late.

| ARN | Merchant | Amount |
|---|---|---:|
| …0400 | JOHN LEWIS | £230.00 |
| …1200 | H&M BERLIN | £50.60 |

**How the engine finds it:** it looks up ARN …0400 in the Thredd **Day-1** file → not there. It looks in the **Day-2** file → found. Same for …1200.

**How it's proven (not just guessed):** each of these carries a Visa clearing date of **Day 1** but a Thredd posting date of **Day 2**. Same ARN, one day apart = a posting delay, provably not a loss.

**Total:** £230.00 + £50.60 = **£280.60.**

> **Say:** "This is why we load two days of Thredd files — so we can *prove* the missing money
> just showed up a day late, using the very same reference number."

---

### Scenario B — FX (foreign-exchange) rate-timing → £7.29 → cleared automatically

**Plain English:** two cross-border transactions that **match** on both sides, but the pound amounts differ by a few pounds. Why? Visa converted the currency using the rate on the **settlement date**; our platform used the rate on the **transaction date**. The rate moved a little between those dates.

| ARN | Merchant | Visa's GBP | Thredd's GBP | Difference |
|---|---|---:|---:|---:|
| …0900 | FNAC PARIS (EUR 80.00) | 68.56 | 67.46 | £1.10 |
| …1000 | APPLE STORE SF (USD 500.00) | 402.50 | 396.31 | £6.19 |

**Total:** £1.10 + £6.19 = **£7.29.**

#### Where does the difference come from? (nobody made a mistake)

This is the point to be crystal clear on: **both Visa and Thredd did their maths perfectly.** They
just used **different exchange rates**, because exchange rates change day to day and the two sides
convert on different dates:

- **Thredd** converts on the **transaction date** (the day the card was tapped) → uses that day's rate.
- **Visa** converts on the **settlement date** (a day or two later, when money actually moves) → uses that day's rate.

Same purchase, both multiply correctly, but a different rate goes in — so a slightly different
number of pounds comes out. Using APPLE STORE SF ($500.00):

```
Thredd:  $500 × 0.792618 (transaction-date rate) = £396.31   ← correct maths
Visa:    $500 × 0.805000 (settlement-date rate)  = £402.50   ← also correct maths
                                                   ─────────
difference                                         = £6.19
```

> **Analogy to say if asked:** "It's like you and a friend buying the same $500 gadget, but you pay
> Monday and they pay Wednesday. Both banks use the correct rate, but the rate shifted midweek, so
> the pound bills differ. Neither bank erred — it's *when* the conversion happened, not *how*."

This is normal and expected on **every** cross-border transaction, which is why the system's job is
to *recognise* it, not eliminate it.

#### How the engine classifies it — two separate numbers (don't mix them up)

**The 5-pence (5p) threshold — "is this difference big enough to bother with?"**
For every matched transaction the engine computes the difference in pounds and compares it to a **5p cutoff**:

- difference **5p or more** → worth flagging as **FX**.
- difference **under 5p** → treat as a clean match; the stray pennies just fall into the rounding bucket.

Note this is a **comparison**, not a conversion — the £1.10 difference isn't "becoming" 5p. Put both
on the same scale to see it: £1.10 is **110 pence**, the cutoff is **5 pence**, so 110p easily clears
5p. (Every normal transaction has a difference of £0.00 = 0p, which is under 5p → clean match.)

**The 2-pence (2p) verification — "do the rates actually prove it's FX?"**
Clearing the 5p bar only means the difference is *worth checking*. The engine then **re-derives** the
difference from the two rates and confirms it matches, before clearing it:

```
predicted difference = source amount × (Visa's rate − Thredd's rate)

FNAC:  €80  × (0.857000 − 0.843271) = £1.0983  vs observed £1.10  → agree ✓
APPLE: $500 × (0.805000 − 0.792618) = £6.1910  vs observed £6.19  → agree ✓
accept as FX if | observed − predicted | ≤ 2p
```

If the rates account for the difference (within 2p) → **cleared as FX**. If they **don't** — or the
source amount / rate is missing (e.g. a plain GBP item that shouldn't have a conversion) — the engine
**cannot prove it's FX, so it routes it to a human** as a possible break instead of clearing it. That
is how we know it's genuinely a rate difference and not something else (a fee, a partial refund, a
keyed-in error) that happened to be a similar size.

> **The 2p is NOT a cap on how big an FX difference can be.** It's the allowed gap between the
> *observed* difference and the *predicted* difference — and those only ever disagree by a rounding
> penny, no matter how large the transaction. So a genuine £6, £60 or £600 FX difference all pass;
> only differences the rates *can't* explain get flagged.

**The two numbers side by side:**

| Number | Question it answers | Below it → | Above it → |
|---|---|---|---|
| **5p** (label threshold) | Is the difference big enough to call FX at all? | clean match (→ rounding) | worth checking as FX |
| **2p** (verify tolerance) | Do the rates actually explain the difference? | escalate — rates can't prove it | cleared as genuine FX |

> **Say:** "These aren't errors — they're the normal, expected result of Visa and our platform
> stamping the exchange rate on slightly different dates. The system doesn't just assume that,
> though — it re-does the conversion from both rates and only clears the difference if the rates
> actually account for it. Anything they can't explain goes to a human instead."

---

### Scenario C — Rounding → −£0.01 → cleared automatically

**Plain English:** the smallest possible difference — a single penny. Visa gives us **one** number at full precision; we add up **many** individual transactions each rounded to the penny. Adding rounded pennies drifts a hair from the single full-precision total.

**How the engine handles it:** it's the leftover after the three real causes are removed. The engine then checks it's within the **0.01% tolerance** — here it's **0.0007%**, far inside — so it's accepted as rounding.

**Amount:** **−£0.01.**

> **Say:** "One penny, and the system can even tell you it's 0.0007% of the day's total —
> comfortably within tolerance. It's noise, not a problem."

---

### Scenario D — Scheme ISA fee → £0.00 → dismissed as "not the cause"

**Plain English:** **ISA** is a Visa **fee** on cross-border transactions. People often *suspect* fees when a day won't balance, so this scenario exists to show the system can rule out the usual suspect.

**How the engine handles it:** it adds up the ISA fees on the Visa side of matched transactions (**£4.26**) and on the Thredd side (**£4.26**). They're **equal** — so the fees cancel out and contribute **nothing** to the gap.

**Amount:** **£0.00 impact.**

> **Say:** "The fees are real, but they're identical on both sides, so they net to zero. The
> system proactively clears the usual suspect so the analyst never wastes time on it."

---

### Scenario E — The TRUE break → £59.45 → escalated to a human

**Plain English:** the one real problem. A transaction Visa says it settled that **does not exist anywhere in our platform** — not Day 1, not Day 2.

| ARN | Merchant | Amount |
|---|---|---:|
| …1300 | UBER US TRIP | £59.45 |

**How the engine finds it:** ARN …1300 is in Visa's file but matches **nothing** in either Thredd file. It's not late (it's not in Day 2), and it's not a rate difference. Visa is charging us £59.45 for something we have no record of.

**What the agent does:** it classifies this as a genuine break and **opens one Jira ticket for it** — and the dashboard shows *"Escalated → Jira RECON-123."* It is instructed to escalate **only** genuine breaks — never timing, FX, rounding, or ISA.

**Amount:** **£59.45 → routed to an analyst.**

> **Say:** "This is the payoff. Out of everything, this is the single transaction a human needs
> to see — and it's been isolated, explained, and ticketed automatically."

---

## 8. The calculations — with the real numbers plugged in

You don't have to read all of this aloud — but keep it handy for a technical audience who asks
"show me the math." Every number here is straight from the running system.

### Step 1 — The raw difference
```
raw difference = Visa net settlement (VSS)  −  Thredd Day-1 total
               = 1,457.94  −  1,110.61
               = £347.33
```
*(The Thredd Day-1 total is only £1,110.61 because three transactions Visa cleared — John Lewis,
H&M and Uber — are missing from it.)*

### Step 2 — Timing
```
timing = sum of Visa amounts whose ARN turns up in the Thredd Day-2 file
       = 230.00 (John Lewis)  +  50.60 (H&M)
       = £280.60
```

### Step 3 — FX rate-timing
```
Each difference is re-derived from the two rates to confirm it's genuinely FX:
  FNAC:  €80  × (0.857000 − 0.843271) = £1.0983  ≈ observed £1.10  ✓ (within 2p)
  APPLE: $500 × (0.805000 − 0.792618) = £6.1910  ≈ observed £6.19  ✓ (within 2p)

FX = sum of the confirmed pound differences on matched cross-border transactions (each ≥ 5p)
   = 1.10 (FNAC)  +  6.19 (Apple)
   = £7.29
```

### Step 4 — The true break (residual)
```
residual = sum of Visa amounts whose ARN is in NEITHER Thredd file
         = 59.45 (Uber)
         = £59.45
```

### Step 5 — Rounding (the balancing penny)
```
rounding = raw difference  −  timing  −  FX  −  residual
         = 347.33  −  280.60  −  7.29  −  59.45
         = −£0.01
tolerance check: 0.01 / 1,457.94 = 0.0007%   (well under the 0.01% limit)
```

### Step 6 — ISA fee check (confirm it's not the cause)
```
Visa ISA total (matched)   = 0.42 + 0.99 + 0.34 + 1.98 + 0.39 + 0.14 = £4.26
Thredd ISA total (matched) = 0.42 + 0.99 + 0.34 + 1.98 + 0.39 + 0.14 = £4.26
equal?  4.26 = 4.26  →  YES  →  contributes £0.00 to the gap
```

### The final check — it must balance exactly
```
timing + FX + rounding + residual  =  raw difference
280.60 + 7.29 + (−0.01) + 59.45    =  347.33
                          347.33   =  347.33   ✓
```

> **Say:** "And the engine *insists* on this last line balancing to the penny. If it ever didn't,
> the system is built to hand the **entire** difference to a human rather than pretend it's
> explained. The AI never gets to fudge the math — it only interprets numbers the engine has
> already proved add up."

### One-look summary table

| Piece | What it is | Amount | Outcome |
|---|---|---:|---|
| Raw difference | Visa net − Thredd Day-1 | **£347.33** | the gap to explain |
| Timing | John Lewis + H&M, cleared next day | £280.60 | ✅ explained |
| FX rate-timing | FNAC + Apple, rate-date difference | £7.29 | ✅ explained |
| Rounding | penny drift, within tolerance | −£0.01 | ✅ explained |
| ISA fee | equal both sides | £0.00 | ✅ dismissed |
| **True break** | Uber — missing everywhere | **£59.45** | 🎫 **escalated** |

---

## 9. Anticipated client questions (and your answers)

**"Is this real data?"**
> "No — it's fully synthetic, no real card numbers. The numbers are fixed so the demo always ties
> out, but the dates automatically advance to today, so it always looks current."

**"Does a person really click Run in production?"**
> "No. That's just for the demo. In production the agent triggers automatically the moment all the
> files land on the secure sFTP drop."

**"Where does the AI's secret key live? Is it safe?"**
> "The key lives only in the backend, never in the browser. And the AI never sees or produces money
> figures — it only classifies facts the engine computed — so it can't get a number wrong."

**"What if the AI is wrong or makes something up?"**
> "The engine enforces a hard check that all the pieces add back to the exact gap. If anything
> doesn't reconcile, the system routes the whole difference to a human instead of trusting the AI."

**"What happens to the escalated break?"**
> "The agent opens a Jira ticket — one per genuine break — with the evidence attached, and it only
> ever does that for real breaks, never for timing, FX, rounding or fees. So the analyst's queue is
> only ever real work."

**"How do you know a currency difference isn't hiding a real problem?"**
> "We don't just assume it. The engine re-derives each difference from the two exchange rates —
> the amount times the rate change — and only clears it if the rates actually account for it,
> within a 2p tolerance. If they can't explain it, it's treated as a possible break and escalated
> to a human, just like the Uber transaction."

**"Isn't 2p too tight — what if a real currency difference is bigger than 2p?"**
> "The 2p isn't a limit on the size of the difference — a genuine £6, £60 or £600 FX difference all
> pass. It's the allowed gap between the difference we *see* and the difference the rates *predict*,
> and those only ever disagree by a rounding penny however large the transaction. Only differences
> the rates genuinely can't explain exceed it."

---

## 10. The five talking points to land (if you remember nothing else)

1. **The gap is £347.33. The system explains all of it and escalates only £59.45.**
2. **Math is deterministic, judgement is AI — kept separate so you never trust the AI with numbers.**
3. **The ARN is the match key** — it's how the same transaction is tracked across Visa and Thredd.
4. **Two Thredd days prove "late, not lost"** — the timing scenario is the biggest chunk (£280.60).
5. **The one true break (Uber, £59.45) is auto-ticketed in Jira** for a human — everything else clears itself.

---

## 11. The 30-second version (if the room is in a hurry)

> "Visa says we owe £1,457.94; our platform shows £1,110.61 — a £347 gap. Our engine parses the
> raw Visa and Thredd files, matches every transaction on its reference number, and proves exactly
> where that gap comes from: £280 is just late posting, £7 is currency-rate timing, a penny is
> rounding, and the fees cancel out. Then it flags the **one** £59.45 transaction that's genuinely
> missing and opens a Jira ticket for it. Hours of analyst work, done in seconds — and the math is
> guaranteed correct because the AI never touches the numbers, it only explains them."
