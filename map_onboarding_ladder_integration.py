from pathlib import Path
import re

BOT = Path("bot.py")

print("=== ONBOARDING LADDER INTEGRATION MAP ===")
print("Purpose: map the exact safe insertion points for the validated live ladder.")
print("bot.py changed: NO")
print("Scalp logic changed: NO")
print("Orders placed: NO")
print()

if not BOT.exists():
    raise SystemExit("ERROR: bot.py not found in this folder.")

text = BOT.read_text()
lines = text.splitlines()

print("Total bot.py lines:", len(lines))
print()

def show(start, end, title):
    start = max(1, start)
    end = min(len(lines), end)
    print("=" * 78)
    print(title)
    print("=" * 78)
    for n in range(start, end + 1):
        print(f"{n:4d}: {lines[n-1]}")
    print()

def find_lines(patterns):
    hits = []
    for n, line in enumerate(lines, start=1):
        low = line.lower()
        if any(p.lower() in low for p in patterns):
            hits.append(n)
    return hits

# ------------------------------------------------------------
# 1) Verify the Kalshi clock repair is still present.
# ------------------------------------------------------------
clock_patterns = [
    "_strict_active_open",
    "_strict_elapsed_minute",
    "active kalshi contract",
    "get_kalshi_btc_markets",
]
clock_hits = find_lines(clock_patterns)

print("=== CLOCK ALIGNMENT CHECK ===")
if clock_hits:
    print("Kalshi-clock related code found: YES")
    print("Matching lines:", sorted(set(clock_hits))[:30])
else:
    print("Kalshi-clock related code found: NO")
print()

for n in sorted(set(clock_hits))[:5]:
    show(n - 12, n + 22, f"CLOCK CONTEXT AROUND LINE {n}")

# ------------------------------------------------------------
# 2) Find current live 15-minute prediction/confidence variables.
# ------------------------------------------------------------
model_patterns = [
    "current 15-minute prediction",
    "current 15-minute confidence",
    "current_prediction",
    "current_confidence",
    "strict model ready",
    "_strict_model_ready",
]
model_hits = find_lines(model_patterns)

print("=== LIVE 15-MIN MODEL MAP ===")
print("Matching lines:", sorted(set(model_hits))[:40] if model_hits else "NONE")
print()

for n in sorted(set(model_hits))[:6]:
    show(n - 10, n + 24, f"LIVE MODEL CONTEXT AROUND LINE {n}")

# ------------------------------------------------------------
# 3) Find Kalshi/BRTI target and odds variables.
# ------------------------------------------------------------
kalshi_patterns = [
    "kalshi target",
    "yes bid",
    "yes ask",
    "no bid",
    "no ask",
    "brti",
    "_strict_active_market",
]
kalshi_hits = find_lines(kalshi_patterns)

print("=== KALSHI / BRTI LIVE MAP ===")
print("Matching lines:", sorted(set(kalshi_hits))[:50] if kalshi_hits else "NONE")
print()

# Show a few non-overlapping contexts.
shown = []
for n in sorted(set(kalshi_hits)):
    if all(abs(n - old) > 25 for old in shown):
        show(n - 10, n + 25, f"KALSHI/BRTI CONTEXT AROUND LINE {n}")
        shown.append(n)
    if len(shown) >= 5:
        break

# ------------------------------------------------------------
# 4) Find current strict/final gate output.
# ------------------------------------------------------------
gate_patterns = [
    "strict 15-min + v3 final gate",
    "expected final outcome",
    "entry status",
    "final 15-min status",
    "current lean",
    "brti/kalshi gate ready",
]
gate_hits = find_lines(gate_patterns)

print("=== CURRENT FINAL-GATE MAP ===")
print("Matching lines:", sorted(set(gate_hits))[:50] if gate_hits else "NONE")
print()

shown = []
for n in sorted(set(gate_hits)):
    if all(abs(n - old) > 20 for old in shown):
        show(n - 18, n + 35, f"FINAL-GATE CONTEXT AROUND LINE {n}")
        shown.append(n)
    if len(shown) >= 4:
        break

# ------------------------------------------------------------
# 5) Locate scalp section boundaries so ladder stays separate.
# ------------------------------------------------------------
scalp_patterns = [
    "--- scalp signal ---",
    "scalp signal",
    "scalp score",
    "reversal watch",
]
scalp_hits = find_lines(scalp_patterns)

print("=== SCALP BOUNDARY MAP ===")
print("Matching lines:", sorted(set(scalp_hits))[:40] if scalp_hits else "NONE")
print()

if scalp_hits:
    first_scalp = min(scalp_hits)
    show(first_scalp - 15, first_scalp + 45, "FIRST SCALP SECTION CONTEXT")

# ------------------------------------------------------------
# 6) Search for state/history capability needed for 7->8 agreement.
# ------------------------------------------------------------
history_patterns = [
    "previous",
    "history",
    "state",
    "last_prediction",
    "prev_prediction",
    "contract",
]
history_hits = find_lines(history_patterns)

print("=== STATE / SAME-CONTRACT MEMORY MAP ===")
print("Potential state/history lines:", sorted(set(history_hits))[:60])
print()

# ------------------------------------------------------------
# 7) Exact recommended integration zones based on current file.
# ------------------------------------------------------------
print("=== INTEGRATION READINESS SUMMARY ===")

checks = {
    "Corrected Kalshi active-contract clock present": bool(clock_hits),
    "Live 15-minute prediction/confidence found": bool(model_hits),
    "Kalshi/BRTI live data found": bool(kalshi_hits),
    "Current strict/final gate found": bool(gate_hits),
    "Scalp section identifiable": bool(scalp_hits),
}

for name, ok in checks.items():
    print(f"{name}: {'PASS' if ok else 'REVIEW'}")

print()
print("VALIDATED LADDER TO INTEGRATE LATER:")
print("1) RAW FORECAST: always-visible live UP/DOWN probability.")
print("2) MINUTE-8 QUALIFIED: minute 7 & 8 directions agree AND both confidence >= 85%.")
print("3) MINUTE-11 FINAL LOCK: (minute 9 & 11 agree AND both >=85%) OR minute-11 confidence >=90%.")
print("4) Keep Kalshi/BRTI contract target and odds visible beside the signal.")
print("5) Do not alter scalp logic.")
print("6) Do not add order-placement code.")
print()

print("=== FINAL 220 LINES FOR EXACT INSERTION REVIEW ===")
show(max(1, len(lines) - 219), len(lines), "FINAL 220 LINES OF CURRENT bot.py")

print("=== MAP COMPLETE ===")
print("No files modified.")
print("NEXT: use this output to build a surgical integration patch against the CURRENT bot.py.")
