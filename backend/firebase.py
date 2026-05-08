"""
NuroTrack — Firebase Service
Handles Firebase Admin SDK initialization and Firestore sync.
Non-fatal: app runs fine without a valid serviceAccountKey.json.
"""

import firebase_admin
from firebase_admin import credentials, firestore

from config import FIREBASE_CRED_PATH, USER_ID
from database import get_conn


def init_firebase():
    """Initialize Firebase Admin SDK. Returns Firestore client or None."""
    try:
        cred = credentials.Certificate(str(FIREBASE_CRED_PATH))
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("[Firebase] Connected.")
        return db
    except Exception as e:
        print(f"[Firebase] Not connected (non-fatal): {e}")
        return None


def sync_to_firebase(fb_db):
    """Push all unsynced local sessions to Firestore in batches of 400."""
    if not fb_db:
        return
    try:
        conn  = get_conn()
        rows  = conn.execute(
            "SELECT * FROM sessions WHERE synced=0 AND user_id=?", (USER_ID,)
        ).fetchall()
        if not rows:
            return

        cols  = ["id", "user_id", "app", "window_title", "start_time",
                 "end_time", "duration_sec", "category", "synced"]
        batch = fb_db.batch()
        count = 0

        for row in rows:
            doc = dict(zip(cols, row))
            doc.pop("synced")
            ref = (fb_db.collection("users")
                        .document(USER_ID)
                        .collection("sessions")
                        .document(str(doc["id"])))
            batch.set(ref, doc)
            count += 1
            if count % 400 == 0:
                batch.commit()
                batch = fb_db.batch()

        batch.commit()
        conn.execute(
            "UPDATE sessions SET synced=1 WHERE synced=0 AND user_id=?", (USER_ID,)
        )
        conn.commit()
        print(f"[Firebase] Synced {count} sessions.")
    except Exception as e:
        print(f"[Firebase] Sync failed (non-fatal): {e}")
