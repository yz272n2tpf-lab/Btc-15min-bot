import time
from datetime import datetime, timezone, timedelta

import pandas as pd
import requests
from sklearn.ensemble import RandomForestClassifier


# ============================================================
# BOT 42 — DIST175 LONGER-HISTORY WALK-FORWARD STRESS TEST
#
# Candidate carried forward from Bots 40/41:
#   Minute 8-9
#   confidence >= 95%
#   full 3/3 directional agreement
#   confidence strengthening
#   distance >= 0.175%
#
# Purpose:
#   Stress-test the candidate over longer BTC history.
#   Check:
#       overall accuracy
#       UP accuracy
#       DOWN accuracy
#       fold consistency
#       minute 8 vs minute 9
#       failure details
#
# Diagnostic only.
# Live rules changed: NO
# Scalp logic changed: NO
# ============================================================


def coinbase_history(days, granularity=60):
    url = "https://api.exchange.coinbase.com/products/BTC-USD/candles"

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    rows = []
    step_seconds = granularity * 300
    batch_start = start

    while batch_start < end:
        batch_end = min(
            batch_start + timedelta(seconds=step_seconds),
            end
        )

        params = {
            "granularity": granularity,
            "start": batch_start.isoformat(),
            "end": batch_end.isoformat(),
        }

        r = requests.get(url, params=params, timeout=20)
        r.raise_for_status()

        batch = r.json()

        if isinstance(batch, list):
            rows.extend(batch)

        batch_start = batch_end
        time.sleep(0.04)

    df = pd.DataFrame(
        rows,
        columns=["Time", "Low", "High", "Open", "Close", "Volume"]
    )

    df["Datetime"] = pd.to_datetime(
        df["Time"],
        unit="s",
        utc=True
    )

    df = (
        df
        .drop_duplicates("Datetime")
        .sort_values("Datetime")
        .set_index("Datetime")
    )

    return df[
        ["Open", "High", "Low", "Close", "Volume"]
    ]


print(
    "--- BOT 42 DIST175 LONGER-HISTORY "
    "WALK-FORWARD STRESS TEST ---"
)

print("Loading 35-day BTC history...")

data = coinbase_history(35)

print("BTC 1-minute rows:", len(data))


# ============================================================
# BUILD 15-MINUTE CONTRACT FEATURES
# ============================================================

df = data.copy()

df["contract_bucket"] = df.index.floor("15min")

df["contract_start_price"] = (
    df
    .groupby("contract_bucket")["Open"]
    .transform("first")
)

df["contract_final_close"] = (
    df
    .groupby("contract_bucket")["Close"]
    .transform("last")
)

df["elapsed_minute"] = (
    (
        df.index.to_series(index=df.index)
        - df["contract_bucket"]
    ).dt.total_seconds()
    / 60.0
)

df["remaining_minutes"] = (
    15.0 - df["elapsed_minute"]
)

df["move_from_start_pct"] = (
    df["Close"]
    / df["contract_start_price"]
    - 1.0
)

df["distance_abs"] = (
    df["move_from_start_pct"].abs()
)

df["return_1m"] = (
    df["Close"].pct_change(1)
)

df["return_3m"] = (
    df["Close"].pct_change(3)
)

df["return_5m"] = (
    df["Close"].pct_change(5)
)

df["momentum_1m"] = (
    df["return_1m"]
    - df["return_1m"].shift(1)
)

df["volatility_5m"] = (
    df["return_1m"]
    .rolling(5)
    .std()
)

df["sma_5"] = (
    df["Close"]
    .rolling(5)
    .mean()
)

df["sma_distance_5"] = (
    df["Close"]
    / df["sma_5"]
    - 1.0
)

df["contract_outcome"] = (
    df["contract_final_close"]
    > df["contract_start_price"]
)


feature_cols = [
    "elapsed_minute",
    "remaining_minutes",
    "move_from_start_pct",
    "return_1m",
    "return_3m",
    "return_5m",
    "momentum_1m",
    "volatility_5m",
    "sma_distance_5",
]


