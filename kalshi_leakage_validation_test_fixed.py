from pathlib import Path
import re, numpy as np, pandas as pd
from zoneinfo import ZoneInfo
from sklearn.ensemble import RandomForestClassifier

CAL=Path("brti_calibration_results.csv"); BTC=Path("btc_35d_live_cache.csv")
print("=== KALSHI FUTURE-DATA / LEAKAGE VALIDATION ===")
print("bot.py changed: NO | Scalp changed: NO | Orders: NO")

cal=pd.read_csv(CAL); btc=pd.read_csv(BTC)
btc["Datetime"]=pd.to_datetime(btc["Datetime"],utc=True,errors="coerce")
btc=btc.dropna(subset=["Datetime"]).sort_values("Datetime").set_index("Datetime")
for c in ["Open","High","Low","Close","Volume"]:
    if c in btc: btc[c]=pd.to_numeric(btc[c],errors="coerce")

months={m:i+1 for i,m in enumerate(["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"])}
def times(t):
    m=re.search(r"KXBTC15M-(\d{2})([A-Z]{3})(\d{2})(\d{2})(\d{2})-",str(t).upper())
    if not m:return pd.NaT,pd.NaT
    y,mo,d,h,mi=m.groups()
    wall=pd.Timestamp(year=2000+int(y),month=months[mo],day=int(d),hour=int(h),minute=int(mi))
    close=wall.tz_localize(ZoneInfo("America/New_York")).tz_convert("UTC")
    return close-pd.Timedelta(minutes=15),close

z=cal["ticker"].map(times); cal["start"]=[x[0] for x in z]; cal["close"]=[x[1] for x in z]
cal["target_brti"]=pd.to_numeric(cal["target_brti"],errors="coerce")
cal["final_brti"]=pd.to_numeric(cal["final_brti"],errors="coerce")
cal["y"]=cal["result"].astype(str).str.lower().map({"yes":1,"no":0})
cal=cal.dropna(subset=["start","target_brti","final_brti","y"]).sort_values("start").reset_index(drop=True)
label_ok=((cal.final_brti>=cal.target_brti).astype(int)==cal.y.astype(int))

def px(ts):
    i=btc.index.searchsorted(ts,side="right")-1
    if i<0:return np.nan,pd.NaT
    ti=btc.index[i]
    if ts-ti>pd.Timedelta(minutes=2):return np.nan,pd.NaT
    return float(btc.iloc[i]["Close"]),ti

def snap(r,e):
    s=r.start; cut=s+pd.Timedelta(minutes=e); target=float(r.target_brti)
    vals=[px(s),px(cut),px(cut-pd.Timedelta(minutes=1)),px(cut-pd.Timedelta(minutes=3)),px(cut-pd.Timedelta(minutes=5))]
    if any(pd.isna(v[0]) for v in vals):return None
    ps,p1,pm1,pm3,pm5=[v[0] for v in vals]; used=[v[1] for v in vals]
    w=btc.loc[(btc.index>cut-pd.Timedelta(minutes=5))&(btc.index<=cut)]
    if len(w)<3:return None
    if max(used+[w.index.max()])>cut:raise RuntimeError("FUTURE DATA DETECTED")
    closes=w.Close.dropna()
    if len(closes)<2:return None
    dist=p1-target
    return {"start":s,"cut":cut,"latest":max(used+[w.index.max()]),"y":int(r.y),
    "current_side":int(dist>=0),"dist_target":dist,"dist_target_pct":dist/target,"abs_dist":abs(dist),
    "dist_start":p1-ps,"dist_start_pct":(p1-ps)/ps,"move1":p1-pm1,"move3":p1-pm3,"move5":p1-pm5,
    "range5":float(w.High.max()-w.Low.min()),"vol5":float(closes.pct_change().std(ddof=0))}

features=["current_side","dist_target","dist_target_pct","abs_dist","dist_start","dist_start_pct","move1","move3","move5","range5","vol5"]
rows=[]
for e in [1,3,5,7,9,11]:
    items=[x for _,r in cal.iterrows() if (x:=snap(r,e)) is not None]
    if not items:
        raise RuntimeError(f"No snapshots parsed at elapsed minute {e}. Check ticker/time parsing.")
    df=pd.DataFrame(items).sort_values("start").reset_index(drop=True)
    tc=tn=c70=n70=c80=n80=0; chrono=True
    for a,b in [(0.5,0.6),(0.6,0.7),(0.7,0.8),(0.8,0.9),(0.9,1.0)]:
        tr=df.iloc[:int(len(df)*a)]; te=df.iloc[int(len(df)*a):int(len(df)*b)]
        if len(tr)<100 or te.empty:continue
        chrono &= tr.start.max()<te.start.min()
        m=RandomForestClassifier(n_estimators=400,max_depth=7,min_samples_leaf=8,class_weight="balanced",random_state=42,n_jobs=-1)
        m.fit(tr[features],tr.y); pred=m.predict(te[features]); conf=m.predict_proba(te[features]).max(axis=1); ok=pred==te.y.to_numpy()
        tc+=ok.sum();tn+=len(te)
        q=conf>=.70;c70+=ok[q].sum();n70+=q.sum()
        q=conf>=.80;c80+=ok[q].sum();n80+=q.sum()
    rows.append([e,len(df),int((df.latest>df.cut).sum()),chrono,tc/tn,c70/n70 if n70 else np.nan,int(n70),c80/n80 if n80 else np.nan,int(n80)])

res=pd.DataFrame(rows,columns=["minute","snapshots","future_rows","chronology_ok","accuracy","acc_70+","n_70+","acc_80+","n_80+"])
print("\n=== LEAKAGE CHECK RESULTS ===");print(res.to_string(index=False,float_format=lambda x:f"{x:.3f}"))
print("\n=== HARD CHECKS ===")
a=(res.future_rows==0).all(); b=res.chronology_ok.all(); c=label_ok.all()
print("Feature timestamps <= cutoff:","PASS" if a else "FAIL")
print("Walk-forward chronology:","PASS" if b else "FAIL")
print("Settlement-label consistency:","PASS" if c else "FAIL")
print("\nLEAKAGE AUDIT VERDICT:","PASS" if a and b and c else "FAIL")
print("No bot files modified.")
