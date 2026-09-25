# Two-clock recovery checkpoint

Work in progress; NOT deployment approval. Parent: 9ff0a2f036df989b98c6bc5d6835933f1c7d7c9d.

Recovered four candidate files intact from the interrupted workspace. The initial 26-test run had two failures and two errors (saved in TWO_CLOCK_RECOVERED_FIRST_TESTS_20260925.log). Fractional-cut conversion in the information-only feature adapter was a genuine engineering defect; the patched adapter now uses PR36's UTC datetime precision. Other initial failures were fixture support/WAIT handling. Additional quote-identity conflict checks were added. Retest and full acceptance are pending at this checkpoint.

Production PR36 source, model artifact, deployment configuration and action consumers are unchanged. The optional native bridge/worker have not been enabled. No orders, deployment, merge, prediction tuning, cohort scoring or upstream polling.
