from pathlib import Path

BOT = Path("bot.py")

if not BOT.exists():
    raise SystemExit("bot.py not found.")

lines = BOT.read_text().splitlines()

print("=== V3 FINAL INTEGRATION MAP ===")
print("Total bot.py lines:", len(lines))

def show(start, end, title):
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)

    start = max(1, start)
    end = min(len(lines), end)

    for n in range(start, end + 1):
        print(f"{n:4d}: {lines[n-1]}")

# Existing live Kalshi snapshot return area.
show(78, 110, "CURRENT KALSHI SNAPSHOT BLOCK")

# Scalp/reversal handoff.
show(420, 490, "SCALP / REVERSAL BLOCK")

# Most important: current final live-output section.
show(max(1, len(lines) - 150), len(lines), "FINAL 150 LINES OF bot.py")

print()
print("=" * 70)
print("SAFETY CHECK")
print("=" * 70)
print("bot.py modified: NO")
print("Purpose: exact V3 insertion mapping only.")
