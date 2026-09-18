"""One source observation's derived-row obligation, with fail-closed reopen.

The envelope is committed first. Its ordered event-ID commitment makes a
missing batch detectable even if disk failure prevents creation of an intent
marker. This adds no aggregate event and never auto-completes old obligations.
Old envelopes and the existing immutable-body verification remain supported.
"""
from integrity_sentinel.identity_v1 import exact_contract, validate_contract
from integrity_sentinel.nextgen_body_store_v1 import NextgenMembershipLedger
from integrity_sentinel.recorder_core_v1 import sha256_json

SCHEME = "MEMBERSHIP_BATCH_V2"


def batch_commitment(events):
    return {"scheme": SCHEME, "count": len(events),
            "event_ids_sha256": sha256_json([event["event_id"] for event in events])}


class BatchedMembershipLedger(NextgenMembershipLedger):
    def _verify_obligations(self, completing_batch=None):
        parent, expected, ids = None, None, []
        declared_observations = set()

        def consume(body):
            nonlocal parent, expected, ids
            if expected is not None:
                observation = parent["body"]
                if (body.get("record_type") != "STRATEGY_MEMBERSHIP"
                        or body.get("source") != observation["source"]
                        or body.get("observation_id") != observation["observation_id"]
                        or body.get("observation_record_hash") != parent["record_hash"]
                        or body.get("observed_by_sentinel_utc") != observation["completed_at_utc"]):
                    raise ValueError("membership batch observation linkage mismatch")
                if "body_ref" in observation:
                    if body.get("observation_body_sha256") != observation["body_sha256"]:
                        raise ValueError("membership batch body provenance mismatch")
                elif "observation_body_sha256" in body:
                    raise ValueError("unexpected membership batch body provenance")
                record = body.get("record")
                validate_contract(body.get("contract_id"))
                if (not isinstance(record, dict) or exact_contract(record) != body.get("contract_id")
                        or body.get("record_sha256") != sha256_json(record)
                        or body.get("event_id") != sha256_json({k: body.get(k) for k in
                            ("source", "container", "contract_id", "record")})
                        or body.get("orders") is not False or body.get("rescore_performed") is not False):
                    raise ValueError("membership batch record identity mismatch")
                ids.append(body["event_id"])
                if len(ids) == expected["count"]:
                    if len(set(ids)) != len(ids) or sha256_json(ids) != expected["event_ids_sha256"]:
                        raise ValueError("membership batch event commitment mismatch")
                    parent, expected, ids = None, None, []

        for row in self._iter_records():
            body = row["body"]
            if expected is not None:
                consume(body)
            elif "membership_batch" in body:
                commitment = body["membership_batch"]
                if (body.get("record_type") != "SOURCE_OBSERVATION"
                        or body.get("source_kind") != "membership"
                        or not isinstance(body.get("observation_id"), str)
                        or not body["observation_id"]
                        or body["observation_id"] in declared_observations
                        or not isinstance(commitment, dict)
                        or set(commitment) != {"scheme", "count", "event_ids_sha256"}
                        or commitment["scheme"] != SCHEME
                        or type(commitment["count"]) is not int or commitment["count"] < 0
                        or not isinstance(commitment["event_ids_sha256"], str)
                        or len(commitment["event_ids_sha256"]) != 64):
                    raise ValueError("invalid membership batch commitment")
                declared_observations.add(body["observation_id"])
                if commitment["count"] == 0:
                    if commitment != batch_commitment([]):
                        raise ValueError("invalid empty membership batch commitment")
                else:
                    parent, expected = row, commitment
            elif (body.get("record_type") == "STRATEGY_MEMBERSHIP"
                    and body.get("observation_id") in declared_observations):
                raise ValueError("extra membership row after completed batch")
        if completing_batch:
            # Only a live caller holding this ledger instance may finish its
            # just-committed envelope. Reopen rejects the pending obligation.
            if expected is None or expected["count"] != len(completing_batch) or ids:
                raise ValueError("batch requires one complete pending observation")
            for body in completing_batch:
                consume(body)
        if expected is not None:
            raise ValueError("incomplete membership batch; independent recovery required")

    def _verify_locked(self):
        status = super()._verify_locked()
        self._verify_obligations()
        return status

    def _verify_batch_locked(self, bodies):
        # Preserve the entire V1 chain/anchor/durability/body/provenance gate.
        # The only admissible unfinished obligation is this exact incoming
        # batch following its already durable observation at the current tail.
        status = super()._verify_locked()
        self._verify_obligations(completing_batch=bodies)
        return status
