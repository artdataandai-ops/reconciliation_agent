#!/usr/bin/env python3
"""
Unreconciled-Day Reconciliation POC dataset generator (Thredd <-> Visa).

Dates are dynamic: D1 (reconciled day) = as-of - 1, D2 (catch-up) = as-of (default today).
Run `python gen_unrecon_day.py --as-of YYYY-MM-DD` to pin the demo date.

Produces (with <D1>/<D2> = YYYYMMDD):
  Scheme side (Visa BASE II — ITF clearing, representative fixed-width + readable CSV):
    VISA_CLR_NAT_5359282076_<D1>.itf   / clearing_detail_NAT_5359282076_<D1>.csv
    VISA_CLR_INTL_5359282076_<D1>.itf  / clearing_detail_INTL_5359282076_<D1>.csv
    VISA_SETTLEMENT_NET_5359282076_<D1>.json   (VSS definitive net settlement figure)
  Platform side (Thredd Transaction XML Report, conforms to the XSD):
    THREDD_TXN_REPORT_<D1>.xml  (D1 - short by late txns)
    THREDD_TXN_REPORT_<D2>.xml  (D2 - late txns appear here)

All amounts synthetic. Settlement currency = GBP. Ties out by construction:
  raw Day-1 difference (Visa net - Thredd Day-1 sum)
     = timing(A) + FX rate-timing(B) + rounding(C) + true residual(E)
  ISA(D) is equal on both sides -> nets to 0 (confirmed, not the cause).
"""
from decimal import Decimal, ROUND_HALF_UP
from datetime import date, timedelta
import csv, os, json, argparse

_ap = argparse.ArgumentParser(description="Generate the Unreconciled-Day POC dataset (Thredd <-> Visa).")
_ap.add_argument("--as-of", dest="as_of",
                 help="Catch-up day (D2) as YYYY-MM-DD. Default: today. The reconciled day D1 = as-of - 1.")
_ap.add_argument("--out", default=r"c:\tasks\vss110\data", help="Output directory.")
_args, _ = _ap.parse_known_args()

OUT = _args.out
os.makedirs(OUT, exist_ok=True)
_asof = date.fromisoformat(_args.as_of) if _args.as_of else date.today()
D1 = (_asof - timedelta(days=1)).strftime("%Y%m%d")   # the unreconciled day (Thredd D1 is short)
D2 = _asof.strftime("%Y%m%d")                          # catch-up day (late txns land here)
SRE = "5359282076"        # Funds Transfer Settlement Reporting Entity (FTSRE, 10-digit)
ACQ_BIN, ISS_BIN = "422050", "476173"
ISA_RATE = Decimal("0.005")   # 0.5% International Service Assessment (equal both sides)

CCY = {"GBP": ("826", 2), "EUR": ("978", 2), "USD": ("840", 2), "JPY": ("392", 0)}

def q(value, exp):
    """Round Decimal to currency exponent, half-up."""
    return Decimal(value).quantize(Decimal(1).scaleb(-exp), rounding=ROUND_HALF_UP)

def gbp(v):   # 2dp GBP
    return q(v, 2)

# ---------------------------------------------------------------------------
# Master transaction set for Day 1.  scenario: NORMAL | A | B | E   (C is emergent; D=ISA on all INTL)
# rate = GBP per 1 unit of txn currency.  trate = Thredd/transaction-date rate, srate = Visa/settlement-date rate.
# ---------------------------------------------------------------------------
TXN = [
  # id          region ccy   amount      trate         srate         scen   merchant
  ("DOM-001","NAT","GBP","45.00",   "1","1","NORMAL","TESCO STORES 2245"),
  ("DOM-002","NAT","GBP","120.50",  "1","1","NORMAL","ARGOS RETAIL 0098"),
  ("DOM-003","NAT","GBP","8.99",    "1","1","NORMAL","GREGGS 1042"),
  ("DOM-004","NAT","GBP","230.00",  "1","1","A",     "JOHN LEWIS 0031"),
  ("DOM-005","NAT","GBP","15.75",   "1","1","NORMAL","PRET A MANGER 88"),
  ("DOM-006","NAT","GBP","67.20",   "1","1","NORMAL","SAINSBURYS 1190"),
  ("INTL-001","INTL","EUR","100.00","0.843271","0.843271","NORMAL","ZARA MADRID"),
  ("INTL-002","INTL","USD","250.00","0.792618","0.792618","NORMAL","BEST BUY NYC"),
  ("INTL-003","INTL","EUR","80.00", "0.843271","0.857000","B",     "FNAC PARIS"),
  ("INTL-004","INTL","USD","500.00","0.792618","0.805000","B",     "APPLE STORE SF"),
  ("INTL-005","INTL","JPY","15000", "0.0052537","0.0052537","NORMAL","BIC CAMERA TOKYO"),
  ("INTL-006","INTL","EUR","60.00", "0.843271","0.843271","A",     "H&M BERLIN"),
  ("INTL-007","INTL","USD","75.00", "0.792618","0.792618","E",     "UBER US TRIP"),
  ("INTL-008","INTL","EUR","33.33", "0.843271","0.843271","NORMAL","LIDL DUBLIN"),
]

