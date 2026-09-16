#!/usr/bin/env python3
"""Offline fixture preview for BTC15 mobile dashboard candidate.

NO NETWORK | FIXTURE DATA ONLY | PRESENTATION ONLY | NO ORDERS

Builds a self-contained HTML page from the frozen scalp UI fixtures and mobile
view-model. It is intentionally separate from the live V14/V15 dashboard and is
used only for deterministic phone/tablet visual QA.
"""
from __future__ import annotations

from html import escape
import json
from pathlib import Path

from btc15_mobile_dashboard_view_model_v1 import build_mobile_dashboard_view_model
from btc15_scalp_ui_state_fixtures_v1 import FIXTURES

VERSION = "BTC15_DASHBOARD_V15_FIXTURE_PREVIEW"
OUT = Path("/tmp/BTC15_DASHBOARD_V15_FIXTURE_PREVIEW.html")


def combined_for_fixture(name: str) -> dict:
    # Keep FINAL/EARLY stable so the preview isolates scalp/layout transitions.
    # This is deterministic fixture data, never a live signal.
    return {
        "contract": "KXBTC15M-FIXTURE",
        "canonical_seconds_left": 600.0,
        "up_bid": .44,
        "up_ask": .45,
        "down_bid": .55,
        "down_ask": .56,
        "early": {
            "state": "QUALIFIED" if name in {"ACTIVE_IDEAL", "PROTECT_PULLBACK"} else "PASS",
            "side": "UP" if name in {"ACTIVE_IDEAL", "PROTECT_PULLBACK"} else None,
            "ask": .34 if name in {"ACTIVE_IDEAL", "PROTECT_PULLBACK"} else None,
            "fair": .78 if name in {"ACTIVE_IDEAL", "PROTECT_PULLBACK"} else None,
            "edge": .44 if name in {"ACTIVE_IDEAL", "PROTECT_PULLBACK"} else None,
        },
        "final": {
            "state": "LOCK" if name == "EXIT" else "WATCH",
            "side": "UP" if name == "EXIT" else None,
            "fair": .94 if name == "EXIT" else None,
        },
    }


def preview_models() -> dict[str, dict]:
    return {
        name: build_mobile_dashboard_view_model(combined_for_fixture(name), fixture)
        for name, fixture in FIXTURES.items()
    }


