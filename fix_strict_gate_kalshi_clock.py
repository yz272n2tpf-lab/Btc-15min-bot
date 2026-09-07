from pathlib import Path
import shutil
import subprocess
import sys

BOT = Path("bot.py")
BACKUP = Path("bot_before_kalshi_clock_fix.py")

OLD = (
'    _strict_now_ts = live_valid.index[-1]\n'
'\n'
'    if getattr(_strict_now_ts, "tzinfo", None) is None:\n'
'        _strict_now_ts = pd.Timestamp(_strict_now_ts, tz="UTC")\n'
'    else:\n'
'        _strict_now_ts = pd.Timestamp(_strict_now_ts).tz_convert("UTC")\n'
'\n'
'    _strict_bucket = _strict_now_ts.floor("15min")\n'
'    _strict_elapsed_minute = (\n'
'        (_strict_now_ts - _strict_bucket).total_seconds() / 60.0\n'
'    )\n'
)

NEW = (
'    # Use the ACTUAL active Kalshi contract clock.\n'
'    _strict_now_ts = pd.Timestamp(datetime.now(timezone.utc))\n'
'\n'
'    _strict_kalshi_markets = get_kalshi_btc_markets()\n'
'    _strict_active_market = None\n'
'    _strict_active_close = None\n'
'\n'
'    for _strict_market in _strict_kalshi_markets:\n'
'        _strict_ticker = str(_strict_market.get("ticker", ""))\n'
'\n'
'        if not _strict_ticker.startswith("KXBTC15M"):\n'
'            continue\n'
'\n'
'        _strict_open_raw = _strict_market.get("open_time")\n'
'        _strict_close_raw = _strict_market.get("close_time")\n'
'\n'
'        if not _strict_open_raw or not _strict_close_raw:\n'
'            continue\n'
'\n'
'        try:\n'
'            _strict_open_ts = pd.Timestamp(_strict_open_raw)\n'
'            _strict_close_ts = pd.Timestamp(_strict_close_raw)\n'
'\n'
'            if _strict_open_ts.tzinfo is None:\n'
'                _strict_open_ts = _strict_open_ts.tz_localize("UTC")\n'
'            else:\n'
'                _strict_open_ts = _strict_open_ts.tz_convert("UTC")\n'
'\n'
'            if _strict_close_ts.tzinfo is None:\n'
'                _strict_close_ts = _strict_close_ts.tz_localize("UTC")\n'
'            else:\n'
'                _strict_close_ts = _strict_close_ts.tz_convert("UTC")\n'
'\n'
'        except Exception:\n'
'            continue\n'
'\n'
'        if _strict_open_ts <= _strict_now_ts < _strict_close_ts:\n'
'            if (\n'
'                _strict_active_market is None\n'
'                or _strict_close_ts < _strict_active_close\n'
'            ):\n'
'                _strict_active_market = _strict_market\n'
'                _strict_active_close = _strict_close_ts\n'
'                _strict_active_open = _strict_open_ts\n'
'\n'
'    if _strict_active_market is None:\n'
'        raise RuntimeError("No active Kalshi BTC 15-minute contract found.")\n'
'\n'
'    _strict_elapsed_minute = (\n'
'        (_strict_now_ts - _strict_active_open).total_seconds() / 60.0\n'
'    )\n'
'\n'
'    # Use Kalshi contract open time for the BTC start window.\n'
'    _strict_bucket = _strict_active_open\n'
)

if not BOT.exists():
    raise SystemExit("ERROR: bot.py not found.")

text = BOT.read_text()

if OLD not in text:
    raise SystemExit(
        "ERROR: exact old strict-clock block not found. No changes made."
    )

shutil.copy2(BOT, BACKUP)
BOT.write_text(text.replace(OLD, NEW, 1))

result = subprocess.run(
    [sys.executable, "-m", "py_compile", str(BOT)],
    capture_output=True,
    text=True,
)

if result.returncode != 0:
    shutil.copy2(BACKUP, BOT)
    print("=== KALSHI CLOCK FIX FAILED ===")
    print(result.stderr)
    print("Automatic rollback completed.")
    raise SystemExit(1)

print("=== STRICT GATE KALSHI CLOCK FIX COMPLETE ===")
print("Backup created:", BACKUP.name)
print("Syntax check: PASSED")
print("Elapsed-minute source: ACTIVE KALSHI CONTRACT")
print("Scalp logic changed: NO")
print("Order-placement code added: NO")
print("Signal-only behavior preserved: YES")
print()
print("NEXT: run bot.py and inspect elapsed contract minute.")
