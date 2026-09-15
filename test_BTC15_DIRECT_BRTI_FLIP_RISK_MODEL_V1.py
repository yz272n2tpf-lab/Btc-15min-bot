import unittest
import numpy as np
import pandas as pd

import BTC15_DIRECT_BRTI_FLIP_RISK_MODEL_V1 as m


class DirectBRTIFlipRiskV1Tests(unittest.TestCase):
    def tape(self, contract='C', n=181, target=100.0):
        t0=pd.Timestamp('2026-09-15T20:00:00Z')
        rows=[]
        for i in range(n):
            elapsed=i*5
            rows.append({
                'timestamp_utc':t0+pd.Timedelta(seconds=elapsed),
                'contract':contract,
                'target':target,
                'seconds_left':900.0-elapsed,
                'direct_brti':100.0+0.01*i,
                'brti_age_seconds':1.0,
                'direct_brti_ready':True,
                'ready_bool':True,
            })
        return pd.DataFrame(rows)

    def test_feature_set_has_no_start_or_coinbase_inputs(self):
        joined=' '.join(m.FEATURES).lower()
        self.assertNotIn('start',joined)
        self.assertNotIn('coinbase',joined)
        self.assertEqual(len(m.FEATURES),12)

    def test_lag_lookup_is_causal(self):
        g=self.tape(n=100)
        snap=g.iloc[80]['timestamp_utc']
        requested=snap-pd.Timedelta(seconds=60)
        # Add an extreme future row just after the requested lag instant. A bad
        # nearest-neighbor implementation could leak this value.
        future=pd.DataFrame([{
            'timestamp_utc':requested+pd.Timedelta(seconds=1),
            'contract':'C','target':100.0,'seconds_left':0.0,
            'direct_brti':999.0,'brti_age_seconds':1.0,
            'direct_brti_ready':True,'ready_bool':True,
        }])
        g=pd.concat([g,future],ignore_index=True).sort_values('timestamp_utc')
        got=m._lag_price(g,snap,60.0)
        expected=float(g[(g.timestamp_utc<=requested)&(g.direct_brti!=999.0)].iloc[-1].direct_brti)
        self.assertAlmostEqual(got,expected)
        self.assertNotEqual(got,999.0)

    def test_feature_snapshot_requires_five_minute_history(self):
        short=self.tape(n=50)  # <300 seconds total
        self.assertIsNone(m.feature_snapshot(short,9,'UP'))
        full=self.tape(n=181)
        row=m.feature_snapshot(full,9,'UP')
        self.assertIsNotNone(row)
        self.assertEqual(row['target_remaining_min'],9)
        self.assertTrue(all(np.isfinite(row[c]) for c in m.FEATURES))

    def test_snapshot_tie_breaks_to_earlier_timestamp(self):
        g=self.tape(n=181)
        # Remove exact 540s-left row and create equal +/-2s candidates around it.
        g=g[(g.seconds_left-540.0).abs()>0.1].copy()
        base=g.iloc[0].timestamp_utc
        extra=pd.DataFrame([
            {'timestamp_utc':base+pd.Timedelta(seconds=358),'contract':'C','target':100.0,'seconds_left':542.0,'direct_brti':101.0,'brti_age_seconds':1.0,'direct_brti_ready':True,'ready_bool':True},
            {'timestamp_utc':base+pd.Timedelta(seconds=362),'contract':'C','target':100.0,'seconds_left':538.0,'direct_brti':102.0,'brti_age_seconds':1.0,'direct_brti_ready':True,'ready_bool':True},
        ])
        g=pd.concat([g,extra],ignore_index=True).sort_values('timestamp_utc')
        row=m.feature_snapshot(g,9,'UP')
        self.assertIsNotNone(row)
        self.assertEqual(row['snapshot_ts'],base+pd.Timedelta(seconds=358))

    def test_walkforward_test_contracts_are_disjoint_and_total_44(self):
        contracts=[f'C{i:02d}' for i in range(94)]
        rows=[]
        for i,c in enumerate(contracts):
            r={'contract':c,'flip':i%2,'target_remaining_min':5,'snapshot_ts':pd.Timestamp('2026-09-01T00:00:00Z')+pd.Timedelta(minutes=i)}
            for j,f in enumerate(m.FEATURES):
                r[f]=float((i+1)*(j+1))/1000.0
            rows.append(r)
        ds=pd.DataFrame(rows)
        oos,metrics,integrity=m.run_walkforward(ds,contracts)
        self.assertTrue(integrity['block_disjoint'])
        self.assertTrue(integrity['block_chronological'])
        self.assertEqual(oos.contract.nunique(),44)
        self.assertEqual(len(metrics),3)
        sets=[set(oos[oos.block==b].contract) for b in (1,2,3)]
        self.assertFalse(sets[0]&sets[1])
        self.assertFalse(sets[0]&sets[2])
        self.assertFalse(sets[1]&sets[2])

    def test_fixed_blocks_match_freeze(self):
        self.assertEqual(m.BLOCKS[0][1:],(slice(0,40),slice(40,50),slice(50,65)))
        self.assertEqual(m.BLOCKS[1][1:],(slice(0,55),slice(55,65),slice(65,80)))
        self.assertEqual(m.BLOCKS[2][1:],(slice(0,70),slice(70,80),slice(80,94)))


if __name__=='__main__':
    unittest.main()
