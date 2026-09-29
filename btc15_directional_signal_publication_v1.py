"""Read-only durable signal projection; never accepts or updates an origin."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3

from btc15_data_paths_v1 import _btc15_data_root
from btc15_directional_signal_authority_v1 import snapshot_identity, utc, unavailable, manager


def signal_view(raw, path, now):
    try:
        db = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True, timeout=0)
        try:
            db.execute("PRAGMA query_only=ON")
            result = json.loads(db.execute("SELECT value FROM meta WHERE key='latest'").fetchone()[0])
        finally:
            db.close()
        # Projection never retries a transition or refreshes stored source clocks.
        if result["status"] == "UNAVAILABLE":
            return result
        key, content = snapshot_identity(raw)
        manager.read_protected_snapshot(raw, now)
        if (key != result.get("protected_snapshot_key") or content != result.get("protected_content_sha256")):
            return unavailable("AWAITING_MATCHING_OBSERVER_EVIDENCE", origin=result.get("origin_id"))
        from btc15_qualified_forward_observer_v1 import observation
        health = observation(raw, now)
        if (not health["usable_frame"] or not 0 <= (now - utc(result["consumed_utc"])).total_seconds() <= 15):
            return unavailable("STALE_SIGNAL_EVIDENCE", origin=result.get("origin_id"))
        if result.get("guidance") in ("HOLD", "PROTECT") and not health["brti_fresh"]:
            return unavailable("MANAGEMENT_EVIDENCE_UNAVAILABLE", origin=result.get("origin_id"))
        # A BUY event is historical, never a second BUY instruction on HTTP read.
        view = {k: v for k, v in result.items() if k != "protected_evidence"}
        view["event"] = None
        view["last_transition"] = result.get("event")
        view["final_confirmation"] = bool(result.get("final_confirmation") and health["brti_fresh"])
        view["projection_only"] = True
        return view
    except (OSError, sqlite3.Error, ValueError, KeyError, TypeError):
        return unavailable("SIGNAL_LEDGER_UNAVAILABLE")


def attach(state):
    if os.getenv('BTC15_ENABLE_DIRECTIONAL_SIGNALS') == '1':
        state['directional_signal'] = signal_view(state,
            _btc15_data_root(legacy_cwd_fallback=True) / 'btc15_directional_signals_v1.sqlite3',
            datetime.now(timezone.utc))
    return state


def install(directory, replace_once):
    """Opt-in assembly only; protected build_state source remains byte-identical."""
    directory = Path(directory)
    server = directory / 'BTC15_DASHBOARD_LIVE_SERVER_V1.py'
    replace_once(server, '                state = build_state()\n',
                 '                state = build_state()\n'
                 '                from btc15_directional_signal_publication_v1 import attach\n'
                 '                attach(state)\n')
    html = directory / 'BTC_Kalshi_App_Live_v13.html'
    replace_once(html, '  function applyState(d,drawChart=true){\n',
                 '  function applyState(d,drawChart=true){\n'
                 '    renderDirectionalSignal(d);\n')
    # Use existing countdown/HTTP failure invalidation; no timers or fetches added.
    text = html.read_text()
    anchor = next(line for line in text.splitlines(True) if 'function markUnavailable(' in line)
    replace_once(html, anchor, anchor + "    setText('directionalSignalAction','UNAVAILABLE');\n")
    replace_once(html, '  function applyState(d,drawChart=true){\n', RENDER + '\n  function applyState(d,drawChart=true){\n')
    replace_once(html, '</body>', PANEL + '\n</body>')


PANEL = '''<section id="directionalSignalPanel" style="margin:20px;padding:20px;border:1px solid #354b60;border-radius:12px">
<h2>EARLY directional signal · manual execution only</h2>
<strong id="directionalSignalAction">UNAVAILABLE</strong>
<p id="directionalSignalOrigin">No accepted signal evidence.</p>
<p>No order or fill is implied. Executable EXIT guidance is unavailable.</p>
</section>'''

RENDER = '''  function renderDirectionalSignal(d){
    const s=d.directional_signal, o=s?.origin;
    const source=Date.parse(s?.source_timestamp_utc), now=clock.now(performance.now());
    const fresh=usableFrame(d) && Number.isFinite(source) && now>=source && now-source<=15000;
    const management=s?.guidance==='HOLD' || s?.guidance==='PROTECT';
    const available=s?.status==='AVAILABLE' && fresh && (!management || freshBrti(d));
    setText('directionalSignalAction',available?`${s.guidance} · ${o?.side || ''}`:s?.status==='PASS' && fresh?'PASS':'UNAVAILABLE');
    setText('directionalSignalOrigin',o?`Accepted signal ${o.origin_id} · ${o.contract.ticker} · original ASK ${(o.original_ask*100).toFixed(2)}¢ · ${o.signal_timestamp_utc}. Not a fill.`:'No current accepted signal evidence.');
  }'''
