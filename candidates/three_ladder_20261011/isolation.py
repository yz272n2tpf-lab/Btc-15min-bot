"""Read-only release preflight: verify each separately pinned component root.

This module cannot deploy, change config or start a worker. A passing file check
is not statistical acceptance, and the candidate's production flag remains off.
"""
from pathlib import Path
import hashlib,json

LOCK=Path(__file__).with_name('component_lock.json')

def verify_component(name,root,lock=None):
    lock=lock or json.loads(LOCK.read_text());root=Path(root).resolve()
    if lock['signal_only'] is not True or lock['orders'] is not False or lock['production_authorized'] is not False:
        raise ValueError('OFFLINE_SIGNAL_ONLY_REQUIRED')
    c=lock['components'][name]
    for relative,expected in c['files'].items():
        p=(root/relative).resolve()
        if not p.is_relative_to(root) or not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=expected:
            raise ValueError('COMPONENT_REVISION_MISMATCH:'+name+':'+relative)
    return dict(component=name,source_revision=c.get('source_revision',c.get('base_revision')),files=len(c['files']),status='PASS',production_authorized=False)

def deployment_plan(component):
    # This is deliberately a plan, not a generic all-services release command.
    if component=='scalp':return dict(action='KEEP_EXISTING_DEPLOYMENT',deploy=False)
    if component in ('early','final'):return dict(action='RESTRICT_PENDING_PROFILE_OR_NO_GATE_CHANGE',deploy=False)
    if component=='cockpit':return dict(action='SEPARATE_REVIEW_AND_APPROVAL_REQUIRED',deploy=False)
    raise ValueError('UNKNOWN_COMPONENT')
