#!/usr/bin/env python3
"""
BTC15 Generalized Scalp PATH Export Bridge V1

LIVE-MUTATION PREP ONLY — DO NOT DEPLOY WITHOUT EXPLICIT AUTHORIZATION.
# PATH_EXPORT_DEPLOY_TRIGGER_20260913
Purpose:
- Keep the exact Full-Time V2 collector running unchanged.
- Add a read-only HTTP research surface in the SAME generalized shadow service.
- Read /data/scalp_move_shadow_v1_events.csv without writing to it.
- Expose health, integrity-neutral counts, and optional raw CSV export.

Safety:
- GET only.
- No POST/PUT/DELETE.
- No Kalshi order code.
- No strategy threshold changes.
- No edits to the event tape.
- Full export disabled unless PATH_EXPORT_ENABLE=1.
- Optional bearer/query token via PATH_EXPORT_TOKEN; query tokens are never printed in HTTP logs.
"""
from __future__ import annotations
import csv, hashlib, io, json, os, runpy, threading
from collections import Counter, defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

EVENT_CSV = Path(os.environ.get(
    "SCALP_EVENT_CSV",
    "/data/scalp_move_shadow_v1_events.csv"
))
COLLECTOR = Path(os.environ.get(
    "SCALP_COLLECTOR_SCRIPT",
    "scalp_move_shadow_v2_full_time.py"
))
PORT = int(os.environ.get("PORT", "8080"))
EXPORT_ENABLE = os.environ.get("PATH_EXPORT_ENABLE", "0") == "1"
TOKEN = os.environ.get("PATH_EXPORT_TOKEN", "").strip()

def selected_run_path(query, kind, current):
    """Export only the current run or the explicitly retained pre-cadence run."""
    selected=query.get('run_id',[])
    if not selected:return Path(current) if current else None
    if len(selected)!=1 or selected[0] not in {
            'clean-source-v2-20260923',os.getenv('BTC15_CLEAN_RUN_ID','')} or not selected[0]:
        raise ValueError('Unknown retained run')
    suffix={'manifest':'manifest.json','common':'common.jsonl.gz','events':'events.csv'}[kind]
    return Path(os.getenv('BTC15_DATA_DIR','/data'))/('scalp_'+selected[0]+'_'+suffix)