rows = []
for i, (tid, region, ccy, amt, trate, srate, scen, merch) in enumerate(TXN, 1):
    amount = Decimal(amt)
    trate, srate = Decimal(trate), Decimal(srate)
    exp = CCY[ccy][1]
    # GBP amounts (settlement currency)
    thredd_gbp = gbp(amount * trate)            # Thredd: transaction-date rate, stored 2dp
    visa_gbp   = gbp(amount * srate)            # Visa clearing per-txn, 2dp
    exact_visa = amount * srate                 # full precision (feeds Visa net)
    isa        = gbp(thredd_gbp * ISA_RATE) if region == "INTL" else Decimal("0.00")  # ISA = international only
    arn = f"7{ACQ_BIN}5101{i:010d}00"[:23].ljust(23, "0")
    pan = f"{ISS_BIN}{(1234567+i*4099)%1000000:06d}{(3504+i)%10000:04d}"[:16]
    rows.append(dict(
        tid=tid, region=region, ccy=ccy, ccy_num=CCY[ccy][0], exp=exp, amount=amount,
        trate=trate, srate=srate, thredd_gbp=thredd_gbp, visa_gbp=visa_gbp,
        exact_visa=exact_visa, isa=isa, scen=scen, merch=merch, arn=arn, pan=pan,
        masked=pan[:6] + "******" + pan[-4:],
        mcc={"NAT":"5411","INTL":"5732"}[region],
        # presence
        in_thredd_d1 = scen in ("NORMAL", "B"),
        in_thredd_d2 = scen == "A",
    ))

# ===========================================================================
# Reconciliation decomposition
# ===========================================================================
visa_per_txn_total = sum((r["visa_gbp"] for r in rows), Decimal("0"))
visa_exact_total   = sum((r["exact_visa"] for r in rows), Decimal("0"))
visa_net           = gbp(visa_exact_total)                       # Visa's definitive daily net
thredd_d1_total    = sum((r["thredd_gbp"] for r in rows if r["in_thredd_d1"]), Decimal("0"))

timing_A   = sum((r["visa_gbp"] for r in rows if r["scen"] == "A"), Decimal("0"))
fx_B       = sum((r["visa_gbp"] - r["thredd_gbp"] for r in rows if r["scen"] == "B"), Decimal("0"))
residual_E = sum((r["visa_gbp"] for r in rows if r["scen"] == "E"), Decimal("0"))
rounding_C = visa_net - visa_per_txn_total
raw_diff   = visa_net - thredd_d1_total
isa_total  = sum((r["isa"] for r in rows if r["region"] == "INTL"), Decimal("0"))

# ===========================================================================
# Writers
# ===========================================================================
def fw(v, n, num=False):
    s = str(v)
    return (s.rjust(n, "0") if num else s.ljust(n))[:n]

def minor(dec, exp):
    return int((Decimal(dec) * (10 ** exp)).to_integral_value(ROUND_HALF_UP))

