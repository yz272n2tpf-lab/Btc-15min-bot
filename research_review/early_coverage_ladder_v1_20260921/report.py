#!/usr/bin/env python3
"""Render complete research findings without selecting or tuning a rule."""
import json,math
from pathlib import Path
import pandas as pd
HERE=Path(__file__).resolve().parent

def pct(v):return '—' if v is None else f'{100*v:.2f}%'
def num(v):return '—' if v is None else f'{v:.2f}'
def score(s):return f"{s['correct']}/{s['settled']} ({pct(s['accuracy'])})" if s['settled'] else '0 calls; not estimable'
def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(str,r))+' |' for r in rows])

def main():
    r=json.loads((HERE/'results.json').read_text());manifest=json.loads((HERE/'source_manifest.json').read_text())
    mem=pd.read_csv(HERE/'membership.csv');v=json.loads((HERE/'verification.json').read_text())
    lines=['# BTC15 EARLY Coverage Expansion — Tiered Directional Ladder V1',
      '', '**Decision: NO STABLE HIGH-COVERAGE EARLY LADDER.**', '',
      'No additional actionable tier is eligible to freeze for clean validation. No strategy was deployed or promoted.', '',
      'The frozen three-family tournament did not approach 70–80% coverage with 93–95% official-settlement accuracy. '
      'More decisively, even an omniscient selector could cover only 52.26% of the August contracts or 55.50% of the September '
      'contracts at 93% accuracy using the recorded ≤50¢ quotes in the frozen 2–10 minute window. '
      'These are ceilings on these recorded observations, not a claim about unseen seconds, other market regimes, or entries with more than 10 minutes remaining.', '',
      '## Preregistration and boundaries', '',
      f"Preregistration commit: `{manifest['preregistration_commit']}`. Base/input commit: `{manifest['base_commit']}`. "
      'Three fixed families and three fixed ladder orders; no threshold grid, fitting, post-result changes, or second tournament. '
      'All source observations end by September 6, well before either reserved clean boundary.', '',
      'Branch: `research/early-coverage-ladder-v1-20260921`. Final results commit is recorded by the Git commit containing this report. '
      'The protected forward specification and original Tier-1 rule remain unchanged.', '',
      table(['Family','Frozen hypothesis','Availability'],[
       ['Tier 1','ASK ≤45¢, fair ≥75%, edge ≥8pp, 2–10m, absolute exact-target gap ≥$25; first qualifying row','Both cohorts; unchanged'],
       ['A','Target cushion ≥1.50 × volatility scaled to remaining time; no momentum projection or fair threshold','Both cohorts'],
       ['B','BTC and fresh BRTI both ≥$25 ahead of the same target; disagreement ≤$15; BRTI age ≤2s','September only'],
       ['C','Preferred fair ≥75%, strengthening ≥10pp/30s, nondecreasing over 15s, ASK not rising over 30s, target-supported','September only']]), '',
      'Lower-tier common gates: actual ASK ≤50¢, spread ≤5¢, 4–10 minutes left; finite valid inputs. '
      'Exact formulas, missing-data handling, sample floors and advancement gates are in [PREREGISTRATION.md](PREREGISTRATION.md). '
      'B and C are unavailable in August, not empirically rejected there. A produced no calls in either cohort. '
      'B and C failed on September evidence and remain non-actionable; WATCH is not BUY.', '',
      '## Sources and population', '',
      'August replay: 199 unique contracts and 2,700 preferred-side minute snapshots, August 20–22. '
      'September observed sample: 221 unique contracts across September 3–6; 218 have a valid observation in the 2–10m denominator window. '
      'The raw snapshot source contributes 153 eligible contracts and the unified source 65, with no overlap. '
      'Three contracts without that window are excluded explicitly. This is observed-contract coverage, not continuous-calendar uptime coverage.', '',
      'All 420 distinct historical contracts were matched to saved official Kalshi finalized market.result responses; zero unresolved, '
      'zero conflicts with the available archived settlement labels. Every nonmissing derived/logged fixed target matches the official floor strike within $0.01. '
      'Two side rows of one zero-gap August snapshot have an unrecoverable derived target (0/0); they fail the target-cushion family and cannot qualify Tier 1. '
      'Labels are official yes→UP / no→DOWN. No +5/+10 excursion is used as success.', '',
      table(['Historical source at base commit','Rows','Contracts','Use'],[
       [x['path'],x['rows'],x['contracts'],'Provenance only; excluded from scoring' if x['path']=='subminute_early_dataset_v1.csv' else
        'Archived label/target cross-check' if x['path'] in ['brti_calibration_results.csv','subminute_official_truth_cache.csv','kalshi_official_settlement_check.csv'] else
        'Feature/quote source'] for x in manifest['files']]), '',
      'Full SHA-256 hashes, timestamps and the exact settlement allowlist are in `source_manifest.json`; all official responses are preserved in `evidence.zip`. '
      'The old price-filtered sub-minute dataset was not scored because its builder used nearest joins that could take features up to four seconds in the future. '
      'This study instead used raw snapshots with backward-only, same-contract, same-target enrichment, at most five seconds old. '
      'That lag is added to BRTI age. Missing inputs fail closed.', '',
      'August ASK is a reconstructed candle-end historical quote, not proof of a contemporaneously executable manual fill. '
      'The original BTC candle timestamp open/close semantics remain unresolved; the archived benchmark is reproduced, not certified as causal live performance. '
      'September uses observed quote snapshots, typically five seconds apart (maximum observed within-contract gap 385.38 seconds). '
      'Neither dataset proves depth, a manual fill, fees, or latency. Fair-model versions and sampling differ across cohorts; their accuracies are not pooled.', '',
      '## Chronological development halves', '',
      table(['Cohort','Half','Contracts','First close UTC','Last close UTC'],[
       [cohort,int(half),len(g),g.close.min(),g.close.max()] for (cohort,half),g in mem.groupby(['cohort','half'])]), '',
      'All rules were frozen before scoring either half. The second half is report-only for this run. '
      'All data were previously exposed historical development evidence, so neither half is a new independent holdout.', '']
    for cohort,title in [('august_replay','August reconstructed replay'),('september_observed','September observed snapshots')]:
        c=r[cohort]
        lines += ['## '+title,'', 'Standalone families (each first call per unique contract):','',
          table(['Family','Calls','Coverage','Official settlement accuracy','First half','Second half','UP / DOWN'],[
            [f,s['calls'],pct(s['coverage']),score(s),score(s['half1']),score(s['half2']),f"{s['UP_calls']} / {s['DOWN_calls']}"] for f,s in c['families'].items()]),'',
          table(['Family','ASK mean / median ¢','25–35¢ count / rate','≤40¢ count / rate','≤50¢ rate','Minutes mean / median','Wilson 95% accuracy interval'],[
            [f,f"{num(s['ask_mean_c'])} / {num(s['ask_median_c'])}",f"{s['ideal25_35_count']} / {pct(s['ideal25_35_rate'])}",
             f"{s['le40_count']} / {pct(s['le40_rate'])}",pct(s['le50_rate']),f"{num(s['minutes_mean'])} / {num(s['minutes_median'])}",
             f"{pct(s['wilson95'][0])}–{pct(s['wilson95'][1])}"] for f,s in c['families'].items()]),'']
        if cohort=='august_replay':
            lines+=['The protected benchmark reproduces exactly: **36/38 = 94.74%**, coverage **19.10%**. '
                    'Its unchanged 7–10m first-call slice also reproduces **13/14 = 92.86%**, mean ASK 37.29¢, mean time 9.14m. '
                    'No lower family adds an August contract. Every ladder prefix therefore remains 38 calls, 19.10% coverage and 94.74% accuracy.','']
        else:
            lines+=['The same protected qualification rule yields **8/14 = 57.14%** on these September observations. '
                    'That is a material historical generalization concern, not a score of the current clean observer. '
                    'Its standalone Wilson interval is 32.59–78.62%; do not carry the August 94.74% result forward as a universal accuracy claim.','']
        lines+=['Incremental membership attribution (higher tiers own overlapping contracts; no double-counting):','']
        incrows=[];price=[]
        for name,x in c['ladders'].items():
            for i in [1,2,3]:
                s=x['increments']['tier'+str(i)];family=x['order'][i-1]
                incrows.append([name,f'Tier {i}: {family}',s['calls'],pct(s['coverage']),score(s),score(s['half1']),score(s['half2']),f"{s['UP_calls']} / {s['DOWN_calls']}"])
                price.append([name,f'Tier {i}: {family}',f"{num(s['ask_mean_c'])} / {num(s['ask_median_c'])}",
                  f"{s['ideal25_35_count']} / {pct(s['ideal25_35_rate'])}",f"{s['le40_count']} / {pct(s['le40_rate'])}",pct(s['le50_rate']),
                  f"{num(s['minutes_mean'])} / {num(s['minutes_median'])}"])
        lines+=[table(['Ladder','Tier','Incremental calls','Coverage added','Settlement accuracy','First half','Second half','UP / DOWN'],incrows),'',
          table(['Ladder','Tier','ASK mean / median ¢','25–35¢ count / rate','≤40¢ count / rate','≤50¢ rate','Minutes mean / median'],price),'',
          'Causal combined prefixes (first actual entry across enabled tiers; a later Tier 1 cannot replace it):','']
        rows=[]
        for name,x in c['ladders'].items():
            for i in [1,2,3]:
                s=x['prefixes'][str(i)]['causal']
                rows.append([name,' + '.join(x['order'][:i]),s['calls'],pct(s['coverage']),score(s),num(s['ask_mean_c']),num(s['minutes_mean']),score(s['half1']),score(s['half2'])])
        lines+=[table(['Ladder','Enabled families','Union calls','Union coverage','Union accuracy','Mean ASK ¢','Mean minutes','First half','Second half'],rows),'']
        if cohort=='september_observed':
            lines+=['The largest fixed union is **T1+B+C: 27/218 = 12.39% coverage**, **14/27 = 51.85% accuracy**, '
                    'mean ASK **41.56¢**, mean time **7.09m**. B adds nine contracts beyond Tier 1; C adds four beyond both. '
                    'B’s incremental accuracy is 6/9; C’s is 1/4. Neither meets the 30-incremental-call floor or the accuracy/economics gates.','',
                    'Retrospective Tier-1-priority attribution would misleadingly show 15/27 winners for L2; causal first-entry scoring correctly shows 14/27. '
                    'Six Tier-1 contracts receive earlier lower-tier calls in L2, with three side disagreements. '
                    'L1 attribution and causal accuracy are both 14/23; L3 changes from 10/21 attributed to 9/21 causal. '
                    'The report does not present retrospective precedence as deployable behavior.','']
    lines+=['## Accuracy / coverage frontier and recorded-price ceiling','',
       'The measured high-quality point remains only the August Tier-1 replay: 94.74% accuracy at 19.10% coverage. '
       'The September bounded tournament has no 93% point. T1+B reaches 60.87% at 10.55% coverage; T1+B+C reaches 51.85% at 12.39%. '
       'These are measured points from the preregistered policies, not an exhaustive optimized frontier.','',
       'For a strategy with one call per contract, let W be the number of contracts whose eventual winner ever had a recorded ASK≤50¢ in the allowed window. '
       'Even hindsight cannot supply more than W correct entries. At 93% required accuracy, calls≤floor(W/0.93). '
       'This generous ceiling ignores all predictive-feature and signal-quality restrictions.','',
       table(['Cohort','Entry window','Winner ever ≤50¢ / eligible','Maximum calls at ≥93%','Maximum coverage'],[
        [cohort,f"{k}–10m",f"{x['winner_affordable_contracts']}/{x['denominator']}",x['max_calls_at_93pct_accuracy'],pct(x['max_coverage_at_93pct_accuracy'])]
        for cohort,c in r.items() for k,x in c['oracle'].items()]),'',
       'For 70% coverage, the August sample requires at least 140 calls and September at least 153. '
       'With only 97 and 113 available winners respectively, even perfect hindsight caps accuracy at 69.29% and 73.86% at those call counts. '
       'At 80% coverage, the corresponding upper accuracy bounds fall to 60.63% and 64.57%. '
       'For these recorded windows, 70–80% coverage cannot coexist with 93–95% settlement accuracy and ≤50¢ ASK.','',
       'This does not prove a universal market impossibility. Prices between recorded observations, earlier entries outside the frozen window, '
       'other dates, or different data quality are untested. No post-result earlier-entry experiment was added.','',
       '## Decision and protected systems','',
       '**NO STABLE HIGH-COVERAGE EARLY LADDER. No new actionable tier or candidate is frozen for clean validation.** '
       'Tier 1 remains exactly protected; its existing forward validation continues unchanged. FINAL remains later confirmation/danger assessment; '
       'this study did not create a late BUY ladder. No WATCH signal is counted as approved actionable coverage. '
       'All expanded-union figures above are hypothetical research entries, not certified BUY states.','',
       'Production, protected EARLY and FINAL, SCALP, BRTI, Kalshi plumbing, quote provenance, contract timing, running clean EARLY observer, '
       'running clean SCALP collector, and Directional Position Manager work were not modified. No Railway or live-dashboard calls were made; '
       'no clean-forward data were read or scored. Only a new research branch/directory was written. **SIGNAL ONLY / NO ORDERS.**','',
       '## Verification and reproducibility','',
       f"Eight focused tests passed. Independent audit checked {v['per_policy_entry_records_checked']} per-policy entry records "
       f"({v['distinct_entry_rows_checked']} distinct source rows), raw entry ASK values, all official labels, exact target alignment, "
       'chronological membership and the oracle bounds. Both protected August reference results reproduce exactly. '
       'No outcome-conditioned retuning occurred.','',
       'Implementation corrections: initial CSV timestamp parsing required mixed fractional-second handling before scoring; '
       'a pandas assignment warning was removed without changing values; the target audit was corrected to explicitly account for the two missing zero-gap derived targets. '
       'None changed the frozen rules, calls, or sample selection.','',
       'From the repository root on this branch, run:', '',
       '```bash','python research_review/early_coverage_ladder_v1_20260921/reproduce.py','```','',
       'The command uses pinned repository inputs and saved evidence; no network is needed. It rebuilds features, runs the tournament, '
       'runs the eight tests and independent audit, then checks result hashes. `prepare.py --fetch-labels` is optional historical-label recovery only; '
       'it is not used by reproduction.','',
       'Files: `PREREGISTRATION.md`, `source_manifest.json`, `prepare.py`, `score.py`, `test_study.py`, `audit.py`, `report.py`, '
       '`reproduce.py`, `boundary_receipt.json`, `verification.json`, `reproduction_hashes.json`, and `evidence.zip`. '
       'The evidence archive contains `metrics.csv`, `per_call.csv`, `membership.csv`, `labels.csv`, `results.json`, data-quality/label-retrieval receipts '
       'and all 420 official market responses. `metrics.csv` includes full UP/DOWN counts and accuracies, price bands, medians, confidence intervals '
       'and chronological-half metrics for every family, incremental tier and union prefix.','']
    (HERE/'REPORT.md').write_text('\n'.join(lines))
    print('REPORT.md written')

if __name__=='__main__':main()
