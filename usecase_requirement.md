Reconciliation — resolving an "Unreconciled Day" 

TRIGGER — A day-wise reconciliation difference appears between the scheme totals (e.g. Visa) and the issuer platform's transaction file, flagging an "Unreconciled Day" (note: activity reconciliation already accounts for scheme-related charges, including scheme ISA fees, so those do not typically cause this) 

Step 1 — Reconciliation Exception Agent fires (ingest & normalise) 

Pulls the scheme clearing files (national/domestic and international) and the platform's transaction file for the day, and normalises both into a single canonical record set for comparison 

Step 2 — Reconciliation Exception Agent continues (check timing first — primary driver) 

Tests for file-timing differences: identifies scheme transactions that arrived after the platform's fixed file-generation cutoff and were therefore excluded from that day but picked up in the next day's file — confirming no transactions are lost, the gap is purely a posting delay 

Step 3 — Reconciliation Exception Agent continues (reconcile across the day boundary) 

Matches the late-arriving, post-cutoff transactions to the following day's platform file, so the Day 1 "missing" items are accounted for against Day 2's inclusion and the timing shift is explained rather than treated as a true break 

Step 4 — Reconciliation Exception Agent continues (test currency conversion & rounding — second cause) 

For multi-currency activity, checks whether the residual difference is explained by exchange-rate timing (transaction-date vs settlement-date rate, e.g. $100 at 80 = £8,000 vs at 82 = £8,200) or by sub-penny rounding between systems; flags these as expected differences while watching for accumulation 

Step 5 — Reconciliation Exception Agent continues (classify, confirm scheme charges, route) 

Confirms scheme charges (scheme ISA and others) are already handled in reconciliation and not the cause, classifies the day's difference by likelihood (timing → FX/rounding → already-accounted scheme charges), and either auto-clears differences fully explained by timing/rounding or routes any genuine residual to the analyst with the evidence attached 

END RESULT — The "Unreconciled Day" is explained in minutes: timing-shifted transactions reconciled across the day boundary, FX and rounding differences identified as expected, and scheme charges confirmed as already accounted — so a posting delay is no longer mistaken for a data issue, and only a true residual reaches the analyst.