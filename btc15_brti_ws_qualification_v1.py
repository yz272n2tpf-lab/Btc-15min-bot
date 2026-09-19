#!/usr/bin/env python3
"""Read-only Kalshi BRTI WebSocket qualification probe. SIGNAL ONLY. NO ORDERS."""
import asyncio,base64,json,os,time
from decimal import Decimal,InvalidOperation
import websockets
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import padding

URL="wss://external-api-ws.kalshi.com/trade-api/ws/v2"; PATH="/trade-api/ws/v2"
KEY=os.environ["KALSHI_KEY_ID"].strip()
PRIV=serialization.load_pem_private_key(base64.b64decode(os.environ["KALSHI_PRIVATE_KEY_B64"].strip()),password=None)

def headers():
    ts=str(int(time.time()*1000)); msg=ts+"GET"+PATH
    sig=PRIV.sign(msg.encode(),padding.PSS(mgf=padding.MGF1(hashes.SHA256()),salt_length=padding.PSS.DIGEST_LENGTH),hashes.SHA256())
    return {"KALSHI-ACCESS-KEY":KEY,"KALSHI-ACCESS-SIGNATURE":base64.b64encode(sig).decode(),"KALSHI-ACCESS-TIMESTAMP":ts}

async def run():
    n=dup=ooo=wrong=bad=0; last_ts=None; started=time.time(); sid=None\n    forced_after=int(os.getenv("BRTI_WS_FORCE_DISCONNECT_AFTER_TICKS","0")); forced=False
    print("BRTI WS QUAL START | READ/SUBSCRIBE ONLY | NO ORDERS",flush=True)
    async with websockets.connect(URL,additional_headers=headers(),ping_interval=20,ping_timeout=20,max_queue=2048) as ws:
        await ws.send(json.dumps({"id":1,"cmd":"subscribe","params":{"channels":["cfbenchmarks_value"],"index_ids":["BRTI"]}}))
        while time.time()-started < float(os.getenv("BRTI_WS_QUAL_SECONDS","900")):
            raw=await asyncio.wait_for(ws.recv(),timeout=15); recv_ms=int(time.time()*1000)
            try:x=json.loads(raw)
            except Exception: bad+=1;continue
            t=x.get("type")
            if t=="error": raise RuntimeError("Kalshi WS error "+json.dumps(x,sort_keys=True))
            if t=="subscribed":
                sid=x.get("msg",{}).get("sid",x.get("sid"));print("BRTI WS SUBSCRIBED | sid=%s | NO ORDERS"%sid,flush=True)
                if sid is not None:
                    await ws.send(json.dumps({"id":2,"cmd":"update_subscription","params":{"sid":sid,"action":"indexlist"}}))
                continue
            if t=="cfbenchmarks_value_indexlist":
                ids=x.get("msg",{}).get("index_ids",[]);print("BRTI WS INDEXLIST | BRTI_AVAILABLE=%s | count=%s | NO ORDERS"%("BRTI" in ids,len(ids)),flush=True);continue
            if t!="cfbenchmarks_value": continue
            m=x.get("msg",{})
            if m.get("index_id")!="BRTI": wrong+=1;continue
            try:
                d=json.loads(m["data"]); source_ms=int(d["time"]); val=Decimal(str(d["value"]))
                if d.get("id")!="BRTI" or not val.is_finite() or val<=0: raise ValueError("invalid BRTI payload")
            except (KeyError,ValueError,TypeError,InvalidOperation,json.JSONDecodeError): bad+=1;continue
            if source_ms>recv_ms+1000: bad+=1;continue
            if last_ts is not None:
                if source_ms==last_ts: dup+=1
                elif source_ms<last_ts: ooo+=1
            if last_ts is None or source_ms>last_ts:last_ts=source_ms
            n+=1; age=recv_ms-source_ms\n            if forced_after and not forced and n >= forced_after:\n                forced=True\n                print(f"BRTI WS FORCED DISCONNECT | after_ticks={n} | last_source_ms={source_ms} | EXPECT FAIL-CLOSED UNTIL NEW CONNECTION | NO ORDERS",flush=True)\n                await ws.close(code=1000,reason="qualification forced reconnect test")\n                raise RuntimeError("QUAL_FORCED_DISCONNECT")
            if n<=5 or n%30==0: print(f"BRTI WS TICK | n={n} | value={val} | source_ms={source_ms} | age_ms={age} | dup={dup} | ooo={ooo} | bad={bad} | NO ORDERS",flush=True)
    print(f"BRTI_WS_QUAL_COMPLETE | ticks={n} | dup={dup} | ooo={ooo} | wrong={wrong} | bad={bad} | NO ORDERS",flush=True)
if __name__=="__main__": asyncio.run(run())
