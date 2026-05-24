import os
from functools import cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _require(key: str) -> str:
    value = os.getenv(key, "").strip()
    if not value:
        raise ValueError(f"Missing required env var: {key}")
    return value


@cache
def get_discord_token() -> str:
    return _require("DISCORD_TOKEN")


@cache
def get_channel_ids() -> list[str]:
    return [cid.strip() for cid in _require("CHANNEL_IDS").split(",") if cid.strip()]


@cache
def get_output_dir() -> Path:
    return Path(os.getenv("OUTPUT_DIR", "./output")).resolve()


@cache
def get_git_remote_url() -> str:
    return _require("GIT_REMOTE_URL")


@cache
def get_git_user_name() -> str:
    return os.getenv("GIT_USER_NAME", "Arborist Bot")


@cache
def get_git_user_email() -> str:
    return os.getenv("GIT_USER_EMAIL", "arborist@example.com")


@cache
def get_git_branch() -> str:
    return os.getenv("GIT_BRANCH", "gh-pages")


@cache
def get_site_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "site"
