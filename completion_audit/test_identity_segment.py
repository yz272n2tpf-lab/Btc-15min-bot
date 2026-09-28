import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from analyze_identity_segment import load_segment, assess
from cohort_registry import identity, utc


def manifest():
    data = dict(windows=[dict(role='development_tuning',start_utc='2026-09-23T21:15:00Z',end_utc='2026-09-24T21:15:00Z')],
                revisions=dict(clean=dict(run_id='expected')))
    data['canonical_content_sha256_excluding_this_field'] = identity(data)
    return data


class IdentityEvidenceTests(unittest.TestCase):
    def test_validation_window_cannot_be_opened(self):
        with self.assertRaisesRegex(ValueError, 'only open development'):
            load_segment(Path('must-not-be-opened'),manifest(),utc('2026-09-24T21:15:00Z'),utc('2026-09-24T21:30:00Z'))

    def test_modified_manifest_rejected(self):
        m=manifest();m['revisions']['clean']['run_id']='changed'
        with self.assertRaisesRegex(ValueError,'identity mismatch'):
            load_segment(Path('must-not-be-opened'),m,utc('2026-09-24T00:15:00Z'),utc('2026-09-24T01:45:00Z'))

    def test_mixed_run_rejected_even_outside_analysis_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'evidence.gz';p.write_bytes(gzip.compress(json.dumps(dict(run_id='old-five-second',record_type='OBSERVATION',sources=[])).encode()))
            with self.assertRaisesRegex(ValueError,'Mixed collector'):
                load_segment(p,manifest(),utc('2026-09-24T00:15:00Z'),utc('2026-09-24T01:45:00Z'))

    def test_crc_damage_not_silently_dropped(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'evidence.gz';b=bytearray(gzip.compress(json.dumps(dict(run_id='expected',record_type='OBSERVATION',sources=[])).encode()));b[-8]^=1;p.write_bytes(b)
            with self.assertRaisesRegex(ValueError,'CRC/member damage'):
                load_segment(p,manifest(),utc('2026-09-24T00:15:00Z'),utc('2026-09-24T01:45:00Z'))

    def test_excursions_exclude_stale_independent_inputs(self):
        opened='2026-09-24T00:15:00Z';closed='2026-09-24T00:30:00Z';ticker='KXBTC15M-TEST'
        call=dict(contract=ticker,side='UP',observed_utc='2026-09-24T00:20:00Z',entry_ask=.4,sampled_bid_path={'observed_mfe':.6})
        base=dict(lanes={k:dict(calls=[call] if k=='scalp' else []) for k in ('early','final','scalp')})
        def point(t,age,bid):
            now=utc(t)
            return dict(ticker=ticker,target=1,observed_utc=t,quote_validation_utc=t,quote_transport='timestamped_contiguous_ws',
                brti_source_ts_ms=int((now.timestamp()-age)*1000),signal_only=True,orders=False,up_bid=bid,up_ask=bid+.01)
        inputs=[point('2026-09-24T00:20:01Z',6,.95),point('2026-09-24T00:20:02Z',2,.45)]
        with patch('analyze_identity_segment.analyze',return_value=base):
            r=assess([],inputs,[dict(ticker=ticker,open_time=opened,close_time=closed,floor_strike=1)],utc(opened),utc(closed))
        path=r['lanes']['scalp']['calls'][0]['sampled_bid_path']
        self.assertEqual(path['sample_count'],1)
        self.assertAlmostEqual(path['observed_mfe'],.05)
        self.assertFalse(path['entry_ask_confirmed_at_first_quote'])
        self.assertFalse(path['realized_profit'])


if __name__=='__main__': unittest.main()
