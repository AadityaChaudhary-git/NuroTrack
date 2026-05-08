"""
NuroTrack — Central Configuration
All constants and paths live here. Import from anywhere.
"""

from pathlib import Path

# ── Paths ──────────────────────────────────────────────────
BASE_DIR           = Path(__file__).resolve().parent.parent
FIREBASE_CRED_PATH = BASE_DIR / "firebase" / "serviceAccountKey.json"
DB_PATH            = str(BASE_DIR / "data" / "nurotrack.db")
MODEL_PATH         = str(Path(__file__).parent / "ml_model.pkl")

# ── Runtime ────────────────────────────────────────────────
POLL_INTERVAL  = 5      # seconds between window polls
SYNC_INTERVAL  = 300    # seconds between Firebase syncs
USER_ID        = "demo_user"

# ── App Categories ─────────────────────────────────────────
PRODUCTIVE_APPS = [
    "code", "visual studio", "studio code", "vim", "nvim", "terminal",
    "powershell", "cmd", "bash", "python", "jupyter", "postman",
    "notion", "slack", "figma", "obsidian", "word", "excel",
    "sheets", "intellij", "pycharm", "webstorm", "eclipse", "android studio",
    "github", "gitlab", "stackoverflow", "docs.google", "linear", "jira",
    "github.com", "stackoverflow.com", "localhost", "127.0.0.1",
    "claude.ai", "chatgpt", "figma.com", "notion.so", "colab",
    "kaggle", "leetcode", "hackerrank", "google docs", "google sheets",
    "replit", "codepen", "vercel", "netlify", "render", "heroku",
]

UNPRODUCTIVE_APPS = [
    "youtube", "twitter", "instagram", "reddit", "netflix", "tiktok",
    "facebook", "twitch", "discord", "whatsapp", "telegram", "snapchat",
    "prime video", "hotstar", "spotify", "x.com", "reel", "shorts",
]
