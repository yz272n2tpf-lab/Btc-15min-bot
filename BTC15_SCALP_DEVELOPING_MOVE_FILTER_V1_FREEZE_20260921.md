# BTC15 SCALP Developing-Move Filter V1 — Frozen Forward Hypothesis

Status: RESEARCH / SHADOW ONLY  
Frozen: 2026-09-21  
Orders: NEVER

## Purpose
Forward-test whether the clean SCALP sample's useful separation generalizes to unseen contracts.
This is NOT a production rule and MUST NOT modify the protected production bot, EARLY, FINAL,
BRTI, Kalshi plumbing, or the existing clean SCALP collector.

## Frozen qualification hypothesis
Evaluate a raw SCALP_MOVE candidate as V1-qualified only when all are true at candidate time:

- entry ask >= 0.02
- entry ask <= 0.50
- seconds_left >= 180
- absolute BTC 15-second move <= $35

Do not optimize these thresholds on the forward sample.

## Outcome labels
For every qualified candidate preserve the existing clean path/result semantics and report:
- +10c executable move
- +20c executable move
- time to +10c / +20c
- maximum executable favorable excursion
- maximum adverse excursion
- entry ask
- seconds remaining
- contract and side

## Baseline / provenance
Discovery sample was the completed clean forward tape from scalp-finalprod-clean-v1.
Exploratory joined sample showed:
- raw cheap matched candidates: 64, +10c winners: 6
- frozen-hypothesis slice: 14, +10c winners: 6
These discovery numbers are context only and are NOT forward-validation evidence.

## Forward validation
Use only contracts first observed AFTER this freeze. Keep discovery contracts excluded.
Report every qualifying candidate; no cherry-picking, retuning, or threshold search.

Minimum review checkpoints:
- 20 qualified candidates
- 40 qualified candidates
- 60 qualified candidates

At each checkpoint report candidate count, unique-contract count, +10c and +20c hit rates,
entry distribution, adverse excursion, and timing.

## Safety
SIGNAL ONLY / NO ORDERS. This file is a frozen research specification only.
