#!/usr/bin/env python3
"""Offline frame-by-frame dashboard session replay preview.

NO NETWORK | FIXTURE DATA ONLY | PRESENTATION QA | NO ORDERS
"""
from __future__ import annotations

from html import escape
import json
from pathlib import Path

from btc15_dashboard_session_sequence_fixtures_v1 import SEQUENCES

VERSION = "BTC15_DASHBOARD_V15_SEQUENCE_PREVIEW_V1"
OUT = Path("/tmp/BTC15_DASHBOARD_V15_SEQUENCE_PREVIEW.html")


def build_html() -> str:
    payload = json.dumps(SEQUENCES, separators=(",", ":"), sort_keys=True).replace("</", "<\\/")
    sequence_buttons = "".join(
        f'<button type="button" data-seq="{escape(name)}">{escape(name.replace("_", " "))}</button>'
        for name in SEQUENCES
    )
    first = next(iter(SEQUENCES))
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>BTC15 V15 Session Replay</title>
<style>
:root{{--bg:#071018;--card:#101b24;--line:#273744;--text:#eff6fb;--muted:#94a7b5;--good:#65e49a;--warn:#ffd166;--bad:#ff8193;--blue:#82b9ff;}}
*{{box-sizing:border-box}}
html,body{{margin:0;background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
body{{padding:max(12px,env(safe-area-inset-top)) max(12px,env(safe-area-inset-right)) max(18px,env(safe-area-inset-bottom)) max(12px,env(safe-area-inset-left))}}
.shell{{max-width:1080px;margin:0 auto}}
.top{{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}}
.title{{font-size:19px;font-weight:950}}
.meta{{font-size:11px;color:var(--muted);margin-top:3px}}
.bar{{display:flex;gap:7px;overflow:auto;padding:14px 0 9px;scrollbar-width:none}}
button{{border:1px solid var(--line);background:#0b151d;color:var(--text);border-radius:999px;padding:8px 10px;white-space:nowrap;font-size:11px;font-weight:850}}
button.active{{border-color:#7baee0;background:#16304a}}
.frames{{display:flex;gap:7px;overflow:auto;padding:0 0 12px}}
.frames button{{border-radius:10px}}
.status{{min-height:34px;display:flex;flex-wrap:wrap;gap:7px;align-items:center;margin-bottom:10px}}
.badge{{border:1px solid var(--line);border-radius:999px;padding:5px 8px;font-size:10px;font-weight:900;color:var(--muted)}}
.badge.good{{color:var(--good)}} .badge.warn{{color:var(--warn)}} .badge.bad{{color:var(--bad)}}
.grid{{display:grid;grid-template-columns:1fr;gap:10px}}
.card{{border:1px solid var(--line);background:var(--card);border-radius:14px;padding:14px;min-width:0}}
.card-title{{font-size:10px;letter-spacing:.35px;color:#a8bdd0;font-weight:900;margin-bottom:8px}}
.big{{font-size:21px;line-height:1.15;font-weight:950;min-height:2.3em;display:flex;align-items:center}}
.sub{{font-size:12px;color:#c7d5df;font-weight:750;min-height:2.5em}}
.timer .big{{font-size:36px;font-variant-numeric:tabular-nums;min-height:auto}}
.rows{{margin-top:8px}}
.row{{display:flex;justify-content:space-between;gap:12px;border-top:1px solid rgba(255,255,255,.06);min-height:29px;align-items:center;font-size:11px}}
.row span{{color:var(--muted)}} .row strong{{text-align:right}}
.history{{min-height:58px;margin-top:10px;border:1px solid rgba(148,167,181,.18);border-radius:12px;padding:10px 12px;color:var(--muted)}}
.safe{{margin-top:12px;text-align:center;color:#6f8494;font-size:10px}}
@media(min-width:760px){{.grid{{grid-template-columns:1fr 1fr;grid-template-areas:"final timer" "scalp scalp" "context history"}}#finalCard{{grid-area:final}}#timerCard{{grid-area:timer}}#scalpCard{{grid-area:scalp}}#contextCard{{grid-area:context}}#historyCard{{grid-area:history}}}}
</style>
</head>
<body>
<div class="shell">
 <div class="top"><div><div class="title">BTC 15 MIN · SESSION REPLAY</div><div class="meta">OFFLINE FIXTURES · FRAME-BY-FRAME · NO ORDERS</div></div><div class="meta" id="frameMeta"></div></div>
 <div class="bar">{sequence_buttons}</div>
 <div class="frames" id="frameButtons"></div>
 <div class="status" id="status"></div>
 <main class="grid">
  <section class="card" id="finalCard"><div class="card-title">FINAL OUTCOME</div><div class="big" id="finalAction"></div><div class="sub">Current FINAL remains authoritative even when SCALP is quarantined.</div></section>
  <section class="card timer" id="timerCard"><div class="card-title">CONTRACT TIME LEFT</div><div class="big" id="timer"></div><div class="sub">Single canonical timer.</div></section>
  <section class="card" id="scalpCard"><div class="card-title">SCALP OPPORTUNITY</div><div class="big" id="scalpAction"></div><div class="sub" id="scalpPrimary"></div><div class="rows"><div class="row"><span>Lifecycle</span><strong id="lifecycle"></strong></div><div class="row"><span>Opportunity</span><strong id="opp"></strong></div></div></section>
  <section class="card" id="contextCard"><div class="card-title">PRESENTATION CONTEXT</div><div class="big" id="entryContext"></div><div class="rows"><div class="row"><span>Fail Closed</span><strong id="failClosed"></strong></div><div class="row"><span>Quarantined</span><strong id="quarantine"></strong></div><div class="row"><span>Reason</span><strong id="reason"></strong></div></div></section>
  <section class="card" id="historyCard"><div class="card-title">LAST COMPLETED SCALP · HISTORY ONLY</div><div class="history" id="history"></div></section>
 </main>
 <div class="safe">SIGNAL ONLY · MANUAL EXECUTION · OFFLINE REPLAY · NO ORDERS</div>
</div>
<script type="application/json" id="sequenceData">{payload}</script>
<script>
(()=>{{
'use strict';
const DATA=JSON.parse(document.getElementById('sequenceData').textContent);
let currentSeq={json.dumps(first)},currentFrame=0;
const esc=s=>String(s??'—');
function badge(text,cls=''){{return `<span class="badge ${{cls}}">${{text}}</span>`}}
function renderFrame(){{
 const frames=DATA[currentSeq]||[]; const f=frames[currentFrame]||{{}};
 document.getElementById('frameMeta').textContent=`${{currentSeq.replaceAll('_',' ')}} · ${{currentFrame+1}}/${{frames.length}}`;
 document.getElementById('finalAction').textContent=esc(f.final_action);
 document.getElementById('timer').textContent=esc(f.timer);
 document.getElementById('scalpAction').textContent=esc(f.scalp_action);
 document.getElementById('scalpPrimary').textContent=esc(f.scalp_primary);
 document.getElementById('lifecycle').textContent=esc(f.scalp_lifecycle);
 document.getElementById('opp').textContent=f.opportunity_index??'—';
 document.getElementById('entryContext').textContent=esc(f.entry_context);
 document.getElementById('failClosed').textContent=f.source_fail_closed?'YES':'NO';
 document.getElementById('quarantine').textContent=f.scalp_quarantined?'YES':'NO';
 document.getElementById('reason').textContent=esc(f.quarantine_reason);
 document.getElementById('history').textContent=f.history_visible?esc(f.history_headline):'No completed scalp history visible.';
 let s='';
 s+=badge(f.source_fail_closed?'SOURCE FAIL-CLOSED':'SOURCE HEALTHY',f.source_fail_closed?'bad':'good');
 s+=badge(f.scalp_quarantined?'SCALP FRAME QUARANTINED':'SCALP FRAME ACCEPTED',f.scalp_quarantined?'warn':'good');
 s+=badge('MANUAL POSITION NOT CONFIRMED'); s+=badge('NO ORDERS');
 document.getElementById('status').innerHTML=s;
 document.querySelectorAll('[data-frame]').forEach(b=>b.classList.toggle('active',Number(b.dataset.frame)===currentFrame));
}}
function renderSeq(name){{
 currentSeq=name; currentFrame=0;
 document.querySelectorAll('[data-seq]').forEach(b=>b.classList.toggle('active',b.dataset.seq===name));
 const frames=DATA[name]||[];
 document.getElementById('frameButtons').innerHTML=frames.map((f,i)=>`<button type="button" data-frame="${{i}}">${{i+1}} · ${{f.frame.replaceAll('_',' ')}}</button>`).join('');
 document.querySelectorAll('[data-frame]').forEach(b=>b.addEventListener('click',()=>{{currentFrame=Number(b.dataset.frame);renderFrame();}}));
 renderFrame();
}}
document.querySelectorAll('[data-seq]').forEach(b=>b.addEventListener('click',()=>renderSeq(b.dataset.seq)));
renderSeq(currentSeq);
}})();
</script>
</body>
</html>'''


def build_preview(path: Path = OUT) -> Path:
    path.write_text(build_html(), encoding="utf-8")
    return path


if __name__ == "__main__":
    p = build_preview()
    print(f"{VERSION} | {p} | OFFLINE SESSION REPLAY | NO ORDERS")
