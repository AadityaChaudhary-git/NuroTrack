"""
NuroTrack — Entry Point
Run with: python main.py

Startup sequence:
  1. Init SQLite DB
  2. Train ML model
  3. Connect Firebase (non-fatal)
  4. Backfill hourly stats for today
  5. Start background scheduler
  6. Start Flask API (background thread)
  7. Start window tracker (blocking main thread)
"""

from database import init_db
from ml import load_or_train_model
from firebase import init_firebase, sync_to_firebase
from stats import backfill_hourly, generate_daily_report
from api import start_api, start_scheduler
from tracker import WindowTracker
from database import get_conn


if __name__ == "__main__":
    print("=" * 52)
    print("  NuroTrack — Backend System Starting")
    print("=" * 52)

    init_db()
    model, encoder = load_or_train_model()
    fb_db          = init_firebase()

    print("[Startup] Backfilling hourly stats…")
    backfill_hourly(model, encoder)

    start_scheduler(model, encoder, fb_db)
    start_api(model, encoder)

    tracker = WindowTracker()
    try:
        tracker.run()
    except KeyboardInterrupt:
        tracker.stop()
        sync_to_firebase(fb_db)
        generate_daily_report(model, encoder)
        get_conn().close()
        print("\n[NuroTrack] Gracefully shut down.")
