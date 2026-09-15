#!/usr/bin/env python3
"""
BTC15 combined generalized SCALP in-layout dashboard UI V8.

SHADOW DISPLAY FIX ONLY | SIGNAL ONLY | NO ORDERS

V8 addresses the live iPad screenshot after V7:
- Main CONTRACT TIMER showed 14:02 while SCALP showed 14:07, indicating the
  V7 scoped text selector still fell back to bridge seconds instead of reading
  the visible countdown.
- SCALP showed WAIT · CONTRACT SYNC even though the generic V5/V7 UI collapsed
  several backend guard failures (contract alignment, source freshness, and
  integration readiness) into one misleading message.

V8 changes display diagnostics only. It does NOT alter SCALP qualification,
management thresholds, price handling, EARLY, FINAL, or order behavior.
"""
from pathlib import Path
import sys

import BTC15_DASHBOARD_COMBINED_SCALP_UI_V7 as v7

MARKER = "BTC15_COMBINED_SCALP_UI_V8_VISIBLE_TIMER_AND_GUARD_REASON"

OLD_LEFT = v7.NEW_LEFT
NEW_LEFT = r"""const left=usable?n(d.canonical_seconds_left):NaN; const mainClock=(()=>{const norm=x=>String(x||'').replace(/\s+/g,' ').trim();const fmt=x=>{const p=String(x||'').split(':');return p.length===2?`${p[0].padStart(2,'0')}:${p[1]}`:null;};const vis=e=>{try{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden';}catch(_){return false;}};const labels=[...document.querySelectorAll('body *')].filter(e=>vis(e)&&/CONTRACT TIMER/i.test(norm(e.textContent))).sort((a,b)=>norm(a.textContent).length-norm(b.textContent).length);const times=[...document.querySelectorAll('body *')].filter(e=>vis(e)&&/^\d{1,2}:\d{2}$/.test(norm(e.textContent))&&![...e.children].some(c=>/^\d{1,2}:\d{2}$/.test(norm(c.textContent))));if(!labels.length||!times.length)return null;const lab=labels[0],lr=lab.getBoundingClientRect(),lx=lr.left+lr.width/2,ly=lr.top+lr.height/2;let best=null,bd=1e9;for(const e of times){const r=e.getBoundingClientRect(),x=r.left+r.width/2,y=r.top+r.height/2;const d=Math.hypot(x-lx,y-ly);if(d<bd){bd=d;best=e;}}return best&&bd<320?fmt(norm(best.textContent)):null;})();"""

OLD_GUARD = "const ht=String(document.getElementById('currentContract')?.textContent||''); const hm=ht.match(/KXBTC15M-[A-Z0-9-]+/i); const mc=String(hm?.[0]||main?.contract||main?.state?.contract||main?.data?.contract||''); const fresh=Date.now()-okAt<=3500, same=!!(mc&&d&&d.contract===mc&&d.scalp_contract_aligned===true&&d.scalp_source_fresh===true&&d.scalp_integration_ready===true), env=valid(d);"
NEW_GUARD = "const ht=String(document.getElementById('currentContract')?.textContent||''); const hm=ht.match(/KXBTC15M-[A-Z0-9-]+/i); const mc=String(hm?.[0]||main?.contract||main?.state?.contract||main?.data?.contract||''); const fresh=Date.now()-okAt<=3500, domSame=!!(mc&&d&&d.contract===mc), aligned=!!(d&&d.scalp_contract_aligned===true), srcFresh=!!(d&&d.scalp_source_fresh===true), ready=!!(d&&d.scalp_integration_ready===true), same=!!(domSame&&aligned&&srcFresh&&ready), env=valid(d);"

