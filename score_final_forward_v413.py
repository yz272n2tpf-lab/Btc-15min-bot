import csv, json, math, time, urllib.request, urllib.parse
from datetime import datetime, timezone

UNIFIED="kalshi_subminute_unified_v1_1.csv"
START=datetime.fromisoformat("2026-09-06T04:00:00+00:00")
END=datetime.fromisoformat("2026-09-06T18:00:00+00:00")
LIVE_BASE="https://external-api.kalshi.com/trade-api/v2/markets/"
HIST_BASE="https://external-api.kalshi.com/trade-api/v2/historical/markets/"

def num(x):
    try:return float(str(x).strip())
    except:return math.nan
def side(x):
    s=str(x or "").strip().upper()
    if s in {"UP","YES","Y","HIGHER","ABOVE","TRUE","1"}: return "UP"
    if s in {"DOWN","NO","N","LOWER","BELOW","FALSE","0"}: return "DOWN"
    return ""
def dt(x):
    try:
        d=datetime.fromisoformat(str(x).strip().replace("Z","+00:00"))
        if d.tzinfo is None:d=d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)
    except:return None
def fair(x):
    v=num(x)
    if math.isfinite(v) and v>1.5:v/=100.0
    return v
def fetch_market(ticker):
    q=urllib.parse.quote(ticker,safe="-")
    for base in (LIVE_BASE,HIST_BASE):
        try:
            req=urllib.request.Request(base+q,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
            with urllib.request.urlopen(req,timeout=15) as r:
                j=json.loads(r.read().decode())
            m=j.get("market",j)
            if isinstance(m,dict) and m.get("ticker"):
                return m
        except Exception:
            pass
    return None

rows=[]
with open(UNIFIED,newline="",encoding="utf-8-sig",errors="ignore") as f:
    for r in csv.DictReader(f):
        t=dt(r.get("timestamp_utc"))
        if t and START<=t<=END:
            rows.append(r)

contracts=sorted({str(r.get("contract","")).strip() for r in rows if str(r.get("contract","")).strip()})
calls={}
g={"rows":len(rows),"fair":0,"time":0,"gap":0,"range":0,"side":0,"qualified":0}

for r in rows:
    c=str(r.get("contract","")).strip()
    if not c or c in calls: continue
    pf=fair(r.get("preferred_fair"))
    ml=num(r.get("minutes_left"))
    gap=num(r.get("btc_gap"))
    ratio=num(r.get("dist_over_range5"))
    # Unified CSV is side-row based: it does not carry a preferred_side column.
    # Recover the preferred side from the row whose side_fair equals preferred_fair
    # (or from preferred_side_match when that logger flag is present).
    row_side=side(r.get("side"))
    sf=fair(r.get("side_fair"))
    pref_match=str(r.get("preferred_side_match","")).strip().lower() in {"1","true","yes","y"}
    ps=row_side if (pref_match or (row_side and math.isfinite(sf) and math.isfinite(pf) and abs(sf-pf) < 1e-9)) else ""
    target_side=side(r.get("current_target_side"))

    if math.isfinite(pf) and pf>=0.90:g["fair"]+=1
    else:continue
    if math.isfinite(ml) and ml<=8.0:g["time"]+=1
    else:continue
    need=75.0 if ml>6.0 else 50.0
    if math.isfinite(gap) and abs(gap)>=need:g["gap"]+=1
    else:continue
    if math.isfinite(ratio) and ratio>=1.0:g["range"]+=1
    else:continue
    if ps in {"UP","DOWN"} and target_side==ps:g["side"]+=1
    else:continue

    calls[c]={"side":ps,"minutes_left":ml,"fair":pf,"gap":gap,"ratio":ratio}
    g["qualified"]+=1

print("="*72)
print("V4.13 FRESH FINAL FORWARD SCORE — PRODUCTION WINNER")
print("="*72)
print("Observed contracts:",len(contracts))
print("Qualified FINAL calls:",len(calls))
print("Fetching official Kalshi truth for these exact unified contracts...")

official={}
fetch_errors=[]
for i,c in enumerate(contracts,1):
    m=fetch_market(c)
    if m:
        s=side(m.get("result"))
        if s:official[c]=s
    else:
        fetch_errors.append(c)
    if i%10==0 or i==len(contracts):
        print(f"  checked {i}/{len(contracts)}",end="\r",flush=True)
    time.sleep(0.03)
print()

scored=[]
for c,a in calls.items():
    if c in official:
        scored.append((c,a,official[c],a["side"]==official[c]))

n=len(scored); wins=sum(1 for x in scored if x[3])
times=sorted(x[1]["minutes_left"] for x in scored)
avg=sum(times)/n if n else 0
med=(times[n//2] if n%2 else (times[n//2-1]+times[n//2])/2) if n else 0

print("Official settled truth obtained:",len(official),"/",len(contracts))
print("Qualified settled calls:",n)
print("Correct:",wins)
print("Wrong:",n-wins)
print(f"Accuracy: {100*wins/n:.1f}%" if n else "Accuracy: N/A")
print(f"Coverage vs observed contracts: {100*n/len(contracts):.1f}%" if contracts else "Coverage: N/A")
print(f"Average time left: {avg:.2f} min")
print(f"Median time left: {med:.2f} min")
print("GATE DIAGNOSTICS:",g)
print("="*72)
for c,a,o,ok in scored:
    print(c,a["side"],"->",o,f'{a["minutes_left"]:.2f}m',f'fair {a["fair"]*100:.1f}%',"WIN" if ok else "LOSS")

if not calls:
    print("\nNO QUALIFIED CALLS. Diagnostic samples after range gate:")
    shown=0
    for r in rows:
        pf=fair(r.get("preferred_fair")); ml=num(r.get("minutes_left")); gap=num(r.get("btc_gap")); ratio=num(r.get("dist_over_range5"))
        if math.isfinite(pf) and pf>=.90 and math.isfinite(ml) and ml<=8 and math.isfinite(gap) and abs(gap)>=(75 if ml>6 else 50) and math.isfinite(ratio) and ratio>=1:
            print(" row_side=",repr(r.get("side"))," side_fair=",repr(r.get("side_fair"))," preferred_fair=",repr(r.get("preferred_fair"))," pref_match=",repr(r.get("preferred_side_match"))," target=",repr(r.get("current_target_side"))," gap=",gap)
            shown+=1
            if shown>=8:break
