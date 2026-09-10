#!/usr/bin/env python3
"""One-command report generator for V7 Railway logs.

Usage:
  python scalp_v7_report.py < v7.log
or
  python scalp_v7_report.py v7.log

Research/reporting only. No orders and no threshold mutation.
"""
import re, sys, json
from scalp_v7_decision_toolkit import Outcome, decision_report, BrtiHealth

RESULT_RE = re.compile(
    r"LEAD_V7 RESULT \| lane (?P<lane>[^|]+) \| [^|]+ \| (?P<side>UP|DOWN) \| zone (?P<zone>[^|]+) \| style (?P<style>[^|]+) \| entry (?P<entry>[0-9.]+) \| max_gain (?P<gain>[+-]?[0-9.]+) \| adverse (?P<adv>[+-]?[0-9.]+) \| to\+5c (?P<t5>[^|]+) \| to\+10c (?P<t10>[^|]+) \| to\+20c (?P<t20>[^|]+)"
)
BRTI_RE = re.compile(r"samples=(?P<samples>\d+).*?primary_ok=(?P<ok>\d+).*?retry_recovered=(?P<retry>\d+).*?errors=(?P<errors>\d+)")


def ftime(v):
    v=v.strip()
    if v in ('None','N/A',''):
        return None
    try:return float(v)
    except:return None


def read_text():
    if len(sys.argv) > 1:
        with open(sys.argv[1], 'r', encoding='utf-8', errors='replace') as f:
            return f.read()
    return sys.stdin.read()


def main():
    text=read_text()
    outcomes=[]
    for m in RESULT_RE.finditer(text):
        outcomes.append(Outcome(
            lane=m.group('lane').strip(), zone=m.group('zone').strip(),
            entry=float(m.group('entry')), max_gain=float(m.group('gain')),
            adverse=float(m.group('adv')), to5=ftime(m.group('t5')),
            to10=ftime(m.group('t10')), to20=ftime(m.group('t20'))))

    brti=None
    matches=list(BRTI_RE.finditer(text))
    if matches:
        m=matches[-1]
        brti=BrtiHealth(int(m.group('samples')),int(m.group('ok')),int(m.group('retry')),int(m.group('errors')))

    report={'outcome_count':len(outcomes),'groups':decision_report(outcomes)}
    if brti:
        report['brti']={
            'samples':brti.samples,'fresh_ok':brti.fresh_ok,
            'fresh_pct':round(brti.fresh_pct,2),'retry_recovered':brti.retry_recovered,
            'errors':brti.errors,'error_pct':round(brti.error_pct,2),
            'status':brti.status()}

    print(json.dumps(report,indent=2,sort_keys=True))

if __name__=='__main__':
    main()
