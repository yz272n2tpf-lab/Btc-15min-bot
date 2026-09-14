# BTC15 SCALP LADDER SELECTION FREEZE V1

Status: **RESEARCH ONLY / SIGNAL ONLY / NO ORDERS**

This document freezes the selection logic for the two new scalp research questions **before any full-tape result is reviewed**.

The protected primary scalp remains unchanged: first frozen-qualified candidate per contract, >=120 seconds left, side-aligned btc30 >= $15, no entry-price filter, +5c arm, 4c giveback EXIT.

## 1. Secondary / tertiary viability gate

The secondary and tertiary candidate rule itself is already fixed by `BTC15_SCALP_MULTI_OPPORTUNITY_RESEARCH_FREEZE_V1.md`: first later frozen-qualified candidate only after the prior displayed scalp reaches protected EXIT.

Historical replay is used only as a viability screen. The layer may proceed to a fresh forward freeze only if the chronological **VALIDATION** half satisfies all of:

- at least 12 secondary opportunities;
- secondary +5c hit rate >= 80%;
- secondary +10c hit rate >= 60%;
- secondary median peak executable gain >= +10c;
- secondary average adverse excursion no worse than -10c;
- protected management remains +5c arm / 4c giveback, unchanged;
- no entry-price filter is introduced.

Tertiary is reported separately. It is not required for the secondary layer to advance. A tertiary layer needs its own >=12 VALIDATION opportunities and the same viability thresholds before it can be considered separately.

After the candidate rule is frozen, REPORT_ONLY may be opened only as confirmation. Historical success never promotes directly to the app. Any secondary/tertiary candidate still requires at least 20 new unique forward qualified later opportunities.

## 2. Failed-primary cut challenger selection

The pre-arm grid was frozen before results:

- adverse thresholds: -3c, -5c, -7c, -10c;
- minimum elapsed: 10s, 20s, 30s, 45s, 60s.

A failure-cut challenger can be selected from **VALIDATION only** if a grid cell satisfies all of:

- at least 12 triggered protected-primary cases;
- later recovery to +5c after the trigger <= 15%;
- median best recovery after trigger < +5c;
- trigger occurs before the protected +5c arm by definition;
- no entry eligibility rule is changed.

Among eligible VALIDATION cells, select mechanically in this order:

1. lowest later +5c recovery rate;
2. least-negative average executable gain at trigger (protects capital earlier);
3. shortest minimum elapsed time;
4. smallest adverse threshold.

If no VALIDATION cell qualifies, **no failed-primary cut challenger exists in V1**.

Once one VALIDATION cell is selected, its adverse threshold + elapsed requirement is frozen **before** REPORT_ONLY review. REPORT_ONLY may confirm or reject it but may not change the selected threshold.

Even if both historical halves pass, the cut challenger remains research-only until it completes a fresh untouched forward test of at least 20 new unique qualifying failed-primary events.

## Hard guardrails

- REPORT_ONLY is never used for threshold selection.
- No secondary scalp overlaps an active prior scalp.
- No entry-price filter.
- No change to protected primary, EARLY, or FINAL.
- No automatic trading or order actions.
- Any new actionable rule requires a separate frozen forward-test cutoff before collection begins.
