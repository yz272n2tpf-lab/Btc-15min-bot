#!/usr/bin/env python3
"""Offline fixture preview for BTC15 mobile dashboard candidate.

NO NETWORK | FIXTURE DATA ONLY | PRESENTATION ONLY | NO ORDERS

Builds a self-contained HTML page from frozen scalp UI fixtures and mobile
view-model V5. It is intentionally separate from the live V14/V15 dashboard and
is used only for deterministic phone/tablet visual QA.
"""
from __future__ import annotations

import copy
from html import escape
import json
from pathlib import Path

import btc15_mobile_dashboard_view_model_v3 as v3
import btc15_mobile_dashboard_view_model_v5 as v5
from btc15_scalp_ui_state_fixtures_v1 import FIXTURES

VERSION = "BTC15_DASHBOARD_V15_FIXTURE_PREVIEW_V5_ENTRY_CONTEXT"
OUT = Path("/tmp/BTC15_DASHBOARD_V15_FIXTURE_PREVIEW.html")

TIME_FIXTURES = {
    "TIME_5M_CAUTION": 300.0,
    "TIME_3M_GUARD": 180.0,
    "ROLLOVER": 0.0,
}
ROLLOVER_HISTORY_FIXTURE = "CONTRACT_ROLLOVER_HISTORY"
SAME_CONTRACT_SCAN_FIXTURE = "SCALP_1_COMPLETE_SCAN_2"
SAME_CONTRACT_ACTIVE_FIXTURE = "SCALP_1_COMPLETE_SCALP_2_ACTIVE"
GOOD_BLIP_PROTECT_FIXTURE = "GOOD_ENTRY_TELEMETRY_BLIP_PROTECT"
TRACKING_LATER_PROTECT_FIXTURE = "DONT_CHASE_LATER_PROTECT"


