"""
NuroTrack — Window Tracker
Polls the active window, categorizes it, and persists sessions to SQLite.
"""

import time
from datetime import datetime

from config import POLL_INTERVAL, USER_ID, PRODUCTIVE_APPS, UNPRODUCTIVE_APPS
from database import get_conn


# ── Helpers ────────────────────────────────────────────────

def get_active_window() -> str:
    import platform
    try:
        if platform.system() == "Windows":
            import pygetwindow as gw
            win = gw.getActiveWindow()
            return (win.title or "Unknown") if win else "Unknown"
        elif platform.system() == "Darwin":
            import subprocess
            return subprocess.check_output(
                ["osascript", "-e",
                 'tell application "System Events" to get name of first process whose frontmost is true']
            ).decode().strip()
        else:
            import subprocess
            return subprocess.check_output(
                ["xdotool", "getactivewindow", "getwindowname"]
            ).decode().strip()
    except Exception:
        return "Unknown"


def categorize(window_title: str) -> str:
    t = window_title.lower()
    if any(k in t for k in PRODUCTIVE_APPS):   return "productive"
    if any(k in t for k in UNPRODUCTIVE_APPS): return "unproductive"
    return "neutral"


def extract_app_name(window_title: str) -> str:
    for sep in [" — ", " | ", " - "]:
        parts = window_title.split(sep)
        if len(parts) > 1:
            candidate = parts[-1].strip()
            if 2 < len(candidate) < 40:
                return candidate
    return window_title.strip()[:35] or "Unknown"


# ── Tracker Class ──────────────────────────────────────────

class WindowTracker:
    def __init__(self):
        self.last_win = None
        self.start_t  = time.time()
        self.running  = False

    def record_session(self, window: str, duration: int):
        if duration < 1:
            return
        conn = get_conn()
        app  = extract_app_name(window)
        cat  = categorize(window)
        now  = datetime.now().isoformat()
        conn.execute(
            "INSERT INTO sessions "
            "(user_id, app, window_title, start_time, end_time, duration_sec, category)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (USER_ID, app, window,
             datetime.fromtimestamp(self.start_t).isoformat(),
             now, duration, cat)
        )
        conn.commit()
        print(f"[Tracker] {app} ({cat}) — {duration}s")

    def tick(self):
        current = get_active_window()
        now     = time.time()
        if self.last_win is None:
            self.last_win = current
            self.start_t  = now
            return
        if current != self.last_win:
            self.record_session(self.last_win, int(now - self.start_t))
            self.last_win = current
            self.start_t  = now

    def run(self):
        self.running = True
        print(f"[Tracker] Started — polling every {POLL_INTERVAL}s")
        while self.running:
            try:
                self.tick()
            except Exception as e:
                print(f"[Tracker] tick error: {e}")
            time.sleep(POLL_INTERVAL)

    def stop(self):
        self.running = False
