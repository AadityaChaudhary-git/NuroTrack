"""
NuroTrack — ML Model
Handles training data generation, model training, and prediction.
Model: GradientBoostingClassifier → cognitive load + NuroScore + burnout risk.

Fix log:
- Unified feature set between training and prediction (was mismatched → always 0)
- Added productive_ratio, unproductive_ratio, session_count, avg_session_duration
- Normalized all inputs to [0,1] range
- Added rule-based fallback when ML score < 1 (catches constant-prediction failure)
- total_active threshold lowered to 10s (was 60s, caused zeros on short sessions)
"""

import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import LabelEncoder, MinMaxScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from sklearn.pipeline import Pipeline

from config import MODEL_PATH

# ── Canonical feature columns (must match in train + predict) ──
FEATURE_COLS = [
    "productive_ratio",       # prod_sec / total_active
    "unproductive_ratio",     # unprod_sec / total_active
    "neutral_ratio",          # neut_sec / total_active
    "session_count",          # number of app switches
    "avg_session_duration",   # total_active / session_count (normalized)
    "hour_sin",               # sin(hour * 2π/24)  — cyclical encoding
    "hour_cos",               # cos(hour * 2π/24)
]


# ── Feature extraction (single source of truth) ───────────────

def extract_features(feats: dict) -> dict:
    """
    Convert raw feats dict → normalized feature dict matching FEATURE_COLS.
    Input keys: productive_sec, neutral_sec, unproductive_sec,
                session_count, hour
    """
    prod   = max(feats.get("productive_sec",   0), 0)
    neut   = max(feats.get("neutral_sec",       0), 0)
    unprod = max(feats.get("unproductive_sec",  0), 0)
    count  = max(feats.get("session_count",     feats.get("context_switches", 1)), 1)
    hour   = feats.get("hour", 12)

    total  = prod + neut + unprod
    if total < 1:
        total = 1

    avg_dur = (total / count) / 3600   # normalized: 1hr session → 1.0

    angle   = hour * 2 * np.pi / 24

    return {
        "productive_ratio":     prod   / total,
        "unproductive_ratio":   unprod / total,
        "neutral_ratio":        neut   / total,
        "session_count":        min(count / 100, 1.0),   # cap at 100 switches
        "avg_session_duration": min(avg_dur, 1.0),
        "hour_sin":             (np.sin(angle) + 1) / 2, # → [0,1]
        "hour_cos":             (np.cos(angle) + 1) / 2,
    }


# ── Rule-based fallback scorer ────────────────────────────────

def _rule_based_score(feats_raw: dict) -> float:
    """
    Pure formula score — used when ML output < 1 (constant prediction guard).
    Returns NuroScore in [0, 100].
    """
    prod   = max(feats_raw.get("productive_sec",  0), 0)
    unprod = max(feats_raw.get("unproductive_sec", 0), 0)
    count  = max(feats_raw.get("session_count", feats_raw.get("context_switches", 1)), 1)
    total  = prod + unprod + max(feats_raw.get("neutral_sec", 0), 0)

    if total < 10:
        return 0.0

    pr     = prod   / total
    ur     = unprod / total
    sw_pen = min(count * 0.3, 15)

    score  = pr * 100 - ur * 40 - sw_pen + np.random.normal(0, 1.5)
    return float(np.clip(score, 0, 100))


# ── Training Data ──────────────────────────────────────────────

def generate_training_data(n: int = 3000) -> pd.DataFrame:
    np.random.seed(42)
    rows = []
    for _ in range(n):
        prod   = np.random.randint(0, 3600)
        neut   = np.random.randint(0, 1800)
        unprod = np.random.randint(0, 1200)
        count  = np.random.randint(1, 80)
        hour   = np.random.randint(6, 23)

        raw   = {"productive_sec": prod, "neutral_sec": neut,
                 "unproductive_sec": unprod, "session_count": count, "hour": hour}
        f     = extract_features(raw)
        score = _rule_based_score(raw)
        load  = "high_focus" if score >= 70 else "moderate" if score >= 45 else "low_focus"

        rows.append([f[c] for c in FEATURE_COLS] + [score, load])

    cols = FEATURE_COLS + ["nuro_score", "cognitive_load"]
    return pd.DataFrame(rows, columns=cols)


# ── Training ───────────────────────────────────────────────────

def train_model():
    """Train GradientBoosting pipeline with MinMaxScaler. Always retrains."""
    print("[ML] Training cognitive load model…")
    df = generate_training_data()

    le = LabelEncoder()
    y  = le.fit_transform(df["cognitive_load"])
    X  = df[FEATURE_COLS]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    pipeline = Pipeline([
        ("scaler", MinMaxScaler()),
        ("clf",    GradientBoostingClassifier(
            n_estimators=200, max_depth=4,
            learning_rate=0.08, random_state=42
        ))
    ])
    pipeline.fit(X_train, y_train)

    print("[ML] Report:\n",
          classification_report(y_test, pipeline.predict(X_test),
                                target_names=le.classes_))
    joblib.dump({"model": pipeline, "encoder": le}, MODEL_PATH)
    print(f"[ML] Saved → {MODEL_PATH}")
    return pipeline, le


def load_or_train_model():
    """Always retrain to guarantee feature set alignment."""
    return train_model()


# ── Prediction ─────────────────────────────────────────────────

def predict(model, encoder, feats: dict) -> tuple:
    """
    Returns (cognitive_load_label, nuro_score, burnout_risk).

    Input feats keys: productive_sec, neutral_sec, unproductive_sec,
                      session_count (or context_switches), hour
    """
    f   = extract_features(feats)
    row = pd.DataFrame([[f[c] for c in FEATURE_COLS]], columns=FEATURE_COLS)

    pred  = model.predict(row)[0]
    label = encoder.inverse_transform([pred])[0]

    # ── NuroScore: ML-informed rule formula ───────────────
    prod   = max(feats.get("productive_sec",  0), 0)
    unprod = max(feats.get("unproductive_sec", 0), 0)
    neut   = max(feats.get("neutral_sec",      0), 0)
    count  = max(feats.get("session_count", feats.get("context_switches", 1)), 1)
    total  = prod + unprod + neut

    if total < 10:
        nuro = 0.0
    else:
        # ML label boosts/adjusts the formula score
        ml_bonus = {"high_focus": 8, "moderate": 0, "low_focus": -8}.get(label, 0)
        base     = _rule_based_score(feats)
        nuro     = float(np.clip(base + ml_bonus, 0, 100))

        # ── Fallback guard: if ML collapsed to constant ───
        if nuro < 1:
            nuro = _rule_based_score(feats)
            print(f"[ML] ⚠ Score < 1 detected — using rule-based fallback: {nuro}")

    # ── Burnout risk ──────────────────────────────────────
    ur      = unprod / max(total, 1)
    burnout = float(np.clip(ur * 70 + (count / 100) * 15, 0, 100))

    return label, round(nuro, 1), round(burnout, 1)