def write_visa_clearing(region, fname):
    sel = [r for r in rows if r["region"] == region]
    path = os.path.join(OUT, fname)
    lines = []
    # TC90 file header: file type, proc date, SRE, acquirer BIN, settlement currency
    lines.append(fw("90" + "0" + D1 + SRE + ACQ_BIN + "826" + region, 168))
    for r in sel:
        # TCR0 (TC05 First Presentment) - core
        rec = (fw("05",2)+fw("0",1)+fw(r["pan"],19,num=True)
               + fw(minor(r["visa_gbp"],2),12,num=True)   # settlement amount (GBP, 2dp)
               + fw("826",3,num=True)                      # settlement currency
               + fw(r["arn"],23)+fw(D1[4:],4,num=True)     # ARN, purch date MMDD
               + fw("9"+str(700000+sel.index(r)),6)        # auth code
               + fw(r["merch"],25)+fw(region,13)
               + fw(r["ccy_num"],3,num=True)+fw(r["mcc"],4,num=True)
               + fw(ACQ_BIN,6,num=True)+fw(ISS_BIN,6,num=True)
               + fw(minor(r["isa"],2),9,num=True))         # ISA fee
        lines.append(fw(rec,168))
        if region == "INTL":
            # TCR1 (FX / currency-conversion component): source ccy + amount, settle-date rate, dest GBP
            tcr1 = (fw("05",2)+fw("1",1)+fw(r["ccy_num"],3,num=True)
                    + fw(minor(r["amount"],r["exp"]),12,num=True)    # source amount (txn ccy exponent)
                    + fw("826",3,num=True)                            # destination currency (GBP)
                    + fw(minor(r["visa_gbp"],2),12,num=True)          # destination amount (GBP)
                    + fw(int(r["srate"]*Decimal(10**9)),15,num=True)) # conversion rate (9dp)
            lines.append(fw(tcr1,168))
    # TC92 file trailer: record count + total settlement amount
    tot = sum(minor(r["visa_gbp"],2) for r in sel)
    lines.append(fw("92"+"0"+fw(len(sel),6,num=True)+fw(tot,15,num=True),168))
    with open(path,"w",newline="\n") as f:
        f.write("\n".join(lines)+"\n")
    # readable CSV companion
    csvpath = os.path.join(OUT, fname.replace("VISA_CLR_","clearing_detail_").replace(".itf",".csv"))
    with open(csvpath,"w",newline="") as f:
        w = csv.writer(f)
        w.writerow(["tid","tc","arn","masked_pan","merchant","txn_ccy","txn_amount",
                    "settle_ccy","settle_amount_gbp","conv_rate_settlement","isa_fee_gbp","scenario"])
        for r in sel:
            w.writerow([r["tid"],"TC05",r["arn"],r["masked"],r["merch"],r["ccy"],
                        f'{r["amount"]:.{r["exp"]}f}',"GBP",f'{r["visa_gbp"]:.2f}',
                        f'{r["srate"]:.9f}',f'{r["isa"]:.2f}',r["scen"]])
    return path, csvpath

def esc(s): return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")

def cardfinancial(r, settle_date, scheme_settle_date):
    """One <CardFinancial> element (required XSD elements, in schema order)."""
    msgsrc = "54" if r["region"] == "INTL" else "70"   # 54 = Visa International
    rate = r["trate"] if r["region"] == "INTL" else Decimal("1")
    e = []
    a = e.append
    a("  <CardFinancial>")
    a(f"    <RecordType>ADV</RecordType>")
    a(f"    <FinId>{10000+rows.index(r)}</FinId>")
    a(f"    <PresentmentID>{20000+rows.index(r)}</PresentmentID>")
    a(f"    <Traceid_Lifecycle>{r['arn']}</Traceid_Lifecycle>")
    a(f"    <LocalDate>{D1}120000</LocalDate>")
    a(f"    <SettlementDate>{settle_date}</SettlementDate>")
    a(f"    <SchemeSettlementDate>{scheme_settle_date}</SchemeSettlementDate>")
    a(f"    <SchemeReconciliationDate>{scheme_settle_date}</SchemeReconciliationDate>")
    a(f"    <CycleNumber>01</CycleNumber>")  # placeholder; not applicable to Visa
    a(f'    <Card PAN="{r["pan"]}" MaskedPAN="{esc(r["masked"])}" product="DBT"/>')
    a(f'    <Account no="GB{r["pan"][-10:]}" type="02"/>')
    a(f'    <TxnCode direction="debit" Type="pos" Group="pos"/>')
    a(f'    <TxnAmt value="{r["amount"]:.{r["exp"]}f}" currency="{r["ccy_num"]}"/>')
    a(f'    <CashbackAmt value="0.00" currency="826"/>')
    a(f'    <BillAmt value="{r["thredd_gbp"]:.2f}" currency="826" rate="{rate:.9f}"/>')
    a(f'    <ApprCode>{("9"+str(700000+rows.index(r)))[:6]}</ApprCode>')
    a(f'    <Trace auditno="{(100000+rows.index(r))}" Retrefno="{r["arn"][:12]}"/>')
    a(f'    <MerchCode>{esc(r["merch"])[:30]}</MerchCode>')
    a(f'    <Term code="TERM0001" location="{esc(r["merch"])[:40]}" street="1 High St" city="{r["region"]}" country="GB"/>')
    a(f'    <Schema>VISA</Schema>')
    a(f'    <Txn/>')
    a(f'    <MsgSource value="{msgsrc}" domesticMaestro="no"/>')
    a(f'    <Fee direction="debit" value="0.00" currency="826"/>')
    a(f'    <FeeAmt direction="debit" value="{r["isa"]:.2f}" currency="826"/>')
    a(f'    <FeeClass interchangeTransaction="no" type="2" code="1"/>')
    a(f'    <SettlementAmt value="{r["thredd_gbp"]:.2f}" currency="826" rate="{rate:.9f}"/>')
    a(f'    <ARN>{r["arn"]}</ARN>')
    a(f'    <FIID>{ISS_BIN}0000</FIID>')
    a(f'    <RIID>{ACQ_BIN}0000</RIID>')
    a(f'    <ReasonCode>0000</ReasonCode>')
    a(f'    <Classification MCC="{r["mcc"]}"/>')
    a(f'    <Response approved="yes"/>')
    a(f'    <CCAAmount value="0.00" currency="826" included="no"/>')
    a("  </CardFinancial>")
    return "\n".join(e)

