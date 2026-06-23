# Sources — Visa ⇄ Thredd Reconciliation POC

Authoritative references behind this POC. Each line notes what it proves. Stakeholder-ready.

## What Visa sends (BASE II, Domestic + International)
- **Thredd — Global Transaction Reporting Guide (v1.5)**
  https://docs.thredd.com/pdf/Global_Transaction_Reporting_Guide_1.5.pdf
  → "Visa provide 2 files (Domestic + International) each day" (regional timing variants); Mastercard
  uses 6 clearing cycles/day. Describes Thredd's Clearing Report / Non-Clearing Report.

## The platform file = Thredd Transaction XML Report (the XSD)
- **Thredd — Transaction XML Reporting Guide**
  https://docs.thredd.com/Transaction_XML_Reporting_Guide.htm
  (PDF v2.1.5: https://docs.thredd.com/pdf/Transaction_XML_Reporting_Guide_2.1.5.pdf)
  → Daily XML report (Visa/Mastercard/MNE/Discover) via sFTP, "to reconcile against Visa/Mastercard
  settlement advises."

## Proof the Visa feed is BASE II TC-records
- **Thredd — Schema Sub-Elements & Attributes**
  https://docs.thredd.ai/transactionxmlglobal/Content/Schema/Sub_Elements_and_Attributes.htm
  → `SchemeSettlementDate` sourced from **Visa TC90 header**; multicurrency uses **Visa TC56 rates**
  (TC90/TC56 = BASE II records). `CycleNumber` is Mastercard-only; `ARN` is the lifecycle key.

## FX / rounding reconciliation behaviour (Step 4), quantified
- **Thredd — Visa Multicurrency BIN Settlement (product sheet)**
  https://docs.thredd.com/product_sheets/Visa_Multicurrency_Settlement_Product_Sheet.pdf
  → Visa clearing carries Source + Destination currency; per-transaction rounding vs Visa's daily net
  is "< 0.01%"; "treat Visa's Net Settlement position as the definitive reconciliation amount."

## Context / credibility
- **Thredd — Reporting and Reconciliation**
  https://docs.thredd.com/More_Information/Reporting_Options.htm
- **Visa Partner Directory — Thredd** (accredited Visa processor)
  https://partner.visa.com/site/partner-directory/thredd.html

## Caveat for stakeholders
The full byte-level BASE II layout (field offsets, TC01–TC92) is a **proprietary Visa spec** (Visa
Online / VPSS Clearing, behind Visa login) — not publicly linkable. The sources above confirm the
**format and behaviour**; exact offsets come from your Visa/Thredd onboarding pack. The POC matches on
ARN / amounts / dates, so byte-offsets do not affect it.