current_contract = (
    df.index[-1].floor("15min")
)

hist = df[
    df["contract_bucket"] < current_contract
].dropna(
    subset=feature_cols + ["contract_outcome"]
).copy()


contracts = (
    hist["contract_bucket"]
    .drop_duplicates()
    .sort_values()
    .reset_index(drop=True)
)

print(
    "Completed contracts:",
    len(contracts)
)


# ============================================================
# WALK-FORWARD TEST BLOCKS
# ============================================================

fold_specs = [
    (0.20, 0.30),
    (0.30, 0.40),
    (0.40, 0.50),
    (0.50, 0.60),
    (0.60, 0.70),
    (0.70, 0.80),
    (0.80, 0.90),
    (0.90, 1.00),
]


records = []


for train_frac, test_frac in fold_specs:

    train_end = max(
        1,
        int(len(contracts) * train_frac)
    )

    test_end = max(
        train_end + 1,
        int(len(contracts) * test_frac)
    )

    train_contracts = set(
        contracts.iloc[:train_end]
    )

    test_contracts = set(
        contracts.iloc[
            train_end:test_end
        ]
    )

    train = hist[
        hist["contract_bucket"].isin(
            train_contracts
        )
    ].copy()

    test = hist[
        hist["contract_bucket"].isin(
            test_contracts
        )
    ].copy()

    if train.empty or test.empty:
        continue


    model = RandomForestClassifier(
        n_estimators=1200,
        max_depth=8,
        random_state=42,
        class_weight="balanced",
        n_jobs=-1
    )

    model.fit(
        train[feature_cols],
        train["contract_outcome"]
    )


    test = test.sort_values(
        [
            "contract_bucket",
            "elapsed_minute"
        ]
    ).copy()


    test["pred"] = model.predict(
        test[feature_cols]
    )

    test["confidence"] = (
        model
        .predict_proba(
            test[feature_cols]
        )
        .max(axis=1)
    )

    test["correct"] = (
        test["pred"].to_numpy()
        ==
        test["contract_outcome"].to_numpy()
    )

    test["confidence_change_1m"] = (
        test
        .groupby("contract_bucket")[
            "confidence"
        ]
        .diff()
    )


    def agreement_hits(row):

        hits = 0

        for col in [
            "return_1m",
            "return_3m",
            "return_5m"
        ]:

            v = row[col]

            if pd.isna(v):
                continue

            if bool(row["pred"]) and v > 0:
                hits += 1

            elif (
                (not bool(row["pred"]))
                and v < 0
            ):
                hits += 1

        return hits


    test["agreement_hits"] = (
        test.apply(
            agreement_hits,
            axis=1
        )
    )


    candidates = test[
        (test["elapsed_minute"] >= 8)
        & (test["elapsed_minute"] < 10)
        & (test["confidence"] >= 0.95)
        & (test["agreement_hits"] >= 3)
        & (
            test["confidence_change_1m"]
            >= 0
        )
        & (
            test["distance_abs"]
            >= 0.00175
        )
    ].copy()


    first = (
        candidates
        .sort_values(
            [
                "contract_bucket",
                "elapsed_minute"
            ]
        )
        .groupby(
            "contract_bucket",
            as_index=False
        )
        .first()
    )


    for _, r in first.iterrows():

        records.append({
            "fold":
                f"{int(train_frac*100)}"
                f"->{int(test_frac*100)}",

            "contract":
                r["contract_bucket"],

            "minute":
                int(r["elapsed_minute"]),

            "pred":
                "UP"
                if bool(r["pred"])
                else "DOWN",

            "correct":
                bool(r["correct"]),

            "confidence":
                float(r["confidence"]),

            "distance":
                float(r["distance_abs"]),

            "return_1m":
                float(r["return_1m"]),

            "return_3m":
                float(r["return_3m"]),

            "return_5m":
                float(r["return_5m"]),

            "conf_change":
                float(
                    r["confidence_change_1m"]
                ),
        })