def write_thredd(fname, selector, settle_date):
    sel = [r for r in rows if selector(r)]
    path = os.path.join(OUT, fname)
    body = "\n".join(cardfinancial(r, settle_date,
                                   D1 if r["scen"] in ("A",) else settle_date) for r in sel)
    # for on-time rows scheme date == settle date; for late (A) rows scheme date = D1 but file/settle = D2
    xml = ('<?xml version="1.0" encoding="utf-8"?>\n'
           f'<Transactions reportDate="{settle_date}" sre="{SRE}">\n{body}\n</Transactions>\n')
    with open(path,"w",newline="\n") as f:
        f.write(xml)
    return path, len(sel)

# ---- generate (filenames carry the dynamic dates) ----
v1 = write_visa_clearing("NAT",  f"VISA_CLR_NAT_{SRE}_{D1}.itf")
v2 = write_visa_clearing("INTL", f"VISA_CLR_INTL_{SRE}_{D1}.itf")
t1 = write_thredd(f"THREDD_TXN_REPORT_{D1}.xml", lambda r: r["in_thredd_d1"], D1)
t2 = write_thredd(f"THREDD_TXN_REPORT_{D2}.xml", lambda r: r["in_thredd_d2"], D2)

# Visa definitive net settlement (VSS settlement advice) - full-precision-rounded, the figure the
# issuer reconciles against. Distinct from the per-txn clearing sum by the rounding drift.
fn_net = f"VISA_SETTLEMENT_NET_{SRE}_{D1}.json"
with open(os.path.join(OUT, fn_net), "w", newline="\n") as f:
    json.dump({"sre": SRE, "settlement_date": D1, "currency": "GBP",
               "net_settlement_gbp": float(visa_net), "transaction_count": len(rows),
               "source": "VSS net settlement advice (definitive reconciliation figure)"}, f, indent=2)

# ===========================================================================
# Report
# ===========================================================================
def gp(x): return f"GBP {x:>10,.2f}"
print("="*72)
print(f"FILES WRITTEN  (D1/reconciled-day = {D1}, D2/catch-up = {D2})")
for p in (v1[0],v1[1],v2[0],v2[1],t1[0],t2[0],os.path.join(OUT,fn_net)):
    print("  ", os.path.basename(p))
print(f"  Thredd Day-1 rows: {t1[1]}   Thredd Day-2 rows: {t2[1]}   Visa Day-1 rows: {len(rows)}")
print("="*72)
print("STEP 1  Normalise both sides -> match on ARN")
print(f"  Visa Day-1 net settlement (definitive) : {gp(visa_net)}")
print(f"  Thredd Day-1 report sum                : {gp(thredd_d1_total)}")
print(f"  RAW UNRECONCILED DIFFERENCE            : {gp(raw_diff)}")
print("-"*72)
print("STEPS 2-3  Timing / cutoff (primary) -- late txns found in Thredd DAY-2 file")
for r in rows:
    if r["scen"]=="A":
        print(f"    {r['tid']:<9} {r['arn']}  {gp(r['visa_gbp'])}  (Visa D1 -> Thredd D2)")
print(f"  Explained by TIMING                    : {gp(timing_A)}")
print("-"*72)
print("STEP 4  FX rate-timing + rounding (second cause)")
for r in rows:
    if r["scen"]=="B":
        print(f"    {r['tid']:<9} Visa@settle {r['visa_gbp']:.2f} vs Thredd@txn {r['thredd_gbp']:.2f}"
              f" -> delta {r['visa_gbp']-r['thredd_gbp']:.2f}")
print(f"  Explained by FX RATE-TIMING            : {gp(fx_B)}")
print(f"  Explained by ROUNDING (sum vs net)     : {gp(rounding_C)}  "
      f"({abs(rounding_C)/visa_net*100:.4f}% of net, < 0.01% tolerance)")
print("-"*72)
print("STEP 5  Confirm scheme charges, classify, route")
print(f"  ISA scheme charges (equal both sides)  : {gp(isa_total)}  -> nets to 0.00 (NOT the cause)")
print(f"  TRUE RESIDUAL routed to analyst        : {gp(residual_E)}")
for r in rows:
    if r["scen"]=="E":
        print(f"    {r['tid']:<9} {r['arn']}  {gp(r['visa_gbp'])}  (in Visa, absent from Thredd D1 AND D2)")
print("-"*72)
check = timing_A + fx_B + rounding_C + residual_E
print(f"  CHECK  timing+FX+rounding+residual = {gp(check)}  vs raw {gp(raw_diff)}  "
      f"{'OK' if check==raw_diff else 'MISMATCH'}")
print("="*72)
