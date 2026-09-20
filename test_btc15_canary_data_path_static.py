#!/usr/bin/env python3
"""Audit the complete canary chain, including packaged V13 Python, without running it.

No bot imports, credentials, network, orders, or filesystem writes. The preflight
runs this gate before the installer or any full-bot child can start.
"""
import ast
import base64
import gzip
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUNNER = "btc15_dashboard_ws_canary_runner_v1.py"
INSTALLER = "BTC15_INSTALL_LIVE_DASHBOARD_V13.py"
BOT = "bot_two_output_build_v4_13_profit_protection_shadow.py"
HELPER = "btc15_data_paths_v1.py"
DASHBOARD = "BTC15_DASHBOARD_STATE_V2.py"
PARITY = "btc15_kalshi_parity_shadow_v1.py"
RESCUE = "btc15_run_with_rescue_v2_shadow_v1.py"
PROTECT = "btc15_final_position_protection_shadow_v3.py"

# Every runtime data binding, including reader inputs, must share the root.
BOT_FILES = {
    "_ladder_state_path": "kalshi_15m_ladder_state.json",
    "_snapshot_log": "kalshi_two_output_live_log_v4_13.csv",
    "SNAPSHOT_LOG": "kalshi_scalp_shadow_snapshots_v1.csv",
    "EVENT_LOG": "kalshi_scalp_shadow_events_v1.csv",
    "STATE_FILE": "kalshi_scalp_shadow_state_v1.json",
    "BRTI_PARITY_LOG": "kalshi_direct_brti_parity_v1.csv",
    "EARLY_CONF_LOG": "kalshi_early_conf_shadow_v1_2.csv",
    "UNIFIED_SUBMINUTE_LOG": "kalshi_subminute_unified_v1_1.csv",
    "TRUE_SCALP_LOG": "kalshi_true_scalp_forward_shadow_v1.csv",
    "PROFIT_SHADOW_LOG": "kalshi_profit_protection_forward_shadow_v1.csv",
}
ROOT_FILES = {
    RESCUE: {"UNIFIED": BOT_FILES["UNIFIED_SUBMINUTE_LOG"],
             "OUT": "kalshi_rescue_v2_shadow_v1.csv",
             "STATE": "kalshi_rescue_v2_shadow_state_v1.json"},
    PROTECT: {"SOURCE": BOT_FILES["UNIFIED_SUBMINUTE_LOG"],
              "OUT": "kalshi_final_position_protection_shadow_v3.csv",
              "STATE": "kalshi_final_position_protection_shadow_v3_state.json"},
    PARITY: {"UNIFIED": BOT_FILES["UNIFIED_SUBMINUTE_LOG"],
             "BRTI_LOG": BOT_FILES["BRTI_PARITY_LOG"],
             "OUT": "kalshi_app_parity_shadow_v1.csv"},
    DASHBOARD: {"OUT": "dashboard_state.json"},
}
DASHBOARD_FILES = {
    "unified": BOT_FILES["UNIFIED_SUBMINUTE_LOG"],
    "live": BOT_FILES["_snapshot_log"],
    "rescue": ROOT_FILES[RESCUE]["OUT"],
    "parity": ROOT_FILES[PARITY]["OUT"],
    "protect": ROOT_FILES[PROTECT]["OUT"],
}
REQUIRED = {
    RUNNER, "btc15_dashboard_ws_canary_preflight_v1.py", INSTALLER, HELPER,
    "BTC15_DASHBOARD_INLINE_SCALP_DIAG_V2.py", "BTC15_DASHBOARD_INLINE_SCALP_V1.py",
    "BTC15_DASHBOARD_RENDER_FIX_V1.py", "BTC15_RUN_FULL_VALIDATION_WITH_DASHBOARD_V1.py",
    "BTC15_DASHBOARD_LIVE_SERVER_V1.py", DASHBOARD,
    "btc15_run_full_validation_v1.py", "btc15_run_with_rescue_v2_and_parity_v1.py",
    RESCUE, PARITY, PROTECT, BOT,
    "btc15_brti_shared_consumer_v1.py", "btc15_brti_ws_gateway_client_v1.py",
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def dump(node):
    return ast.dump(node, include_attributes=False)


def expr(text):
    return dump(ast.parse(text, mode="eval").body)


def assignments(tree, name):
    return [n for n in ast.walk(tree) if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == name for t in n.targets)]