def build_html() -> str:
    models = preview_models()
    payload = json.dumps(models, separators=(",", ":"), sort_keys=True).replace("</", "<\\/")
    first = next(iter(models))
    buttons = "".join(
        f'<button type="button" data-fixture="{escape(name)}">{escape(name.replace("_", " "))}</button>'
        for name in models
    )
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>BTC15 V15 Fixture Preview</title>
<style>
:root{{--bg:#071018;--card:#101b24;--line:#273744;--text:#eff6fb;--muted:#94a7b5;--good:#65e49a;--warn:#ffd166;--exit:#ff8193;--lock:#82b9ff;}}
*{{box-sizing:border-box}}
html,body{{margin:0;background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
body{{padding:max(12px,env(safe-area-inset-top)) max(12px,env(safe-area-inset-right)) max(18px,env(safe-area-inset-bottom)) max(12px,env(safe-area-inset-left))}}
.shell{{max-width:1180px;margin:0 auto}}
.top{{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px}}
.title{{font-size:18px;font-weight:900}}
.meta{{font-size:11px;color:var(--muted)}}
.fixture-bar{{display:flex;gap:7px;overflow:auto;padding:4px 0 12px;scrollbar-width:none}}
.fixture-bar button{{border:1px solid var(--line);background:#0b151d;color:var(--text);border-radius:999px;padding:8px 10px;white-space:nowrap;font-size:11px;font-weight:800}}
.fixture-bar button.active{{border-color:#7baee0;background:#16304a}}
.grid{{display:grid;grid-template-columns:minmax(0,1fr);gap:12px;align-items:stretch}}
.card{{border:1px solid var(--line);background:var(--card);border-radius:14px;padding:14px;min-width:0;overflow:hidden}}
.card-title{{font-size:11px;color:#a8bdd0;font-weight:900;letter-spacing:.35px;margin-bottom:9px}}
.action{{min-height:2.5em;font-size:20px;font-weight:950;line-height:1.15;display:flex;align-items:center}}
.primary{{min-height:2.6em;margin-top:5px;font-size:13px;font-weight:800;color:#cfdae2}}
.rows{{margin-top:10px}}
.row{{display:flex;justify-content:space-between;gap:10px;min-height:30px;align-items:center;border-top:1px solid rgba(255,255,255,.06);font-size:12px}}
.row span{{color:var(--muted)}}
.row strong{{text-align:right}}
.tone-positive .action{{color:var(--good)}} .tone-caution .action{{color:var(--warn)}} .tone-protect .action{{color:var(--warn)}} .tone-exit .action{{color:var(--exit)}} .tone-lock .action{{color:var(--lock)}}
.timer .primary{{font-size:35px;font-weight:950;font-variant-numeric:tabular-nums;min-height:auto}}
.safe{{margin-top:12px;text-align:center;color:#6f8494;font-size:10px}}
@media(min-width:768px) and (max-width:1180px){{
 .grid{{grid-template-columns:repeat(2,minmax(0,1fr));grid-template-areas:"final final" "early timer" "scalp scalp" "flip flip";gap:14px}}
 #FINAL_OUTCOME{{grid-area:final}} #EARLY_OPPORTUNITY{{grid-area:early}} #CONTRACT_TIME_LEFT{{grid-area:timer}} #SCALP_OPPORTUNITY{{grid-area:scalp}} #FLIP_RISK{{grid-area:flip}}
}}
@media(min-width:1181px){{
 .grid{{grid-template-columns:minmax(0,1.2fr) minmax(0,.8fr);grid-template-areas:"final early" "timer scalp" "flip flip";gap:14px}}
 #FINAL_OUTCOME{{grid-area:final}} #EARLY_OPPORTUNITY{{grid-area:early}} #CONTRACT_TIME_LEFT{{grid-area:timer}} #SCALP_OPPORTUNITY{{grid-area:scalp}} #FLIP_RISK{{grid-area:flip}}
}}
</style>
</head>
<body>
<div class="shell">
 <div class="top"><div><div class="title">BTC 15 MIN · V15 FIXTURE PREVIEW</div><div class="meta">OFFLINE · FIXTURE DATA · NO ORDERS</div></div><div class="meta" id="fixtureName"></div></div>
 <div class="fixture-bar">{buttons}</div>
 <main class="grid" id="grid"></main>
 <div class="safe">SIGNAL ONLY · MANUAL EXECUTION · FIXTURE PREVIEW · NO ORDERS</div>
</div>
<script type="application/json" id="fixtureData">{payload}</script>
<script>
(()=>{{
 'use strict';
 const DATA=JSON.parse(document.getElementById('fixtureData').textContent);
 const ORDER=['FINAL_OUTCOME','EARLY_OPPORTUNITY','CONTRACT_TIME_LEFT','SCALP_OPPORTUNITY','FLIP_RISK'];
 const esc=s=>String(s??'—').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
 function card(c){{
   const rows=(c.rows||[]).map(r=>`<div class="row"><span>${{esc(r.label)}}</span><strong>${{esc(r.value)}}</strong></div>`).join('');
   const timer=c.id==='CONTRACT_TIME_LEFT'?' timer':'';
   return `<section class="card tone-${{esc(c.tone||'neutral')}}${{timer}}" id="${{esc(c.id)}}"><div class="card-title">${{esc(c.title)}}</div><div class="action">${{esc(c.action||c.primary||'—')}}</div>${{c.action?`<div class="primary">${{esc(c.primary||'—')}}</div>`:''}}<div class="rows">${{rows}}</div></section>`;
 }}
 function render(name){{
   const m=DATA[name]; if(!m)return;
   document.getElementById('fixtureName').textContent=name.replaceAll('_',' ');
   document.getElementById('grid').innerHTML=ORDER.map(id=>card(m.cards[id])).join('');
   document.querySelectorAll('[data-fixture]').forEach(b=>b.classList.toggle('active',b.dataset.fixture===name));
 }}
 document.querySelectorAll('[data-fixture]').forEach(b=>b.addEventListener('click',()=>render(b.dataset.fixture)));
 render({json.dumps(first)});
}})();
</script>
</body>
</html>'''


def build_preview(path: Path = OUT) -> Path:
    text = build_html()
    path.write_text(text, encoding="utf-8")
    return path


if __name__ == "__main__":
    p = build_preview()
    print(f"{VERSION} | {p} | OFFLINE FIXTURES | NO ORDERS")
