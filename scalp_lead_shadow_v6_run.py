#!/usr/bin/env python3
"""Explicit Railway entrypoint for the V6 research collector."""
print('V6 ENTRYPOINT ACTIVE | launching scalp_lead_shadow_v6.py', flush=True)
exec(compile(open('scalp_lead_shadow_v6.py', 'r', encoding='utf-8').read(), 'scalp_lead_shadow_v6.py', 'exec'), globals())
