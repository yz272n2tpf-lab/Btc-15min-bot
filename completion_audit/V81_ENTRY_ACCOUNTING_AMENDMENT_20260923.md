# V8.1 executable-entry accounting correction

The 21:22:43 UTC DOWN event on KXBTC15M-26SEP231730-30 published 40c while independently timestamped sources showed 57c ask / 56c bid. Source-ask-to-future-bid calculations therefore created an apparent immediate +16c movement without proving the entry was available.

Preserve the original event, original policy/cohort manifests and all prior derived artifacts. Prior exit comparisons that used unverified source entries are conditional research only and cannot certify executable performance. This applies to all legacy entries without source provenance, not selectively to losing/winning outcomes.

The corrected evaluator retains every published event in its denominator. It requires true source provenance at entry and evaluates the first same-contract quote observed after receipt within the already established 3.5s fresh-entry window. The observed ask must be no higher than the published entry price. Missing data, late observation, higher ask and legacy provenance are explicit rejected/unscored entries; it never searches later observations for a cheaper entry. No order/fill, fees, realized profit or continuous path is inferred.

The four registered exit policy constants and lifecycle are unchanged. Changes apply to measurement integrity, not policy selection. The original immutable cohort and policy files are untouched. Any corrected source runtime requires a fresh prospective identity before performance comparison. Current producer/consumer candidates are PR29 and the matching main source-publication PR; neither is production acceptance.

14/14 local lifecycle/replay tests pass, including rejection of the captured 40c/57c class, missing source provenance, stale entry BRTI, missing ask and later-cheaper-price cherry-picking. Existing bid-based lifecycle, both directions, immutable terminal exits and censored horizons remain tested.