def file_sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def read_rows():
    if not EVENT_CSV.exists():
        return [], []
    with EVENT_CSV.open(newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        return list(r), (r.fieldnames or [])

def summarize():
    rows, _ = read_rows()
    counts = Counter(str(r.get("record_type") or "").strip() for r in rows)
    per = defaultdict(Counter)
    for r in rows:
        cid = str(r.get("candidate_id") or "").strip()
        typ = str(r.get("record_type") or "").strip()
        if cid:
            per[cid][typ] += 1

    complete = []
    missing_path = []
    duplicate_candidate = []
    duplicate_result = []
    for cid, c in sorted(per.items()):
        if c["CANDIDATE"] == 1 and c["PATH"] >= 1 and c["RESULT"] == 1:
            complete.append(cid)
        if c["CANDIDATE"] >= 1 and c["PATH"] == 0:
            missing_path.append(cid)
        if c["CANDIDATE"] > 1:
            duplicate_candidate.append(cid)
        if c["RESULT"] > 1:
            duplicate_result.append(cid)

    stat = EVENT_CSV.stat() if EVENT_CSV.exists() else None
    return {
        "event_csv": str(EVENT_CSV),
        "exists": EVENT_CSV.exists(),
        "size_bytes": None if stat is None else stat.st_size,
        "sha256": file_sha256(EVENT_CSV),
        "total_rows": len(rows),
        "candidate_rows": counts["CANDIDATE"],
        "path_rows": counts["PATH"],
        "result_rows": counts["RESULT"],
        "snapshot_rows": counts["SNAPSHOT"],
        "unique_candidate_ids": len(per),
        "path_complete_candidate_ids": len(complete),
        "missing_path_candidate_ids": missing_path,
        "duplicate_candidate_ids": duplicate_candidate,
        "duplicate_result_ids": duplicate_result,
        "source_file_modified": False,
        "orders": False,
    }

def authorized(handler):
    if not TOKEN:
        return True
    header_ok = handler.headers.get("Authorization", "") == f"Bearer {TOKEN}"
    query = parse_qs(urlparse(handler.path).query)
    query_ok = query.get("token", [""])[0] == TOKEN
    return header_ok or query_ok

class Handler(BaseHTTPRequestHandler):
    server_version = "BTC15PathExportV1/1.0"

    def log_message(self, fmt, *args):
        print("PATH_EXPORT_HTTP | request", flush=True)

    def _json(self, code, obj):
        raw = json.dumps(obj, separators=(",", ":")).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if not authorized(self):
            return self._json(401, {"ok": False, "error": "unauthorized", "orders": False})

        path = urlparse(self.path).path
        query=parse_qs(urlparse(self.path).query)
        try:
            manifest_path=selected_run_path(query,'manifest',os.getenv('BTC15_RUN_MANIFEST'))
            common_path=selected_run_path(query,'common',os.getenv('BTC15_COMMON_OBSERVATIONS'))
            event_path=selected_run_path(query,'events',EVENT_CSV)
        except ValueError:
            return self._json(400, {'ok':False,'error':'unknown_run','orders':False})
        if path == '/research/run-manifest':
            name = manifest_path
            if not name or not Path(name).is_file():
                return self._json(404, {'ok':False,'error':'run_manifest_missing','orders':False})
            return self._json(200, json.loads(Path(name).read_text()))

        if path == '/research/common-export':
            if not EXPORT_ENABLE:
                return self._json(403, {'ok':False,'error':'export_disabled','orders':False})
            name = common_path
            if not name:
                return self._json(404, {'ok':False,'error':'common_evidence_unconfigured','orders':False})
            from btc15_common_observer_v1 import export_chunk
            try:
                query=parse_qs(urlparse(self.path).query)
                meta,raw=export_chunk(name,int(query.get('offset',['0'])[0]),int(query.get('limit',['4000000'])[0]))
            except ValueError:
                return self._json(400, {'ok':False,'error':'invalid_range','orders':False})
            if not meta['exists']:
                return self._json(404,meta)
            self.send_response(200)
            self.send_header('Content-Type','application/octet-stream')
            self.send_header('Content-Length',str(len(raw)))
            self.send_header('Cache-Control','no-store')
            for key in ('offset','next_offset','total_bytes','sha256'):
                self.send_header('X-Evidence-'+key.replace('_','-'),str(meta[key]))
            self.end_headers();self.wfile.write(raw)
            return
        if path == "/health":
            return self._json(200, {
                "ok": True,
                "mode": "READ_ONLY_PATH_EXPORT_BRIDGE_V1",
                "collector_script": str(COLLECTOR),
                "event_csv": str(EVENT_CSV),
                "orders": False,
            })

        if path == "/research/path-summary":
            return self._json(200, summarize())

        if path == "/research/path-export":
            if not EXPORT_ENABLE:
                return self._json(403, {
                    "ok": False,
                    "error": "PATH_EXPORT_ENABLE is not 1",
                    "orders": False,
                })
            if not event_path.exists():
                return self._json(404, {"ok": False, "error": "event_csv_missing", "orders": False})

            # Hash and stream one fixed append-only prefix, not two different
            # growing-file views or a full in-memory copy.
            with event_path.open('rb') as stream:
                size=os.fstat(stream.fileno()).st_size;left=size;digest=hashlib.sha256()
                while left:
                    chunk=stream.read(min(65536,left))
                    if not chunk:raise RuntimeError('Evidence file shortened')
                    digest.update(chunk);left-=len(chunk)
                stream.seek(0)
                self.send_response(200)
                self.send_header("Content-Type", "text/csv; charset=utf-8")
                self.send_header("Content-Disposition", 'attachment; filename="'+event_path.name+'"')
                self.send_header("Content-Length", str(size))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Source-SHA256", digest.hexdigest())
                self.end_headers();left=size
                while left:
                    chunk=stream.read(min(65536,left))
                    if not chunk:raise RuntimeError('Evidence file shortened')
                    self.wfile.write(chunk);left-=len(chunk)
            return

        return self._json(404, {"ok": False, "error": "not_found", "orders": False})

def start_server():
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    t = threading.Thread(target=srv.serve_forever, name="path-export-http", daemon=True)
    t.start()
    print(
        f"PATH EXPORT BRIDGE V1 START | port {PORT} | READ ONLY | "
        f"EXPORT {'ENABLED' if EXPORT_ENABLE else 'DISABLED'} | NO ORDERS",
        flush=True,
    )
    return srv, t

def main():
    if not COLLECTOR.exists():
        raise SystemExit(f"collector missing: {COLLECTOR}")
    start_server()
    # Run the exact existing collector script in-process; no payload edits.
    runpy.run_path(str(COLLECTOR), run_name="__main__")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