OLD_MAIN = "const mainText=shown==='PASS'?(env&&!same?'WAIT · CONTRACT SYNC':fresh?'WAITING FOR QUALIFIED SCALP':'WAIT · FEED STALE'):(shown==='EXIT'?'EXIT / PROTECT PROFITS NOW':shown==='PROTECT'?'PROTECT PROFITS':'SCALP ACTIVE · BUILDING');"
NEW_MAIN = "const guardText=!fresh?'WAIT · FEED STALE':!env?'WAIT · INVALID ENVELOPE':!domSame?'WAIT · CONTRACT SYNC':!aligned?'WAIT · SCALP ALIGNMENT':!srcFresh?'WAIT · SCALP SOURCE STALE':!ready?'WAIT · SCALP INTEGRATION':'WAITING FOR QUALIFIED SCALP'; const mainText=shown==='PASS'?guardText:(shown==='EXIT'?'EXIT / PROTECT PROFITS NOW':shown==='PROTECT'?'PROTECT PROFITS':'SCALP ACTIVE · BUILDING');"

OLD_REASON = "const reason=usable?(d.scalp_block_reason||ctx(d)):(env&&!same?'Main/scalp contracts do not match':fresh?'No qualified generalized scalp':'Generalized scalp feed is stale/unavailable');"
NEW_REASON = "const reason=usable?(d.scalp_block_reason||ctx(d)):(!fresh?'Generalized scalp feed is stale/unavailable':!env?'Invalid scalp safety envelope':!domSame?'Main/scalp contract IDs do not match':!aligned?'Scalp backend contract alignment pending':!srcFresh?'Scalp source is stale':!ready?'Scalp integration not ready':'No qualified generalized scalp');"


def patch_v8(path: Path) -> list[str]:
    text = path.read_text(encoding='utf-8', errors='replace')
    changes = []
    for old, new, label in (
        (OLD_LEFT, NEW_LEFT, 'visible-main-timer-nearest-geometry'),
        (OLD_GUARD, NEW_GUARD, 'split-scalp-guard-diagnostics'),
        (OLD_MAIN, NEW_MAIN, 'specific-wait-state'),
        (OLD_REASON, NEW_REASON, 'specific-wait-reason'),
    ):
        if old in text:
            text = text.replace(old, new, 1)
            changes.append(label)
        elif new not in text:
            raise RuntimeError(f'{label} anchor not found; refusing unsafe patch')
    if MARKER not in text:
        text = text.replace('</body>', f'<!-- {MARKER} -->\n</body>', 1) if '</body>' in text else text + f'\n<!-- {MARKER} -->\n'
    path.write_text(text, encoding='utf-8')
    return changes or ['v8-already-present']


def build_dashboard() -> Path:
    html = v7.build_dashboard()
    patch_v8(html)
    return html


def main() -> int:
    html = build_dashboard()
    rendered = html.read_text(encoding='utf-8', errors='replace')
    print('COMBINED SCALP UI V8 | VISIBLE TIMER MIRROR + SPECIFIC FAIL-CLOSED REASON | SHADOW ONLY | NO ORDERS')
    if '--self-test' in sys.argv:
        assert NEW_LEFT in rendered and OLD_LEFT not in rendered
        assert NEW_GUARD in rendered and OLD_GUARD not in rendered
        assert NEW_MAIN in rendered and OLD_MAIN not in rendered
        assert NEW_REASON in rendered and OLD_REASON not in rendered
        assert 'getBoundingClientRect' in rendered
        assert 'mainClock||secs(left)' in rendered
        assert 'WAIT · SCALP SOURCE STALE' in rendered
        assert 'WAIT · SCALP ALIGNMENT' in rendered
        assert 'WAIT · SCALP INTEGRATION' in rendered
        assert 'scalp_contract_aligned===true' in rendered
        assert 'scalp_source_fresh===true' in rendered
        assert 'scalp_integration_ready===true' in rendered
        assert 'Arm +5¢ · EXIT at 4¢ giveback' in rendered
        assert 'SIGNAL ONLY · MANUAL EXECUTION · NO ORDERS' in rendered
        assert 'flip_risk_percent' not in rendered
        assert MARKER in rendered
        print('COMBINED SCALP UI V8 SELFTEST PASS | TIMER MIRROR + GUARD DIAGNOSTICS | NO ORDERS')
        return 0
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

# deployment trigger: V8 live-shadow acceptance
