"""Only the authorized display indicators; all Coinbase responses are fixtures."""
import json
import math
from pathlib import Path
import unittest
from types import SimpleNamespace

from btc15_v2_product.indicators import calculate, ema, IndicatorFeed, MAX_CLOSE_AGE

END = 1791200400.


def candles(end=END, count=300):
    return [[end-(count-i)*60, 79900.+i, 80100.+i, 80000.+i,
             80000.+i+20*math.sin(i*.3), 1.+i*.01] for i in range(count)]


class IndicatorTests(unittest.TestCase):
    def test_wilder_reference_and_sma_seeded_ema(self):
        # Independently published-style hand worksheet for the classic RSI seed.
        closes=[44.34,44.09,44.15,43.61,44.33,44.83,45.10,45.42,
                45.84,46.08,45.89,46.03,45.61,46.28,46.28]
        gains=sum(max(b-a,0) for a,b in zip(closes,closes[1:]))/14
        losses=sum(max(a-b,0) for a,b in zip(closes,closes[1:]))/14
        self.assertAlmostEqual(100-100/(1+gains/losses),70.4641350211,places=8)
        prices=closes+[closes[-1]]*19
        rsi_rows=[[END-(34-i)*60,1.,100.,v,v,2.] for i,v in enumerate(prices)]
        self.assertAlmostEqual(calculate(rsi_rows,END,END+2)['rsi'],70.4641350211,places=8)
        self.assertEqual(ema([1.,2.,3.,4.,5.],3),[None,None,2.,3.,4.])
        # Linear closes: steady EMA12-EMA26 is seven dollars after SMA seeding.
        rows=[[END-(40-i)*60, 1.,100.,10.+i,10.+i,2.] for i in range(40)]
        v=calculate(rows,END,END+2)
        self.assertEqual((v['rsi'],v['macd'],v['signal'],v['histogram'],v['volume']),(100.,7.,7.,0.,2.))
        # Preserve a flat RSI as neutral rather than fabricating a price change.
        for r in rows:r[3]=r[4]=10.
        self.assertEqual(calculate(rows,END,END+2)['rsi'],50.)

    def test_no_partial_future_synthetic_or_missing_history(self):
        rows=candles();expected=calculate(rows,END,END+2)
        partial=[END,1.,900000.,1.,900000.,0.]
        self.assertEqual(calculate(rows+[partial],END,END+2),expected)
        for invalid in [[],rows[:-2]+rows[-1:],rows+[[END+60,1.,2.,1.,1.,1.]],
                        [*rows[:-1],[*rows[-1][:-1],-1.]], [*rows, [*rows[-1][:-1],999.]]]:
            with self.subTest(invalid=len(invalid)), self.assertRaises(ValueError):calculate(invalid,END,END+2)
        self.assertEqual(expected['volume'],rows[-1][-1])
        one=calculate(rows[-1:],END,END+2)
        self.assertEqual(one['volume'],rows[-1][-1]);self.assertIsNone(one['rsi']);self.assertIsNone(one['macd'])
        fifteen=calculate(rows[-15:],END,END+2)
        self.assertIsNotNone(fifteen['rsi']);self.assertIsNone(fifteen['macd'])
        with self.assertRaisesRegex(ValueError,'STALE'):calculate(rows,END,END+75)
        with self.assertRaisesRegex(ValueError,'CAUSAL'):calculate(rows,END+60,END+2)

    def test_completed_contract_rollover_and_fail_closed(self):
        now=[END+2];payload=[candles()];calls=[]
        def get(url,**kwargs):
            calls.append((url,kwargs));return SimpleNamespace(raise_for_status=lambda:None,json=lambda:payload[0])
        feed=IndicatorFeed(get,lambda:now[0]);feed.sample();count=0;closes=[]
        for second in range(961):
            now[0]=END+2+second
            if second and second%60==0:
                payload[0]=candles(END+second);feed.sample()
            v=feed.capture();self.assertEqual(v['status'],'AVAILABLE')
            self.assertLessEqual(v['candle_close'],now[0]);self.assertEqual(v['volume'],3.99)
            closes.append(v['candle_close']);count+=1
        self.assertEqual(len(calls),17)
        # Browser polling never fetches upstream candles.
        for _ in range(100):feed.capture()
        self.assertEqual(len(calls),17)
        now[0]=closes[-1]+MAX_CLOSE_AGE
        self.assertEqual(feed.capture()['status'],'UNAVAILABLE')
        payload[0]=[];feed.sample();self.assertEqual(feed.capture()['status'],'UNAVAILABLE')
        out=Path(__file__).parent/'qualification/final_completion_20261005';out.mkdir(parents=True,exist_ok=True)
        (out/'indicators-contract.json').write_text(json.dumps(dict(status='PASS',samples=count,
            completed_candle_refreshes=17,partial_bars_used=0,contract_and_rollover=True,
            insufficient_and_stale_closed=True,source='COINBASE_BTC_USD_COMPLETED_1M',
            close_age_limit_seconds=75,authority='DISPLAY_ONLY'),indent=2)+'\n')

    def test_request_crossing_minute_does_not_skip_the_next_completed_bar(self):
        now=[END+59.9]
        def get(url,**kwargs):
            now[0]=END+60.9
            return SimpleNamespace(raise_for_status=lambda:None,json=lambda:candles(END))
        feed=IndicatorFeed(get,lambda:now[0]);feed.sample()
        self.assertEqual(feed.last_cutoff+62,END+62)
        self.assertEqual(feed.capture()['status'],'AVAILABLE')


if __name__=='__main__':unittest.main()
