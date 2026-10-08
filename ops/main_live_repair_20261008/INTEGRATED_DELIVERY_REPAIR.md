# October 8 integrated delivery correction

Candidate continuation from `6c4df3aeb82637ca906a22372ca32915d32d3047`.
Production MAIN, SCALP, cockpit and historical volumes are not changed.

## Evidence and correction

The preserved 21:14:33Z shadow and production logs show repeated subscriptions
to the 21:15-open contract before the current 21:15 close. The next messages
failed identity validation. Current quote waits then prevented the native loop
from reaching its BRTI snapshot and publication observers. BRTI history recovery
continued and the shared service reported PRIMARY_OK. The later publication's
BRTI_SOURCE_UNAVAILABLE label alone does not establish a BRTI outage or prove
that a shared current socket was overwritten (the pool already had two slots).

* Refresh the selected official contract by its exact ticker until official
  close. Reject changed identity/target and explicit non-active official status.
* Keep metadata preparation and each quote owner's connection/retry state
  separate. Defer unopened-market sockets until their official open; retain the
  current slot. Back off failed connections at 1/2/4/8 seconds. Preserve the
  frozen decoder, identity, sequence, proof and original quote-age checks.
* Publish explicit failed native attempts: quote, official market and BTC have
  distinct reasons. Inspect BRTI's original receipt independently, marked
  DIAGNOSTIC_ONLY. No diagnostic can create an action frame or extend a lease.
  Complete qualified native frames recover through the existing durable writer.
* Include diagnostic health in unavailable envelopes; retain the original
  cockpit authority owner. Default the candidate cockpit to live delivery.
* Restore the existing cockpit host to this integration branch. The guarded
  shadow launcher runs the actual native producer, isolated information and
  confirmation worker, assembled dashboard routes and cockpit relay. Its fixed
  shadow-only loopback upstream does not change the protected live cockpit.

## Timing and protections

Native model/ladder evaluation cadence, background candidate cadence and
qualifiers from the starting integration are unchanged. Next-contract sockets
start at official open instead of up to 30 seconds before open; connection
failures back off to 8 seconds. This can delay the first qualified opportunity
after a real transport failure. No pre-open or stale opportunity is admitted.
Failed attempts can now publish unavailable state promptly. BTC 10s, BRTI 5s,
quote 6s limits, source timestamps, model artifact, confidence gates, lifecycle,
FINAL/EARLY/SCALP thresholds and signal-only protections are unchanged.

## Verification before genuine-market acceptance

* 30 current transport/bootstrap/protected ladder tests passed.
* 5 current native-authority tests and 6 paired producer tests passed.
* Existing cockpit owner: 13 checks, 85 checkpoints, 572 differential renders.
* Existing host: 14 behavior tests passed; its optional local browser test was
  skipped. Actual assembled dashboard-to-cockpit relay smoke passed.
* Both frozen lane manifests verified. Product manifest hashes only changed
  for reviewed delivery infrastructure. The producer byte guard now checks the
  unchanged frozen durable writer; its envelope intentionally adds diagnostics.
* The obsolete revalidation suite has the same nine failures on the starting
  commit and this candidate (old CONFIRMED/PENDING protocol expectations).
  Those tests were not changed or counted as passing. The historical cockpit
  whole-tree no-change audit is not applicable to an intentional repair.

Live acceptance is pending. The existing shadow service will run at most
48 minutes, targeting two complete consecutive contracts and rollover, with
no mounted volume and no automatic orders. Production rollout requires
separate Chat approval after results and rollback procedure are reviewed.
