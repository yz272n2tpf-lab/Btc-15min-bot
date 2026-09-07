# ============================================================
# BRIDGE V3 SAFETY-LOGIC TEST
#
# PURPOSE:
#   Verify the combined READY/WAIT logic around:
#     - the validated +/- $11 BRTI danger zone
#     - model/BRTI disagreement
#     - model-not-ready cases
#
# This is a deterministic logic test.
# It does NOT contact Kalshi.
# It does NOT place orders.
# It does NOT change bot.py.
# ============================================================

BUFFER = 11.0


def evaluate_case(
    name,
    model_direction,
    strict_model_ready,
    adjusted_brti_gap,
):
    if adjusted_brti_gap > 0:
        brti_direction = "UP"
    elif adjusted_brti_gap < 0:
        brti_direction = "DOWN"
    else:
        brti_direction = "FLAT"

    inside_wait_zone = abs(adjusted_brti_gap) <= BUFFER

    brti_agrees = (
        brti_direction == model_direction
    )

    brti_gate_ready = (
        not inside_wait_zone
        and brti_agrees
    )

    combined_ready = (
        strict_model_ready
        and brti_gate_ready
    )

    print()
    print(f"CASE: {name}")
    print("Model direction:", model_direction)
    print(
        "Strict model ready:",
        "YES" if strict_model_ready else "NO",
    )
    print(
        "Adjusted BRTI gap:",
        f"${adjusted_brti_gap:+.2f}",
    )
    print("BRTI direction:", brti_direction)
    print(
        "Inside +/-$11 WAIT zone:",
        "YES" if inside_wait_zone else "NO",
    )
    print(
        "BRTI agrees with model:",
        "YES" if brti_agrees else "NO",
    )
    print(
        "BRTI gate ready:",
        "YES" if brti_gate_ready else "NO",
    )
    print(
        "COMBINED STATUS:",
        "READY" if combined_ready else "WAIT",
    )

    return {
        "name": name,
        "ready": combined_ready,
        "inside_wait_zone": inside_wait_zone,
        "brti_agrees": brti_agrees,
        "brti_gate_ready": brti_gate_ready,
    }


cases = [
    # Exact boundary checks.
    ("UP model, +$10.99", "UP", True, 10.99, False),
    ("UP model, +$11.00", "UP", True, 11.00, False),
    ("UP model, +$11.01", "UP", True, 11.01, True),

    ("DOWN model, -$10.99", "DOWN", True, -10.99, False),
    ("DOWN model, -$11.00", "DOWN", True, -11.00, False),
    ("DOWN model, -$11.01", "DOWN", True, -11.01, True),

    # Strong BRTI disagreement must ALWAYS wait.
    ("UP model vs strong DOWN BRTI", "UP", True, -50.00, False),
    ("DOWN model vs strong UP BRTI", "DOWN", True, 50.00, False),

    # Model not ready must ALWAYS wait, even with BRTI agreement.
    ("UP agrees but model not ready", "UP", False, 50.00, False),
    ("DOWN agrees but model not ready", "DOWN", False, -50.00, False),

    # Strong agreement + strict model ready should be READY.
    ("Strong UP confirmation", "UP", True, 50.00, True),
    ("Strong DOWN confirmation", "DOWN", True, -50.00, True),

    # Exactly flat must wait.
    ("UP model, flat BRTI", "UP", True, 0.00, False),
    ("DOWN model, flat BRTI", "DOWN", True, 0.00, False),
]

print("=== BRIDGE V3 SAFETY LOGIC TEST ===")
print("Validated BRTI buffer:", f"+/-${BUFFER:.2f}")

results = []
failures = []

for (
    name,
    model_direction,
    strict_model_ready,
    gap,
    expected_ready,
) in cases:
    result = evaluate_case(
        name,
        model_direction,
        strict_model_ready,
        gap,
    )

    result["expected_ready"] = expected_ready
    results.append(result)

    if result["ready"] != expected_ready:
        failures.append(
            {
                "name": name,
                "expected": expected_ready,
                "actual": result["ready"],
            }
        )


print()
print("=== TEST SUMMARY ===")
print("Cases tested:", len(results))
print("Passed:", len(results) - len(failures))
print("Failed:", len(failures))

if failures:
    print()
    print("FAILURE DETAILS:")
    for f in failures:
        print(
            f"{f['name']} | "
            f"expected READY={f['expected']} | "
            f"actual READY={f['actual']}"
        )
else:
    print(
        "ALL SAFETY-LOGIC CASES PASSED."
    )

print()
print("=== REQUIRED SAFETY BEHAVIOR ===")
print("Inside +/-$11: WAIT")
print("Model/BRTI disagreement: WAIT")
print("Model not strict-ready: WAIT")
print("Only strict-model-ready + BRTI outside buffer + agreement: READY")

print()
print("Orders placed: NO")
print("bot.py changed: NO")
