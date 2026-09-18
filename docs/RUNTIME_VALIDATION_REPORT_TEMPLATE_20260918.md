# RUNTIME VALIDATION REPORT TEMPLATE — COST REMEDIATION

## V2 adapter
Deployment ID:
Commit:
Private source:
Auth reference:
Health:
Refresh 1 rows/bytes/SHA:
Refresh 2 rows/bytes/SHA:
Refresh 3 rows/bytes/SHA:
Delta reconstruction SHA match:
Avg RAM:
Max RAM:
Avg CPU:
Public TX:
PASS/FAIL:

## Regime canary
Deployment ID:
Commit:
V2 source boundary SHA:
Control source boundary SHA:
Source rows match:
Source bytes match:
Source SHA match:
Future contract IDs/count match:
Serial opportunity IDs/count match:
Regime tags match:
Protected exit counts match:
Compact metrics match:
Cutoff match:
orders=false:
Avg RAM:
Max RAM:
Avg CPU:
PASS/FAIL:

## Promotion decision
No production/protected service is changed unless both sections PASS. Record rollback deployment/config before any promotion.
