# Reconciliation Scenario Map — "Unreconciled Day" POC (Thredd ⇄ Visa)

Educational guide to the POC dataset: **what each file is, what each field means, and which
transaction embodies which exception.** All data is synthetic. Regenerate any time with
`python gen_unrecon_day.py`. Settlement currency = **GBP**. Processing **Day 1 = 2025-04-01**,
**Day 2 = 2025-04-02**.

---

## 1. The two sides of the reconciliation

```
   VISA  ───sends 2 BASE II clearing files──▶  THREDD  ───sends XML report──▶  ISSUER
  (scheme truth)        National + International       (platform record)       (you reconcile)
```

- **Scheme side (Visa)** = what Visa cleared. Comes as **fixed-width BASE II — ITF** files (TC records),
  split **National** and **International**, daily.
- **Platform side (Thredd)** = what the issuer platform posted. Comes as the **Transaction XML
  Report** (the XSD), one file per day via sFTP.
- **Reconcile** = match the two on **ARN**; the day's difference must be *explained*.

## 2. The files in this POC

| File | Side | Format | What it is |
|------|------|--------|-----------|
| `VISA_CLR_NAT_5359282076_20250401.itf` | Visa | BASE II — ITF fixed-width | National GBP clearing, Day 1 (no FX) |
| `VISA_CLR_INTL_5359282076_20250401.itf` | Visa | BASE II — ITF fixed-width | International clearing, Day 1 (FX via TCR1, ISA) |
| `clearing_detail_NAT_…csv` / `…INTL_…csv` | Visa | CSV | Readable decode of the two `.itf` files |
| `THREDD_TXN_REPORT_20250401.xml` | Thredd | XML (per XSD) | Platform Day-1 report — **short** by late txns |
| `THREDD_TXN_REPORT_20250402.xml` | Thredd | XML (per XSD) | Platform Day-2 report — late txns land here |

**Why 2 Thredd files?** Same daily report on two consecutive days. The *primary* cause (timing) is a
transaction that slips from Day 1 into Day 2 — you need both days to prove "delayed, not lost".

**BASE II — ITF record types in the `.itf`:** `TC90` = file header · `TC05` = sales draft (TCR0 = core,
TCR1 = FX/currency-conversion component) · `TC92` = file trailer. *(Representative of the proprietary
Visa BASE II layout; recon matches on ARN/amounts/dates, not byte positions.)*

## 3. The five-step reconciliation (with this dataset's actual numbers)

| Step | What happens | Amount |
|------|--------------|-------:|
| **1. Normalise & match (ARN)** | Visa Day-1 **net** (definitive) − Thredd Day-1 sum | **raw diff = GBP 347.33** |
| **2–3. Timing (primary)** | 2 late txns: in Visa Day 1, found in Thredd **Day 2** | GBP 280.60 |
| **4. FX rate-timing** | 2 cross-border txns priced at different rate dates | GBP 7.29 |
| **4. Rounding** | per-txn 2dp sum vs Visa full-precision net | GBP −0.01 (0.0007%, < 0.01%) |
| **5. Scheme ISA (confirm)** | present & equal both sides → nets to 0 | GBP 0.00 (not the cause) |
| **5. TRUE RESIDUAL → analyst** | in Visa, absent from Thredd Day 1 **and** Day 2 | **GBP 59.45** |

`280.60 + 7.29 − 0.01 + 59.45 = 347.33` ✓ — everything except the **GBP 59.45 true break** is explained.

## 4. Scenario → transaction map (the "all cases" coverage)

| Scen | Cause | Transaction(s) | ARN | Amount | Where it lives |
|------|-------|----------------|-----|-------:|----------------|
| **A** | Timing/cutoff (primary) | DOM-004 | `74220505101000000000400` | 230.00 | Visa D1 + Thredd **D2** |
| **A** | Timing/cutoff | INTL-006 | `74220505101000000001200` | 50.60 | Visa D1 + Thredd **D2** |
| **B** | FX rate-timing | INTL-003 | `74220505101000000000900` | Δ 1.10 | both D1; rate 0.857 vs 0.843271 |
| **B** | FX rate-timing | INTL-004 | `74220505101000000001000` | Δ 6.19 | both D1; rate 0.805 vs 0.792618 |
| **C** | Rounding | all NORMAL intl (incl. JPY INTL-005, 0-exponent) | — | −0.01 | sum-vs-net drift |
| **D** | Scheme ISA (red herring) | every INTL txn (`FeeAmt`) | — | 4.81 total | equal both sides → 0 |
| **E** | **True residual** | INTL-007 | `74220505101000000001300` | 59.45 | **Visa only — nowhere in Thredd** |

**How A is proven (not just flagged):** DOM-004 / INTL-006 carry `SchemeSettlementDate=20250401`
(Visa cleared Day 1) but appear in the Day-2 file with `SettlementDate=20250402` (Thredd posted Day 2).
Same ARN, one day later = posting delay.

## 5. Field glossary (what each XSD / clearing field means here)

| Field | Meaning | Role in recon |
|-------|---------|---------------|
| `ARN` | Acquirer Reference Number (≤23) | **the match key** across both sides |
| `SettlementDate` | date **Thredd** settled/posted | Day-1 vs Day-2 → reveals timing shift |
| `SchemeSettlementDate` | date **Visa** cleared (from Visa `TC90` header) | compared to SettlementDate to spot delay |
| `SchemeReconciliationDate` | Visa reconciliation date | same Visa cycle reference |
| `TxnAmt` | amount in **transaction** currency (e.g. EUR/USD/JPY) | original purchase |
| `BillAmt` (value, rate) | amount billed in **GBP** at the **transaction-date** rate | platform's FX view |
| `SettlementAmt` (value, rate) | GBP settled (Visa: = BillAmt unless multicurrency BIN) | compared vs Visa clearing amount |
| `FeeAmt` + `FeeClass` | scheme/programme fee (here **ISA**, type 2) | Step 5 confirms it nets to 0 |
| `MsgSource` | `54` = Visa **International**, else national | tags nat/intl |
| `CycleNumber` | Mastercard-only (Visa has no cycles) | placeholder `01` for Visa rows |

## 6. Regenerate & sources
- Regenerate: `python c:\tasks\vss110\gen_unrecon_day.py` (deterministic; prints the table in §3).
- Authoritative references (Thredd/Visa docs) and the BASE II-format confirmation: see
  [SOURCES.md](SOURCES.md).
