#!/usr/bin/env python3
"""Read-only GET of official Kalshi markets for the exact frozen 51 tickers."""
import concurrent.futures
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
EXPECTED = '7b26852ee6b148761003fee6fa8ac90ba2d19bee5e78774f7800f91d126e6eb1'
BASE = 'https://api.elections.kalshi.com/trade-api/v2/markets/'

def fetch(call):
    ticker = call['contract']
    url = BASE + ticker
    request = Request(url, headers={'Accept': 'application/json'}, method='GET')
    with urlopen(request, timeout=35) as response:
        body = response.read()
        market = json.loads(body)['market']
        assert response.status == 200 and market['ticker'] == ticker
        assert market['status'] == 'finalized' and market['result'] in ('yes', 'no')
        assert market.get('settlement_ts')
        (ROOT / 'official' / (ticker + '.json')).write_bytes(body)
        return {'contract': ticker, 'url': url, 'method': 'GET',
                'retrieved_at_utc': datetime.now(timezone.utc).isoformat(),
                'http_status': response.status, 'response_headers': dict(response.headers),
                'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest(),
                'result': market['result'], 'status': market['status']}

def main():
    raw = (ROOT / 'inputs/early_entries.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == EXPECTED
    calls = json.loads(raw)
    assert len(calls) == len({c['contract'] for c in calls}) == 51
    (ROOT / 'official').mkdir(exist_ok=True)
    receipts, errors = [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        jobs = {pool.submit(fetch, call): call['contract'] for call in calls}
        for future in concurrent.futures.as_completed(jobs):
            try:
                receipts.append(future.result())
                print(f"{len(receipts)}/51 official finalized responses", flush=True)
            except Exception as exc:
                errors.append({'contract': jobs[future], 'error': repr(exc)})
    by_id = {r['contract']: r for r in receipts}
    payload = {'source': BASE, 'calls_sha256': EXPECTED,
               'receipts': [by_id[c['contract']] for c in calls if c['contract'] in by_id],
               'errors': errors}
    (ROOT / 'retrieval_manifest.json').write_text(json.dumps(payload, indent=2, sort_keys=True)+'\n')
    print(json.dumps({'official_results':len(receipts),'errors': errors}))
    if errors:
        raise SystemExit(1)

if __name__ == '__main__':
    main()
