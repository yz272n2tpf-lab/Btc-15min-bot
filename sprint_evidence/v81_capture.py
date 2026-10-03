"""Pinned V8.1 passive publication/evaluation evidence; NO STRATEGY EVALUATION.

Recovered exact current producer from deployment b05723e, not older shadow
policies. Uses existing Producer.LIFECYCLE_EMISSION transport without core edits.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path

from .passive_capture import Producer,Identity,observed_copy,pack,digest

DEPLOYED_COMMIT='b05723ec622f901a05402ecf27f4d33505753ef1'
SOURCE_SHA256='fbd38de2cf4afd7708abcd968e2ce492623225bdfaeb922328b684a2276e0684'
INPUT_SHA256='6ec1687e6f1c18df1e8ad864aef017c725947d533c3594e7f2d189e13f63ae07'
ENGINE_SHA256='0b401bf828188de58b7568f3636dd52a21e03c3e3f8ef6c4da9b6e38e624a933'
DIRECT_SOURCE_PINS={
    'v81_30_45_live_feed.py':SOURCE_SHA256,
    'btc15_v81_qualified_inputs_v1.py':INPUT_SHA256,
    'scalp_lead_unified_v8.py':ENGINE_SHA256,
    'scalp_lead_shadow_v5.py':'f9b6b989794de56aea01a48aa984244f8ffafe97ba13560d77184baf7dcd85be',
    'brti_resilience_shadow_v2.py':'1f4c52973fa1065faacae2fdfba895f63c5e2983fde6db539e06bd765948204d'}
SCHEMA='BTC15_V81_PASSIVE_EMISSION_V1'


class V81Capture:
    """Read already-produced locals only; no gate, feature or source calls."""
    def __init__(self,producer):
        if producer.identity.source_sha256!=SOURCE_SHA256:raise ValueError('V81_PRODUCER_SOURCE_BINDING')
        self.producer=producer

    def publication(self,phase,state,local_values):
        try:
            actual=local_values.get('event') if phase=='SIGNAL' else None
            key=None if not isinstance(actual,dict) else {
                'contract':actual.get('contract'),'side':actual.get('side'),'signal_ts':actual.get('signal_ts')}
            # This is a new EVIDENCE ID over explicit existing origin fields;
            # never an invented upstream accepted-signal identifier.
            original=None if not isinstance(actual,dict) else dict(
                key=key,entry_price=actual.get('entry_price'),entry_provenance=actual.get('entry_provenance'),
                seconds_left_at_signal=actual.get('seconds_left_at_signal'),route=actual.get('route'))
            oid=None if original is None else digest(pack([self.producer.identity.producer_id,
                self.producer.identity.run_id,observed_copy(original)]))
            return self.producer.lifecycle(dict(schema=SCHEMA,event_type='STATE_PUBLICATION',phase=phase,
                producer_commit=DEPLOYED_COMMIT,producer_source_sha256=SOURCE_SHA256,
                state=state,observed_signal_key=key,evidence_origin_id=oid,
                upstream_native_origin_id=None,original_signal_event=actual,
                current_row=local_values.get('row') if phase=='SIGNAL' else None,
                published_entry_price=state.get('entry_price'),
                original_executable_ask=None if original is None else (actual.get('entry_provenance') or {}).get('quote',{}).get(str(actual.get('side','')).lower()+'_ask'),
                completed_http_delivery_utc=None,manual_fill=None,
                basis='EXISTING_STATE_UPDATE_RETURNED; NO_HTTP_GET; NO_GATE_REEVALUATION'))
        except Exception:return False

    def evaluation(self,phase,local_values,global_values):
        try:
            row=local_values.get('row') if phase=='COMPLETE' else None
            ticker=row.get('ticker') if isinstance(row,dict) else None
            last=global_values.get('last_signal') or {}
            cooldown=None if ticker is None else {s:last.get((ticker,s,'HIGH_30_45')) for s in ('UP','DOWN')}
            return self.producer.lifecycle(dict(schema=SCHEMA,event_type='EVALUATION',phase=phase,
                producer_commit=DEPLOYED_COMMIT,producer_source_sha256=SOURCE_SHA256,
                row=row,feature_map=local_values.get('feature_map') if row else None,
                diagnostics=local_values.get('diagnostics') if row else None,
                active=global_values.get('active'),last_signal_for_contract=cooldown,
                source_wait_reason=local_values.get('reason') if phase=='SOURCE_WAIT' else None,
                basis='EXISTING_LOOP_COMPLETED_OR_WAIT; active_IS_ORIGINAL_LIFECYCLE',
                manual_fill=None,automatic_exit=None))
        except Exception:return False


def instrument(source,*,enabled=True):
    if digest(source)!=SOURCE_SHA256:raise ValueError('V81_SOURCE_CHANGED')
    tree=ast.parse(source)
    if not enabled:return tree
    funcs={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
    for name,phase in [('publish_wait','WAIT'),('publish_signal','SIGNAL')]:
        fn=funcs.get(name)
        if fn is None or not isinstance(fn.body[-1],ast.With):raise ValueError('V81_PUBLICATION_SEAM')
        # Outside the existing STATE_LOCK: only this loop writes STATE. HTTP
        # publication_view copies it; this hook never holds the publication lock.
        fn.body.append(ast.parse(f"_sprint_v81.publication('{phase}', STATE, locals())").body[0])
    loop=funcs.get('loop')
    loops=[n for n in loop.body if isinstance(n,ast.While)] if loop else []
    if len(loops)!=1:raise ValueError('V81_LOOP_SEAM')
    blocks=[n for n in loops[0].body if isinstance(n,ast.Try)]
    if len(blocks)!=1 or len(blocks[0].handlers)!=1:raise ValueError('V81_TRY_SEAM')
    blocks[0].body.append(ast.parse("_sprint_v81.evaluation('COMPLETE', locals(), globals())").body[0])
    blocks[0].handlers[0].body.append(ast.parse("_sprint_v81.evaluation('SOURCE_WAIT', locals(), globals())").body[0])
    return ast.fix_missing_locations(tree)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--nonproduction',required=True,action='store_true')
    ap.add_argument('--source',required=True)
    ap.add_argument('--identity-json',required=True)
    ap.add_argument('--key-file',required=True)
    ap.add_argument('--socket',required=True)
    args=ap.parse_args()
    producer=Producer(args.socket,Identity(**json.loads(Path(args.identity_json).read_text())),Path(args.key_file).read_bytes())
    source=Path(args.source).resolve()
    if source.parent!=Path.cwd():raise ValueError('V81_EXACT_CHECKOUT_CWD_REQUIRED')
    for name,expected in DIRECT_SOURCE_PINS.items():
        if digest((source.parent/name).read_bytes())!=expected:raise ValueError('V81_DEPENDENCY_CHANGED:'+name)
    raw=source.read_bytes()
    namespace=dict(__name__='__main__',__file__=str(args.source),_sprint_v81=V81Capture(producer))
    try:exec(compile(instrument(raw),str(args.source),'exec'),namespace)
    finally:producer.close()

if __name__=='__main__':main()
