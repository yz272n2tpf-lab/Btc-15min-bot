"""Regression: the bounded event replay cannot erase saved checkpoint history."""
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import zlib

from btc15_v2_product import REVISION
from btc15_v2_product.early_origin_transfer import PREDECESSORS, transfer
from btc15_v2_product.directional import Directional


class MemoryJournal:
    def __init__(self):
        self.db = sqlite3.connect(':memory:')
        self.db.execute('CREATE TABLE meta(k TEXT PRIMARY KEY, v TEXT NOT NULL)')
        self.db.execute('INSERT INTO meta VALUES (?, ?)', ('lane', 'main'))
        self.db.commit()

    def get(self, key):
        row = self.db.execute('SELECT v FROM meta WHERE k=?', (key,)).fetchone()
        return json.loads(row[0]) if row else None


class HandoffHistoryRegression(unittest.TestCase):
    def test_checkpoint_history_survives_when_origin_outside_event_tail(self):
        deployment, build = PREDECESSORS['main']
        # The checkpoint has a historical signal absent from the latest 2048
        # events. No original journal is ever opened for writing by transfer.
        old = dict(origin_id='older-buy-not-in-event-tail', contract='KXBTC15M-TEST',
                   side='UP', original_ask=.35, signal_ts=1.0, open_ts=0.0,
                   close_ts=900.0, target=100000, terminal=dict(state='EXIT'))
        saved = dict(signal_history=[old], origin=None, terminal=None)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prior = root / deployment
            prior.mkdir()
            dbpath = prior / 'main.sqlite3'
            with sqlite3.connect(dbpath) as db:
                db.execute('CREATE TABLE meta(k TEXT PRIMARY KEY, v TEXT NOT NULL)')
                db.execute('CREATE TABLE events(seq INTEGER PRIMARY KEY, sha256 TEXT, body BLOB)')
                for k, v in dict(product_revision=REVISION, deployment=deployment,
                                 build=build, lane='main', state=json.dumps(saved)).items():
                    db.execute('INSERT INTO meta VALUES (?, ?)', (k, v))
                raw = json.dumps(dict(published_ts=1.0)).encode()
                sha = hashlib.sha256(raw).hexdigest()
                body = zlib.compress(raw)
                db.executemany('INSERT INTO events VALUES (?, ?, ?)',
                               ((i, sha, body) for i in range(1, 2101)))
            def restore(self, state):
                self.signal_history = state.get('signal_history', [])
                self.origin = state.get('origin')
                self.terminal = state.get('terminal')
            def checkpoint(self):
                return dict(signal_history=self.signal_history,
                            origin=self.origin, terminal=self.terminal)
            journal = MemoryJournal()
            try:
                with patch.object(Directional, 'restore', restore), patch.object(Directional, 'checkpoint', checkpoint):
                    transfer(journal, root / 'new-deployment' / 'main.sqlite3', now=1000)
                state = journal.get('state')
                self.assertEqual(state['signal_history'], [old])
                self.assertEqual(journal.get('origin_transfer')['history_count'], 1)
                with sqlite3.connect(dbpath) as db:
                    self.assertEqual(db.execute('SELECT count(*) FROM events').fetchone()[0], 2100)
            finally:
                journal.db.close()


if __name__ == '__main__':
    unittest.main()
