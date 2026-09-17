"""Nextgen /audit only: immutable entity bytes plus per-fetch ledger envelopes.

No last-good cache, repair, GC, evidence rewrite, or network operations.
POSIX fsync/flock assumptions match the existing Sentinel ledger. A durable
intent precedes object creation; any unacknowledged write requires independent
recovery. The catalog uses the unchanged ledger/anchor durability protocol.
"""
from contextlib import contextmanager
import base64
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import threading
from urllib.parse import urlparse

from integrity_sentinel.recorder_core_v1 import AppendOnlyHashChainLedger, canonical_json
from integrity_sentinel.storage_guard_v1 import storage_status

SCHEME = "NEXTGEN_SHA256_V1"
DIGEST = re.compile(r"[0-9a-f]{64}\Z")


def nextgen_audit(observation):
    return (observation.get("source") == "nextgen_membership"
            and observation.get("source_kind") == "membership"
            and urlparse(observation.get("request_url", "")).path == "/audit")


def eligible(observation):
    status = observation.get("http_status")
    return (nextgen_audit(observation) and type(status) is int and 200 <= status < 300
            and observation.get("body_complete") is True
            and observation.get("parse_outcome") == "OBJECT"
            and observation.get("parse_error") is None
            and observation.get("error_type") is None
            and observation.get("source_failures") == [])


def parse_body(raw):
    def reject(value):
        raise ValueError("non-finite JSON constant: " + value)
    payload = json.loads(raw, parse_constant=reject)
    canonical_json(payload)  # Also rejects finite-parser overflow.
    if not isinstance(payload, dict):
        raise ValueError("expected Nextgen object")
    return payload


