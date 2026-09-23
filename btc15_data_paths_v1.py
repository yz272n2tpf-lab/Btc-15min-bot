"""Runtime data paths only; no market logic, network access, or orders."""
import os
from pathlib import Path


def _btc15_isolated_canary():
    return os.getenv("BTC15_ISOLATED_CANARY_LOCAL_DATA", "").strip() == "1"


def _btc15_data_root(*, legacy_cwd_fallback=False):
    if _btc15_isolated_canary():
        base = Path("/tmp/btc15-canary-data")
    elif legacy_cwd_fallback:
        # Preserve the pre-existing off-canary behavior of rescue/protection/UI.
        return Path("/data") if Path("/data").exists() else Path(".")
    else:
        base = Path(os.getenv("BTC15_DATA_DIR", "/data"))
    base.mkdir(parents=True, exist_ok=True)
    return base


def _btc15_data_path(filename):
    # Runtime callers supply basenames; never allow a filename to escape root.
    if not filename or Path(filename).name != filename or filename in {".", ".."}:
        raise ValueError("runtime data filename must be a basename")
    return _btc15_data_root() / filename