def binding(tree, name, expected):
    found = assignments(tree, name)
    require(len(found) == 1 and dump(found[0].value) == expr(expected),
            f"{name} must be assigned exactly once to {expected}")
    return found[0]


def load_sources(root=ROOT):
    # Parse the installer as data; importing/exec'ing a bot here is forbidden.
    sources = {p.name: p.read_text() for p in root.glob("*.py")}
    tree = ast.parse(sources[INSTALLER])
    payloads = ast.literal_eval(assignments(tree, "PAYLOADS")[0].value)
    for name, payload in payloads.items():
        if name.endswith(".py"):
            require(name not in sources, f"ambiguous packaged/repository module: {name}")
            sources[name] = gzip.decompress(base64.b64decode(payload)).decode()
    return sources, payloads


def runtime_chain(sources, payloads):
    seen, pending = {}, [RUNNER]
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        require(name in sources, f"missing runtime source: {name}")
        tree = ast.parse(sources[name], filename=name)
        seen[name] = tree
        dependencies = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                dependencies.update(a.name.split(".")[0] + ".py" for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                dependencies.add(node.module.split(".")[0] + ".py")
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value.endswith(".py") and "\n" not in node.value:
                    dependency = Path(node.value).name
                    # Preflight test programs are independent gates, not bot children.
                    if not dependency.startswith("test_"):
                        require(dependency in sources, f"{name}: missing child {dependency}")
                        dependencies.add(dependency)
        if name == INSTALLER:
            dependencies.update(p for p in payloads if p.endswith(".py"))
        pending.extend(d for d in dependencies if d in sources and not d.startswith("test_"))
    require(REQUIRED <= seen.keys(), "runtime chain lost audited children: " +
            ", ".join(sorted(REQUIRED - seen.keys())))
    return seen


def audit(sources, payloads):
    trees = runtime_chain(sources, payloads)
    allowed_nodes = {name: set() for name in trees}

    def allow(name, node):
        allowed_nodes[name].update(id(n) for n in ast.walk(node))

    for variable, filename in BOT_FILES.items():
        allow(BOT, binding(trees[BOT], variable, f"_btc15_data_path({filename!r})"))
    for name, files in ROOT_FILES.items():
        root_expr = "_btc15_data_root()" if name == PARITY else "_btc15_data_root(legacy_cwd_fallback=True)"
        binding(trees[name], "DATA_ROOT", root_expr)
        for variable, filename in files.items():
            allow(name, binding(trees[name], variable, f"DATA_ROOT / {filename!r}"))
    allow(DASHBOARD, binding(trees[DASHBOARD], "FILES", repr(DASHBOARD_FILES)))

    # Only these two packaged historical/model inputs are deliberately not data-root files.
    binding(trees[BOT], "_fair_cache_path", "Path('btc_35d_live_cache.csv')")
    for node in ast.walk(trees[BOT]):
        if isinstance(node, ast.Call) and dump(node) in {
            expr("pd.read_csv('brti_calibration_results.csv')"),
            expr("Path('btc_35d_live_cache.csv')"),
        }:
            allow(BOT, node)

    # The shared helper owns the only executable production-root defaults.
    root_fn = next(n for n in trees[HELPER].body if isinstance(n, ast.FunctionDef)
                   and n.name == "_btc15_data_root")
    for node in ast.walk(root_fn):
        if isinstance(node, ast.Call) and dump(node) in {
            expr("Path('/data')"), expr("Path('/tmp/btc15-canary-data')"),
            expr("os.getenv('BTC15_DATA_DIR', '/data')"),
        }:
            allow(HELPER, node)

    # Remote production-data download remains an OFF-canary diagnostic only.
    pull = next(n for n in trees[DASHBOARD].body if isinstance(n, ast.FunctionDef)
                and n.name == "pull_local_files")
    guard = ast.parse('if _btc15_isolated_canary():\n    raise RuntimeError("Railway production-data pull is disabled in isolated canary mode")').body[0]
    require(dump(pull.body[0]) == dump(guard), "dashboard pull must reject isolated canaries first")
    allow(DASHBOARD, binding(trees[DASHBOARD], "remote", "f'/data/{filename}'"))
    for node in ast.walk(trees[DASHBOARD]):
        if isinstance(node, ast.If) and dump(node.test) == expr("args.pull and DATA_ROOT != Path('/data')"):
            allow(DASHBOARD, node.test)

    # Atomic temp files must remain siblings of the already-isolated state files.
    for name in (RESCUE, PROTECT):
        allow(name, binding(trees[name], "tmp", "STATE.with_suffix('.tmp')"))

    for name, tree in trees.items():
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            value = node.value
            if id(node) in allowed_nodes[name]:
                continue
            # Documentation/JS/HTML strings are not filesystem paths.
            if "\n" in value:
                continue
            if value == "/data" or value.startswith("/data/"):
                raise ValueError(f"{name}:{node.lineno}: production path bypass: {value}")
            if value.endswith((".csv", ".json", ".tmp")):
                # A web route, not a disk path.
                if name == "BTC15_DASHBOARD_LIVE_SERVER_V1.py" and value == "/dashboard_state.json":
                    continue
                raise ValueError(f"{name}:{node.lineno}: unreviewed runtime data path: {value}")

    # Extraction must make the helper available beside the packaged state builder.
    installer = sources[INSTALLER]
    for marker in ['helper = Path(__file__).with_name("btc15_data_paths_v1.py")',
                   '(d/helper.name).write_bytes(helper.read_bytes())']:
        require(marker in installer, "installer does not package shared helper: " + marker)
    preflight = sources["btc15_dashboard_ws_canary_preflight_v1.py"]
    require('"test_btc15_canary_data_path_static.py"' in preflight,
            "data-path gate missing from preflight")
    return trees


def check_root_behavior(sources):
    # Execute only the small, side-effect-free helper; mock all filesystem calls.
    import os
    from unittest.mock import patch
    scope = {}
    exec(compile(sources[HELPER], HELPER, "exec"), scope)
    root = scope["_btc15_data_root"]
    data_path = scope["_btc15_data_path"]
    for isolated in ("1", " 1 ", "0", ""):
        for mounted in (False, True):
            for override in (None, "/custom/btc15-test-data"):
                env = {} if override is None else {"BTC15_DATA_DIR": override}
                if isolated:
                    env["BTC15_ISOLATED_CANARY_LOCAL_DATA"] = isolated
                with patch.dict(os.environ, env, clear=True), \
                     patch.object(Path, "exists", return_value=mounted), \
                     patch.object(Path, "mkdir") as mkdir:
                    expected = Path("/tmp/btc15-canary-data" if isolated.strip() == "1"
                                    else override or "/data")
                    require(root() == expected, "wrong bot/parity root")
                    mkdir.assert_called_with(parents=True, exist_ok=True)
                    require(data_path("probe.csv") == expected / "probe.csv", "wrong data path")
                    legacy = expected if isolated.strip() == "1" else Path("/data" if mounted else ".")
                    require(root(legacy_cwd_fallback=True) == legacy, "legacy child root drift")
    for bad in ("", ".", "..", "/data/escape.csv", "../escape.csv", "nested/escape.csv"):
        try:
            data_path(bad)
        except ValueError:
            pass
        else:
            raise ValueError("data helper accepts escaping filename")


def main():
    sources, payloads = load_sources()
    trees = audit(sources, payloads)
    check_root_behavior(sources)
    print(f"BTC15_CANARY_DATA_PATH_GATE_PASS | {len(trees)} RUNTIME SOURCES INCLUDING V13 PAYLOADS | SHARED ISOLATED /tmp | PRODUCTION DEFAULTS PRESERVED | NO NETWORK | NO ORDERS")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, SyntaxError, KeyError, StopIteration) as exc:
        raise SystemExit("STOP canary data-path gate: " + str(exc))
