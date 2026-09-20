#!/usr/bin/env python3
"""Offline regressions for the canary path gate. Never import/start the live bot."""
import ast
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_btc15_canary_data_path_static as gate
import btc15_data_paths_v1 as paths


class CanaryDataPaths(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources, cls.payloads = gate.load_sources()

    def rejected(self, name, old, new):
        sources = dict(self.sources)
        self.assertIn(old, sources[name])
        sources[name] = sources[name].replace(old, new, 1)
        with self.assertRaises(ValueError):
            gate.audit(sources, self.payloads)

    def test_all_main_paths_reject_hardcoded_production_and_relative_paths(self):
        for filename in gate.BOT_FILES.values():
            for replacement in (f'Path("/data/{filename}")', f'Path("{filename}")'):
                with self.subTest(filename=filename, replacement=replacement):
                    self.rejected(gate.BOT, f'_btc15_data_path("{filename}")', replacement)

    def test_every_child_and_embedded_dashboard_root_is_guarded(self):
        for name in gate.ROOT_FILES:
            old = ('_btc15_data_root()' if name == gate.PARITY
                   else '_btc15_data_root(legacy_cwd_fallback=True)')
            with self.subTest(child=name):
                self.rejected(name, 'DATA_ROOT = ' + old, 'DATA_ROOT = Path("/data")')

    def test_new_runtime_child_is_discovered_and_rejected(self):
        sources = dict(self.sources)
        sources[gate.RUNNER] += '\nimport btc15_unreviewed_child\n'
        sources['btc15_unreviewed_child.py'] = 'from pathlib import Path\nPath("/data/new.csv").touch()\n'
        with self.assertRaisesRegex(ValueError, 'btc15_unreviewed_child.py'):
            gate.audit(sources, self.payloads)

    def test_new_read_write_and_cwd_paths_are_rejected(self):
        for leak in ('open("/data/new.csv", "a")', 'open("/data/state.json")',
                     'Path("new.csv")', 'Path("/tmp/unisolated.json")',
                     'Path("/data") / "new.csv"'):
            sources = dict(self.sources)
            sources[gate.PARITY] += '\n' + leak + '\n'
            with self.subTest(leak=leak), self.assertRaises(ValueError):
                gate.audit(sources, self.payloads)

    def test_embedded_pull_cannot_reach_production(self):
        self.rejected(gate.DASHBOARD, 'if _btc15_isolated_canary():', 'if False:')
        tree = ast.parse(self.sources[gate.DASHBOARD])
        pull = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'pull_local_files')
        scope = {'Dict': dict, '_btc15_isolated_canary': lambda: True}
        exec(compile(ast.Module(body=[pull], type_ignores=[]), gate.DASHBOARD, 'exec'), scope)
        # Missing subprocess/FILES is intentional: reject before either is touched.
        with self.assertRaisesRegex(RuntimeError, 'disabled in isolated canary'):
            scope['pull_local_files']()

    def test_installer_must_copy_helper(self):
        self.rejected(gate.INSTALLER, '(d/helper.name).write_bytes(helper.read_bytes())', 'pass')

    def test_preflight_must_include_gate(self):
        self.rejected('btc15_dashboard_ws_canary_preflight_v1.py',
                      ' "test_btc15_canary_data_path_static.py",', '')

    def test_root_selection_matrix_and_escape_rejection(self):
        gate.check_root_behavior(self.sources)

    def test_canary_creates_missing_directory_and_ignores_production_override(self):
        with tempfile.TemporaryDirectory() as temp:
            sandbox_root = Path(temp) / 'new-canary-root'
            def local_path(value):
                self.assertEqual(value, '/tmp/btc15-canary-data')
                return sandbox_root
            with patch.dict(os.environ, {'BTC15_ISOLATED_CANARY_LOCAL_DATA': '1',
                                         'BTC15_DATA_DIR': '/data'}, clear=True), \
                 patch.object(paths, 'Path', side_effect=local_path):
                self.assertEqual(paths._btc15_data_root(), sandbox_root)
            self.assertTrue(sandbox_root.is_dir())

    def test_all_writers_and_readers_resolve_to_same_canary_root(self):
        # Evaluate only audited path declarations, never the bot's top-level code.
        with patch.dict(os.environ, {'BTC15_ISOLATED_CANARY_LOCAL_DATA': '1',
                                     'BTC15_DATA_DIR': '/data'}, clear=True), \
             patch.object(Path, 'mkdir'):
            scope = {'_btc15_data_path': paths._btc15_data_path,
                     '_btc15_data_root': paths._btc15_data_root}
            root = Path('/tmp/btc15-canary-data')
            for name, variables in {gate.BOT: gate.BOT_FILES, **gate.ROOT_FILES}.items():
                tree = ast.parse(self.sources[name])
                if name != gate.BOT:
                    n = gate.assignments(tree, 'DATA_ROOT')[0]
                    scope['DATA_ROOT'] = eval(compile(ast.Expression(n.value), name, 'eval'), scope)
                for variable, filename in variables.items():
                    n = gate.assignments(tree, variable)[0]
                    value = eval(compile(ast.Expression(n.value), name, 'eval'), scope)
                    self.assertEqual(value, root / filename, (name, variable))
                    if variable == 'STATE':
                        self.assertEqual(value.with_suffix('.tmp').parent, root)

    def test_main_csv_initializers_and_appends_with_missing_data_directory(self):
        # Exercise the actual CSV functions against every bot CSV, with no model,
        # network, authentication, startup or background collection.
        import csv
        tree = ast.parse(self.sources[gate.BOT])
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                     and n.name in {'ensure_csv', 'append_csv'}]
        self.assertEqual(len(functions), 2)
        scope = {'csv': csv}
        exec(compile(ast.Module(body=functions, type_ignores=[]), gate.BOT, 'exec'), scope)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'initially-missing'
            with patch.dict(os.environ, {'BTC15_DATA_DIR': str(root)}, clear=True):
                for filename in gate.BOT_FILES.values():
                    if not filename.endswith('.csv'):
                        continue
                    path = paths._btc15_data_path(filename)
                    scope['ensure_csv'](path, ['canary_probe'])
                    scope['append_csv'](path, ['canary_probe'], {'canary_probe': 'ok'})
                    with path.open() as stream:
                        self.assertEqual(list(csv.DictReader(stream)), [{'canary_probe': 'ok'}])


if __name__ == '__main__':
    unittest.main(verbosity=2)
