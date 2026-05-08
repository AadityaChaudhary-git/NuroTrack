"""
NuroTrack — Flask API + Scheduler
All HTTP routes and the background scheduler live here.
Start with: start_api(model, encoder) and start_scheduler(model, encoder, fb_db)
"""

import sys
import os
import threading
import schedule
import time
from datetime import datetime

# Ensure backend/ dir is always on the path (fixes threaded import issues)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import USER_ID, SYNC_INTERVAL
from database import get_conn
from stats import aggregate_hourly, generate_daily_report
from firebase import sync_to_firebase

# Shared mutable goal state (same as original)
_daily_goal = {"goal_min": 240}


# ── Scheduler ──────────────────────────────────────────────

def start_scheduler(model, encoder, fb_db):
    def safe_agg():
        try:   aggregate_hourly(model, encoder)
        except Exception as e: print(f"[Scheduler] aggregate error: {e}")

    def safe_rep():
        try:   generate_daily_report(model, encoder)
        except Exception as e: print(f"[Scheduler] report error: {e}")

    def safe_sync():
        try:   sync_to_firebase(fb_db)
        except Exception as e: print(f"[Scheduler] sync error: {e}")

    schedule.every(1).hours.do(safe_agg)
    schedule.every().day.at("23:55").do(safe_rep)
    schedule.every(SYNC_INTERVAL).seconds.do(safe_sync)

    def run():
        while True:
            try:   schedule.run_pending()
            except Exception as e: print(f"[Scheduler] error: {e}")
            time.sleep(20)

    threading.Thread(target=run, daemon=True).start()
    print("[Scheduler] Active.")


# ── Flask API ──────────────────────────────────────────────

def start_api(model, encoder):
    try:
        from flask import Flask, jsonify, request as freq
        from flask_cors import CORS
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from auth import register_auth_routes, require_auth

        app = Flask(__name__)
        CORS(app)
        register_auth_routes(app)

        @app.route("/api/health")
        def health():
            return jsonify({"status": "ok", "time": datetime.now().isoformat()})

        @app.route("/api/today")
        @require_auth
        def today():
            return jsonify(generate_daily_report(model, encoder))

        @app.route("/api/sessions")
        @require_auth
        def sessions():
            conn = get_conn()
            date = datetime.now().strftime("%Y-%m-%d")
            rows = conn.execute("""
                SELECT app, window_title, start_time, duration_sec, category
                FROM sessions WHERE user_id=? AND date(start_time)=?
                ORDER BY start_time DESC LIMIT 50
            """, (USER_ID, date)).fetchall()
            cols = ["app", "window_title", "start_time", "duration_sec", "category"]
            return jsonify([dict(zip(cols, r)) for r in rows])

        @app.route("/api/weekly")
        @require_auth
        def weekly():
            conn = get_conn()
            rows = conn.execute("""
                SELECT date, active_sec, productive_sec, neutral_sec,
                       unproductive_sec, top_app, nuro_score,
                       cognitive_state, burnout_risk, apps_count
                FROM daily_reports ORDER BY date DESC LIMIT 7
            """).fetchall()
            cols = ["date", "active_sec", "productive_sec", "neutral_sec",
                    "unproductive_sec", "top_app", "nuro_score",
                    "cognitive_state", "burnout_risk", "apps_count"]
            return jsonify([dict(zip(cols, r)) for r in rows])

        @app.route("/api/hourly")
        @require_auth
        def hourly():
            conn = get_conn()
            date = datetime.now().strftime("%Y-%m-%d")
            rows = conn.execute("""
                SELECT start_time, duration_sec, category FROM sessions
                WHERE user_id=? AND date(start_time)=?
                ORDER BY start_time
            """, (USER_ID, date)).fetchall()

            buckets = {}
            for start_time_str, duration_sec, category in rows:
                try:   dt = datetime.fromisoformat(start_time_str)
                except: continue
                bmin = (dt.minute // 10) * 10
                key  = dt.strftime(f"%H:{bmin:02d}")
                if key not in buckets:
                    buckets[key] = {"productive": 0, "neutral": 0, "unproductive": 0, "total": 0}
                buckets[key]["total"] += duration_sec
                if category in buckets[key]:
                    buckets[key][category] += duration_sec

            result = []
            for key in sorted(buckets.keys()):
                b     = buckets[key]
                total = b["total"] or 1
                score = round((b["productive"] / total) * 100, 1)
                result.append({
                    "time":             key,
                    "hour":             int(key.split(":")[0]),
                    "nuro_score":       score,
                    "productive_sec":   b["productive"],
                    "neutral_sec":      b["neutral"],
                    "unproductive_sec": b["unproductive"],
                })
            return jsonify(result)

        @app.route("/api/aggregate")
        @require_auth
        def aggregate():
            try:
                nuro = aggregate_hourly(model, encoder)
                return jsonify({"status": "ok", "nuro_score": nuro})
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 500

        @app.route("/api/goal", methods=["GET"])
        @require_auth
        def get_goal():
            conn = get_conn()
            date = datetime.now().strftime("%Y-%m-%d")
            row  = conn.execute("""
                SELECT SUM(duration_sec) FROM sessions
                WHERE user_id=? AND date(start_time)=? AND category='productive'
            """, (USER_ID, date)).fetchone()
            productive_sec = row[0] or 0
            return jsonify({
                "goal_min":     _daily_goal["goal_min"],
                "progress_min": round(productive_sec / 60, 1),
            })

        @app.route("/api/goal", methods=["POST"])
        @require_auth
        def set_goal():
            data = freq.get_json(silent=True) or {}
            try:
                goal = int(data.get("goal_min", 240))
                if goal < 1 or goal > 1440:
                    return jsonify({"error": "goal_min must be 1–1440"}), 400
                _daily_goal["goal_min"] = goal
                return jsonify({"goal_min": goal, "status": "updated"})
            except (ValueError, TypeError):
                return jsonify({"error": "goal_min must be an integer"}), 400

        def _run():
            try:
                app.run(port=5050, debug=False, use_reloader=False)
            except Exception as e:
                print(f"[API] ❌ Flask crashed: {e}")

        threading.Thread(target=_run, daemon=True).start()
        print("[API] Running on http://localhost:5050")

    except ImportError as e:
        print(f"[API] ❌ Import error — {e}")
    except Exception as e:
        print(f"[API] ❌ Unexpected error — {e}")