class NextgenBodyStore:
    def __init__(self, root, write_guard=None):
        self.root = Path(root) / "nextgen-bodies-v1"
        self.pending = self.root / "durability-pending.json"
        self.catalog_path = self.root / "catalog.jsonl"
        self._lock = threading.RLock()
        self._write_guard = write_guard
        self._failed = False

    def _guard(self):
        if self._write_guard:
            self._write_guard()
        elif storage_status(self.root.parent)["storage_ok"] is not True:
            raise OSError("storage guard FAIL")

    @staticmethod
    def _sync_dir(path):
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    @contextmanager
    def _locked(self, create=False):
        with self._lock:
            if create:
                self._guard()
                try:
                    self.root.mkdir(mode=0o700)
                except FileExistsError:
                    pass
                self._sync_dir(self.root.parent)
            if not os.path.lexists(self.root):
                yield False
                return
            fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                # Readers also take EX: catalog initialization and publication
                # cannot race a health/reopen check from another process.
                fcntl.flock(fd, fcntl.LOCK_EX)
                yield True
            finally:
                os.close(fd)

    def _catalog(self):
        return AppendOnlyHashChainLedger(self.catalog_path, self._guard)

    def _read(self, digest, size):
        if not isinstance(digest, str) or not DIGEST.fullmatch(digest):
            raise ValueError("invalid body digest")
        if type(size) is not int or size < 0:
            raise ValueError("invalid body size")
        fd = os.open(self.root / (digest + ".body"), os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size != size:
                raise ValueError("body type/size mismatch")
            raw = stream.read(size + 1)
        if len(raw) != size or hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError("body SHA-256 mismatch")
        return raw

    def _verify_locked(self):
        if self._failed or os.path.lexists(self.pending):
            raise ValueError("unacknowledged body durability; independent recovery required")
        if not self.catalog_path.exists():
            if list(self.root.iterdir()):
                raise ValueError("body store missing catalog")
            return {}
        catalog = self._catalog()  # Verifies full catalog, anchor and markers.
        known = {}
        for row in catalog._iter_records():
            entry = row["body"]
            if set(entry) != {"record_type", "sha256", "bytes"} or entry["record_type"] != "IMMUTABLE_NEXTGEN_BODY":
                raise ValueError("invalid body catalog entry")
            digest, size = entry["sha256"], entry["bytes"]
            self._read(digest, size)
            if digest in known:
                raise ValueError("duplicate catalog object")
            known[digest] = size
        allowed = {"catalog.jsonl", "catalog.jsonl.anchor.json"} | {h + ".body" for h in known}
        if {p.name for p in self.root.iterdir()} != allowed:
            raise ValueError("catalog/body-store mismatch")
        return known

    def verify(self):
        with self._locked() as exists:
            if self._failed:
                raise ValueError("body store write failed; independent recovery required")
            return self._verify_locked() if exists else {}

    def put(self, raw):
        digest = hashlib.sha256(raw).hexdigest()
        reference = {"scheme": SCHEME, "sha256": digest, "bytes": len(raw)}
        with self._locked(create=True):
            known = self._verify_locked()
            if digest in known:
                # Verify bytes, never trust a pathname or an in-memory cache.
                if self._read(digest, len(raw)) != raw:
                    raise ValueError("body collision/mismatch")
                return reference
            try:
                self._guard()
                marker = canonical_json({"state": "DURABILITY_UNACKNOWLEDGED", **reference}).encode()
                fd = os.open(self.pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                try:
                    if os.write(fd, marker) != len(marker):
                        raise OSError("short body intent write")
                    os.fsync(fd)
                finally:
                    os.close(fd)
                self._sync_dir(self.root)
                self._guard()
                fd = os.open(self.root / (digest + ".body"),
                             os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
                try:
                    if os.write(fd, raw) != len(raw):
                        raise OSError("short immutable body write")
                    os.fsync(fd)
                finally:
                    os.close(fd)
                self._sync_dir(self.root)
                self._catalog().append({"record_type": "IMMUTABLE_NEXTGEN_BODY",
                                        "sha256": digest, "bytes": len(raw)})
                self._sync_dir(self.root)
                # Only the transient intent is removed. No referenced evidence
                # is ever removed. Resurrected intent fails conservatively.
                self.pending.unlink()
            except Exception:
                self._failed = True
                raise
        return reference

    def compact(self, observation):
        if not eligible(observation):
            return observation
        raw = base64.b64decode(observation["body_base64"], validate=True)
        if (hashlib.sha256(raw).hexdigest() != observation["body_sha256"]
                or len(raw) != observation["body_bytes"]
                or canonical_json(parse_body(raw)) != canonical_json(observation["payload"])):
            raise ValueError("observation/received-body mismatch")
        reference = self.put(raw)
        return {**observation, "body_base64": None, "payload": None,
                "body_ref": reference, "payload_storage": SCHEME}

    def resolve(self, observation):
        """Return this observation's bytes; never substitute a prior response."""
        if "body_ref" not in observation:
            value = observation.get("body_base64")
            return None if value is None else base64.b64decode(value, validate=True)
        with self._locked() as exists:
            known = self._verify_locked() if exists else {}
            self.check_reference(observation, known)
            return self._read(observation["body_sha256"], observation["body_bytes"])

    @staticmethod
    def check_reference(observation, known):
        ref = observation.get("body_ref")
        if not isinstance(ref, dict) or set(ref) != {"scheme", "sha256", "bytes"}:
            raise ValueError("invalid body reference")
        digest, size = observation.get("body_sha256"), observation.get("body_bytes")
        if (not eligible(observation) or observation.get("record_type") != "SOURCE_OBSERVATION"
                or ref != {"scheme": SCHEME, "sha256": digest, "bytes": size}
                or type(size) is not int or not isinstance(digest, str)
                or known.get(digest) != size or digest not in known
                or observation.get("payload_storage") != SCHEME
                or observation.get("body_base64") is not None or observation.get("payload") is not None):
            raise ValueError("ledger/body-store reference mismatch")


class NextgenMembershipLedger(AppendOnlyHashChainLedger):
    """Existing chain/anchors unchanged; body integrity joins the health gate."""
    def __init__(self, path, body_store, write_guard=None, **kwargs):
        self.body_store = body_store
        super().__init__(path, write_guard, **kwargs)

    def _verify_locked(self):
        status = super()._verify_locked()
        known = self.body_store.verify()
        observations = {}
        for row in self._iter_records():
            body = row["body"]
            if "body_ref" in body or "payload_storage" in body:
                self.body_store.check_reference(body, known)
                observation_id = body.get("observation_id")
                if not isinstance(observation_id, str) or not observation_id or observation_id in observations:
                    raise ValueError("invalid/duplicate observation identity")
                observations[observation_id] = (row["record_hash"], body["body_sha256"])
            if body.get("record_type") == "STRATEGY_MEMBERSHIP":
                parent = observations.get(body.get("observation_id"))
                if parent is not None or "observation_body_sha256" in body:
                    if parent != (body.get("observation_record_hash"), body.get("observation_body_sha256")):
                        raise ValueError("membership observation/body linkage mismatch")
        return status

    def append(self, body):
        if "body_ref" in body or "payload_storage" in body:
            self.body_store.check_reference(body, self.body_store.verify())
        return super().append(body)