def combined_for_fixture(name: str, *, contract: str | None = None, seconds_left: float | None = None) -> dict:
    if seconds_left is None:
        if name == ROLLOVER_HISTORY_FIXTURE:
            seconds_left = 899.0
        elif name in {SAME_CONTRACT_SCAN_FIXTURE, SAME_CONTRACT_ACTIVE_FIXTURE}:
            seconds_left = 240.0 if name == SAME_CONTRACT_SCAN_FIXTURE else 220.0
        elif name in {GOOD_BLIP_PROTECT_FIXTURE, TRACKING_LATER_PROTECT_FIXTURE}:
            seconds_left = 480.0
        else:
            seconds_left = TIME_FIXTURES.get(name, 600.0)
    if contract is None:
        contract = "KXBTC15M-FIXTURE-NEW" if name == ROLLOVER_HISTORY_FIXTURE else "KXBTC15M-FIXTURE"
    return {
        "contract": contract,
        "canonical_seconds_left": seconds_left,
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


def _clone_ui(name: str, **updates) -> dict:
    out = copy.deepcopy(FIXTURES[name])
    out.update(updates)
    return out


def _exit_one_ui() -> dict:
    return _clone_ui("EXIT", opportunity_index=1, serial_opportunities_completed=1, scanning_for_next=False)


def _previous_rollover_model() -> dict:
    old_combined = combined_for_fixture("EXIT", contract="KXBTC15M-FIXTURE-OLD", seconds_left=1.0)
    return v3.build_mobile_dashboard_view_model(old_combined, _exit_one_ui())


def _previous_same_contract_exit_model() -> dict:
    old_combined = combined_for_fixture("EXIT", contract="KXBTC15M-FIXTURE", seconds_left=250.0)
    return v3.build_mobile_dashboard_view_model(old_combined, _exit_one_ui())


def _scan_two_ui() -> dict:
    return _clone_ui("WAIT", opportunity_index=None, serial_opportunities_completed=1, scanning_for_next=True)


def _active_two_ui() -> dict:
    return _clone_ui("ACTIVE_IDEAL", opportunity_index=2, serial_opportunities_completed=1, scanning_for_next=False)


def _previous_good_entry_model() -> dict:
    return v5.build_mobile_dashboard_view_model(
        combined_for_fixture("ACTIVE_IDEAL", seconds_left=520.0),
        _clone_ui("ACTIVE_IDEAL", opportunity_index=1, serial_opportunities_completed=0, scanning_for_next=False),
    )


def _good_entry_blip_protect_ui() -> dict:
    return _clone_ui(
        "PROTECT_PULLBACK",
        opportunity_index=1,
        serial_opportunities_completed=0,
        scanning_for_next=False,
        entry_guidance={"tier": "UNAVAILABLE"},
        entry_ask_c=None,
    )


def _previous_tracking_model() -> dict:
    return v5.build_mobile_dashboard_view_model(
        combined_for_fixture("ACTIVE_CAUTION_ABOVE_50", seconds_left=520.0),
        _clone_ui("ACTIVE_CAUTION_ABOVE_50", opportunity_index=1, serial_opportunities_completed=0, scanning_for_next=False),
    )


def _tracking_later_protect_ui() -> dict:
    return _clone_ui(
        "PROTECT_PULLBACK",
        opportunity_index=1,
        serial_opportunities_completed=0,
        scanning_for_next=False,
        entry_guidance={"tier": "GOOD_36_50"},
        entry_ask_c=44.0,
    )


def preview_models() -> dict[str, dict]:
    models = {
        name: v5.build_mobile_dashboard_view_model(combined_for_fixture(name), fixture)
        for name, fixture in FIXTURES.items()
    }
    wait_fixture = FIXTURES["WAIT"]
    for name in TIME_FIXTURES:
        models[name] = v5.build_mobile_dashboard_view_model(combined_for_fixture(name), wait_fixture)
    models[ROLLOVER_HISTORY_FIXTURE] = v5.build_mobile_dashboard_view_model(
        combined_for_fixture(ROLLOVER_HISTORY_FIXTURE),
        wait_fixture,
        previous_model=_previous_rollover_model(),
    )
    previous_same = _previous_same_contract_exit_model()
    models[SAME_CONTRACT_SCAN_FIXTURE] = v5.build_mobile_dashboard_view_model(
        combined_for_fixture(SAME_CONTRACT_SCAN_FIXTURE),
        _scan_two_ui(),
        previous_model=previous_same,
    )
    models[SAME_CONTRACT_ACTIVE_FIXTURE] = v5.build_mobile_dashboard_view_model(
        combined_for_fixture(SAME_CONTRACT_ACTIVE_FIXTURE),
        _active_two_ui(),
        previous_model=previous_same,
    )
    models[GOOD_BLIP_PROTECT_FIXTURE] = v5.build_mobile_dashboard_view_model(
        combined_for_fixture(GOOD_BLIP_PROTECT_FIXTURE),
        _good_entry_blip_protect_ui(),
        previous_model=_previous_good_entry_model(),
    )
    models[TRACKING_LATER_PROTECT_FIXTURE] = v5.build_mobile_dashboard_view_model(
        combined_for_fixture(TRACKING_LATER_PROTECT_FIXTURE),
        _tracking_later_protect_ui(),
        previous_model=_previous_tracking_model(),
    )
    return models


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
.timer .action{{font-size:35px;font-weight:950;font-variant-numeric:tabular-nums;min-height:auto}}
.timer .primary{{min-height:1.5em;color:#cfdae2}}
.history-slot{{min-height:58px;margin-top:12px;border:1px solid rgba(148,167,181,.18);border-radius:12px;padding:10px 12px;color:var(--muted);display:flex;flex-direction:column;justify-content:center}}
.history-slot.hidden{{visibility:hidden}}
.history-title{{font-size:11px;font-weight:900;letter-spacing:.3px}}
.history-detail{{font-size:11px;margin-top:4px}}
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
 <aside class="history-slot hidden" id="historySlot" aria-label="Previous scalp history"><div class="history-title" id="historyTitle"></div><div class="history-detail" id="historyDetail"></div></aside>
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
   const mainAction=c.action||c.primary||'—';
   const secondary=c.action?(c.primary||''):(c.status_label||'');
   return `<section class="card tone-${{esc(c.tone||'neutral')}}${{timer}}" id="${{esc(c.id)}}"><div class="card-title">${{esc(c.title)}}</div><div class="action">${{esc(mainAction)}}</div>${{secondary?`<div class="primary">${{esc(secondary)}}</div>`:''}}<div class="rows">${{rows}}</div></section>`;
 }}
 function renderHistory(h){{
   const slot=document.getElementById('historySlot');
   const visible=!!(h&&h.visible&&h.historical_only===true&&h.actionable===false);
   slot.classList.toggle('hidden',!visible);
   document.getElementById('historyTitle').textContent=visible?(h.headline||'PREVIOUS SCALP'):'';
   document.getElementById('historyDetail').textContent=visible?(h.detail||'Historical context only.'):'';
 }}
 function render(name){{
   const m=DATA[name]; if(!m)return;
   document.getElementById('fixtureName').textContent=name.replaceAll('_',' ');
   document.getElementById('grid').innerHTML=ORDER.map(id=>card(m.cards[id])).join('');
   renderHistory(m.scalp_history_slot);
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
