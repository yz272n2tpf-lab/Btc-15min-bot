# BTC15 Railway EARLY synthetic capacity qualification — VERIFIED 2026-10-16

Source report: `/research-evidence/early_capacity_probe_second_attempt/QUALIFICATION.json`

- Isolated Railway project: `btc15-early-capacity-test`, project `87ad03d5-e1d6-47d6-b1ea-159cd7594686`
- Service: `existing-reader-capacity-probe`; volume: `early-probe-scratch`, 65,536 MB
- Report size: **8160 bytes**
- Original report SHA-256 (computed inside Railway from saved file): `af269a21c2523c8e9eb1b089500be2d69ae61268cf96680dbac1eafaa3e9138c`
- Report schema: `BTC15_SYNTHETIC_DURATION_QUALIFICATION_V1`
- Input generated records: **600000**
- Actual envelopes incl. protocol records: **600004**
- Independent reader records: **600004**
- Reader partitions: **66**, all processed: **true**
- Issue counts: `{}`
- Writer elapsed seconds: **1910.080486278981**
- Writer throughput (envelopes/s): **314.1228887002857**
- Index elapsed seconds: **50.30303384363651**
- Reader elapsed seconds: **127.62710287980735**
- Compressed evidence bytes: **347157819**
- Decoded evidence bytes: **552455159**
- Independent reader working database bytes: **2050920448**
- Peak Python process resource RSS: **60180 KiB** (separate from Railway container metrics)
- Segment count: **42**; sum of segment bytes: **347157819**; matches reported compressed total: **true**
- Railway container metrics from prior 12h inspection: observed peak memory ~2.27 GB, observed disk ~4.09 GB, CPU peak ~1.20 vCPU.

**Decision: PASS — synthetic 600,000-envelope recording, indexing, independent reader and integrity verification on isolated Railway.**

**EXPLICITLY NOT QUALIFIED:** `live rates or worst feed bursts`; `native timing interference`; `private transfer`; `strategy/lifecycle completeness`; `production dependencies/free space`.

This is a synthetic workload spanning 86940 logical seconds (about 24 hours and 9 minutes) but it ran faster than real-time; it is **not** a 24-hour real-source EARLY strategy validation or profitability/entry/EXIT result.

Verification method: Existing isolated Railway service launched **a read-only, one-time report-print command** pinned to a new deployment. It read the persisted JSON on the same volume and printed its SHA and contents to deployment logs. **The original 600k-record workload was not rerun.** No production Railway services, live journals, models or trading orders were modified.
