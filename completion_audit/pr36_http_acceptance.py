import datetime as dt,hashlib,json,math,urllib.request,urllib.parse
BASE="https://btc-15min-bot-production.up.railway.app"
DEP="f82466d0-70ab-4779-a0fd-58832ad31513"
WEIGHTS="95fc4e893c9032f29b9732d03c4a2e0cd62755ba93b36106a1d0c8c094520ba6"
ARTIFACT="1bf10e755fc81584bab3c3682b16103353f84582c27bb003664de883e7e7c816"
START="2026-09-24T19:54:18.990766+00:00"
END="2026-09-24T21:15:00+00:00"
def utc(s): return dt.datetime.fromisoformat(s.replace("Z","+00:00"))
def get(url):
 with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"BTC15-read-only-PR36-acceptance","Accept-Encoding":"identity"}),timeout=20) as r:
  body=r.read(1048577)
  assert len(body)<=1048576,"response over bounded limit"
  return dict(r.headers),body
health=json.loads(get(BASE+"/health")[1])
manifest=json.loads(get(BASE+"/research/fair-input-manifest")[1])
assert manifest["serving_deployment"]==DEP
assert manifest["signal_only"] is True and manifest["orders"] is False
assert manifest["size_bytes"]<=16*1048576,"journal requires a registered larger bounded pass"
offset=4405306;ranges=[];rows=[];old=0;after=0
while offset<manifest["size_bytes"]:
 query=urllib.parse.urlencode(dict(identity=manifest["identity"],offset=offset,limit=1048576))
 headers,body=get(BASE+"/research/fair-input-export?"+query)
 h={k.lower():v for k,v in headers.items()}
 assert h["x-btc15-identity"]==manifest["identity"]
 assert int(h["x-range-offset"])==offset
 digest=hashlib.sha256(body).hexdigest()
 assert digest==h["x-range-sha256"]
 nxt=int(h["x-range-next-offset"]);assert nxt==offset+len(body)
 ranges.append(dict(offset=offset,next_offset=nxt,sha256=digest,records=int(h["x-range-records"])))
 if not body:break
 for line in body.splitlines():
  row=json.loads(line);decision=utc(row["decision_utc"])
  if decision<utc(START):old+=1;continue
  if decision>=utc(END):after+=1;continue
  assert row["schema"]=="BTC15_FAIR_INPUT_V1"
  assert row["signal_only"] is True and row["orders"] is False
  assert utc(row["btc_source_utc"])<=utc(row["btc_observed_utc"])<=decision
  assert row["weights_sha256"]==WEIGHTS and row["artifact_sha256"]==ARTIFACT
  assert all(math.isfinite(v) for v in row["features"].values())
  rows.append(row)
 offset=nxt
summary=dict(schema="BTC15_PR36_HTTP_ACCEPTANCE_V1",checked_utc=dt.datetime.now(dt.timezone.utc).isoformat(),serving_deployment=DEP,
 health=health,journal_identity=manifest["identity"],journal_snapshot_bytes=manifest["size_bytes"],ranges=ranges,
 old_rows_excluded=old,after_validation_excluded=after,corrected_input_frames=len(rows),first_corrected_decision=rows[0]["decision_utc"] if rows else None,
 last_corrected_decision=rows[-1]["decision_utc"] if rows else None,causal_clocks_pass=True,weights_match=True,signal_only=True,orders=False,
 warning="Input integrity only, includes warmup; no outcomes, fitting or performance claim")
contracts={}
for row in rows:
 c=contracts.setdefault(row["ticker"],dict(count=0,targets=set(),first=row["decision_utc"],last=None))
 c["count"]+=1;c["targets"].add(row["target"]);c["last"]=row["decision_utc"]
for c in contracts.values():
 assert len(c["targets"])==1,"fixed target changed";c["targets"]=sorted(c["targets"])
summary["contracts"]=contracts
times=[utc(r["decision_utc"]) for r in rows]
summary["max_input_gap_seconds"]=max(((b-a).total_seconds() for a,b in zip(times,times[1:])),default=None)
summary["btc_source_age_max_seconds"]=max(((utc(r["decision_utc"])-utc(r["btc_source_utc"])).total_seconds() for r in rows),default=None)
summary["incremental_resume_offset"]=4405306
print("PR36_HTTP_ACCEPTANCE "+json.dumps(summary,separators=(",",":")))