res = pd.DataFrame(records)


print(
    "\n--- DIST175 LONG-HISTORY TOTALS ---"
)


if res.empty:

    print("No qualifying signals.")

else:

    total = len(res)

    wins = int(
        res["correct"].sum()
    )

    print(
        f"TOTAL | {wins}/{total}"
        f" = {wins/total:.3f}"
    )

    print(
        "Mean minute:",
        f"{res['minute'].mean():.2f}"
    )

    print(
        "Mean confidence:",
        f"{res['confidence'].mean():.3f}"
    )

    print(
        "Mean |distance|:",
        f"{res['distance'].mean():.3%}"
    )


    print(
        "\n--- DIRECTION QUALITY ---"
    )

    for direction in ["UP", "DOWN"]:

        q = res[
            res["pred"] == direction
        ]

        if q.empty:

            print(
                f"{direction} | 0 signals"
            )

        else:

            w = int(
                q["correct"].sum()
            )

            print(
                f"{direction} | "
                f"{w}/{len(q)}"
                f" = {w/len(q):.3f}"
            )


    print(
        "\n--- MINUTE QUALITY ---"
    )

    for minute in [8, 9]:

        q = res[
            res["minute"] == minute
        ]

        if q.empty:

            print(
                f"M{minute} | 0 signals"
            )

        else:

            w = int(
                q["correct"].sum()
            )

            print(
                f"M{minute} | "
                f"{w}/{len(q)}"
                f" = {w/len(q):.3f}"
                f" | UP "
                f"{int((q['pred']=='UP').sum())}"
                f" | DOWN "
                f"{int((q['pred']=='DOWN').sum())}"
            )


    print(
        "\n--- FOLD CONSISTENCY ---"
    )

    for fold in res["fold"].unique():

        q = res[
            res["fold"] == fold
        ]

        w = int(
            q["correct"].sum()
        )

        print(
            f"{fold} | "
            f"{w}/{len(q)}"
            f" = {w/len(q):.3f}"
            f" | UP "
            f"{int((q['pred']=='UP').sum())}"
            f" | DOWN "
            f"{int((q['pred']=='DOWN').sum())}"
        )


    print(
        "\n--- DISTANCE BAND QUALITY ---"
    )

    bands = [
        (
            "0.175-0.200%",
            0.00175,
            0.00200
        ),
        (
            "0.200-0.250%",
            0.00200,
            0.00250
        ),
        (
            "0.250-0.300%",
            0.00250,
            0.00300
        ),
        (
            ">=0.300%",
            0.00300,
            999.0
        ),
    ]


    for label, low, high in bands:

        q = res[
            (res["distance"] >= low)
            & (res["distance"] < high)
        ]

        if q.empty:

            print(
                f"{label} | 0 signals"
            )

        else:

            w = int(
                q["correct"].sum()
            )

            print(
                f"{label} | "
                f"{w}/{len(q)}"
                f" = {w/len(q):.3f}"
            )


    print(
        "\n--- FAILURE DETAILS ---"
    )

    failures = res[
        ~res["correct"]
    ]


    if failures.empty:

        print("No failures.")

    else:

        for _, r in failures.iterrows():

            print(
                f"contract={r['contract']}"
                f" | fold={r['fold']}"
                f" | M{r['minute']}"
                f" | pred={r['pred']}"
                f" | conf={r['confidence']:.3f}"
                f" | |dist|={r['distance']:.3%}"
                f" | r1={r['return_1m']:+.3%}"
                f" | r3={r['return_3m']:+.3%}"
                f" | r5={r['return_5m']:+.3%}"
                f" | confΔ={r['conf_change']:+.4f}"
            )


print(
    "\n--- BOT 42 COMPLETE ---"
)

print(
    "DIST175 longer-history "
    "walk-forward stress test complete."
)

print(
    "Diagnostic only. "
    "No live rules were changed."
)
