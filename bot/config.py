import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def _require(key: str) -> str:
    value = os.getenv(key, "").strip()
    if not value:
        raise ValueError(f"Missing required env var: {key}")
    return value


DISCORD_TOKEN = _require("DISCORD_TOKEN")
CHANNEL_IDS = [cid.strip() for cid in _require("CHANNEL_IDS").split(",") if cid.strip()]
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "./output")).resolve()
GIT_REMOTE_URL = _require("GIT_REMOTE_URL")
GIT_USER_NAME = os.getenv("GIT_USER_NAME", "Arborist Bot")
GIT_USER_EMAIL = os.getenv("GIT_USER_EMAIL", "arborist@example.com")
GIT_BRANCH = os.getenv("GIT_BRANCH", "gh-pages")

SITE_DIR = Path(__file__).resolve().parent.parent / "site"
