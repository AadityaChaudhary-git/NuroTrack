"""
NuroTrack — Stats Aggregator
Computes hourly stats, daily reports, and backfills missing hours.
"""

from datetime import datetime

from config import USER_ID
from database import get_conn
from ml import predict


# ── Hourly Aggregation ─────────────────────────────────────

def aggregate_hourly(model, encoder, target_hour: int = None) -> float:
    conn = get_conn()
    now  = datetime.now()
    date = now.strftime("%Y-%m-%d")
    hour = target_hour if target_hour is not None else now.hour

    rows = conn.execute("""
        SELECT category, SUM(duration_sec) FROM sessions
        WHERE user_id=? AND date(start_time)=?
          AND CAST(strftime('%H', start_time) AS INTEGER)=?
        GROUP BY category
    """, (USER_ID, date, hour)).fetchall()

    stats = {"productive": 0, "neutral": 0, "unproductive": 0}
    for cat, sec in rows:
        if cat in stats:
            stats[cat] = sec

    session_count = conn.execute("""
        SELECT COUNT(*) FROM sessions
        WHERE user_id=? AND date(start_time)=?
          AND CAST(strftime('%H', start_time) AS INTEGER)=?
    """, (USER_ID, date, hour)).fetchone()[0]

    feats = {
        "productive_sec":   stats["productive"],
        "neutral_sec":      stats["neutral"],
        "unproductive_sec": stats["unproductive"],
        "session_count":    session_count,
        "hour":             hour,
    }

    load, nuro, _ = predict(model, encoder, feats)

    conn.execute("""
        INSERT INTO hourly_stats
          (date, hour, productive_sec, neutral_sec, unproductive_sec, nuro_score, cognitive_load)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(date, hour) DO UPDATE SET
          productive_sec=excluded.productive_sec,
          neutral_sec=excluded.neutral_sec,
          unproductive_sec=excluded.unproductive_sec,
          nuro_score=excluded.nuro_score,
          cognitive_load=excluded.cognitive_load
    """, (date, hour, stats["productive"], stats["neutral"],
          stats["unproductive"], nuro, load))
    conn.commit()

    print(f"[Stats] Hour {hour:02d}: NuroScore={nuro} | Load={load}")
    return nuro


def backfill_hourly(model, encoder):
    """Aggregate all hours from midnight up to the current hour."""
    cur_hour = datetime.now().hour
    for h in range(cur_hour + 1):
        try:
            aggregate_hourly(model, encoder, target_hour=h)
        except Exception as e:
            print(f"[Backfill] Hour {h} failed: {e}")


# ── Daily Report ───────────────────────────────────────────

def generate_daily_report(model, encoder, date: str = None) -> dict:
    conn = get_conn()
    date = date or datetime.now().strftime("%Y-%m-%d")

    rows = conn.execute("""
        SELECT category, SUM(duration_sec) FROM sessions
        WHERE user_id=? AND date(start_time)=?
        GROUP BY category
    """, (USER_ID, date)).fetchall()

    top_app_row = conn.execute("""
        SELECT app, SUM(duration_sec) as t FROM sessions
        WHERE user_id=? AND date(start_time)=?
        GROUP BY app ORDER BY t DESC LIMIT 1
    """, (USER_ID, date)).fetchone()

    apps_count = conn.execute("""
        SELECT COUNT(DISTINCT app) FROM sessions
        WHERE user_id=? AND date(start_time)=?
    """, (USER_ID, date)).fetchone()[0]

    switches = conn.execute("""
        SELECT COUNT(*) FROM sessions
        WHERE user_id=? AND date(start_time)=?
    """, (USER_ID, date)).fetchone()[0]

    stats = {"productive": 0, "neutral": 0, "unproductive": 0}
    for cat, sec in rows:
        if cat in stats:
            stats[cat] = sec

    total_active = stats["productive"] + stats["neutral"] + stats["unproductive"]

    # ✅ FIX 1 — Do NOT kill score for small sessions
    if total_active <= 0:
        return {
            "date":             date,
            "nuro_score":       0,
            "cognitive_state":  "no_data",
            "burnout_risk":     0,
            "active_sec":       total_active,
            "productive_sec":   stats["productive"],
            "neutral_sec":      stats["neutral"],
            "unproductive_sec": stats["unproductive"],
            "top_app":          top_app_row[0] if top_app_row else "N/A",
            "apps_count":       apps_count,
        }

    # ✅ FIX 2 — Correct feature names for ML
    feats = {
        "productive_sec":   stats["productive"],
        "neutral_sec":      stats["neutral"],
        "unproductive_sec": stats["unproductive"],
        "session_count":    switches,   # FIXED (was context_switches)
        "hour":             datetime.now().hour,
    }

    load, nuro, burnout = predict(model, encoder, feats)

    # ✅ FIX 3 — Fallback if ML gives bad score
    if nuro < 1:
        print("[Fix] Using fallback score")

        pr = stats["productive"] / total_active
        ur = stats["unproductive"] / total_active

        nuro = pr * 100 - ur * 50
        nuro = max(0, min(100, nuro))

    conn.execute("""
        INSERT INTO daily_reports
          (date, active_sec, productive_sec, neutral_sec, unproductive_sec,
           top_app, nuro_score, cognitive_state, burnout_risk, apps_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(date) DO UPDATE SET
          active_sec=excluded.active_sec,
          productive_sec=excluded.productive_sec,
          neutral_sec=excluded.neutral_sec,
          unproductive_sec=excluded.unproductive_sec,
          nuro_score=excluded.nuro_score,
          cognitive_state=excluded.cognitive_state,
          burnout_risk=excluded.burnout_risk,
          top_app=excluded.top_app,
          apps_count=excluded.apps_count
    """, (date, total_active, stats["productive"], stats["neutral"],
          stats["unproductive"], top_app_row[0] if top_app_row else "N/A",
          nuro, load, burnout, apps_count))
    conn.commit()

    print(f"[Report] {date}: NuroScore={nuro} | State={load} | Burnout={burnout}%")

    return {
        "date":             date,
        "nuro_score":       nuro,
        "cognitive_state":  load,
        "burnout_risk":     burnout,
        "active_sec":       total_active,
        "productive_sec":   stats["productive"],
        "neutral_sec":      stats["neutral"],
        "unproductive_sec": stats["unproductive"],
        "top_app":          top_app_row[0] if top_app_row else "N/A",
        "apps_count":       apps_count,
    }