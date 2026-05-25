"""Configuration: secrets from .env, everything else from config.yaml."""

import os
import shutil
import threading
from functools import cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

load_dotenv()

_CONFIG_DIR = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _CONFIG_DIR / "config.yaml"
_CONFIG_EXAMPLE = _CONFIG_DIR / "config.example.yaml"


def _ensure_config() -> None:
    """Copy config.example.yaml → config.yaml if the latter doesn't exist."""
    if not _CONFIG_PATH.exists() and _CONFIG_EXAMPLE.exists():
        shutil.copy2(_CONFIG_EXAMPLE, _CONFIG_PATH)


class ConfigStore:
    """Thread-safe YAML-backed config with env-var fallbacks."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._data: dict[str, Any] = {}

    # -- load / save -------------------------------------------------------

    def load(self) -> None:
        if self._path.exists():
            with self._lock:
                self._data = yaml.safe_load(self._path.read_text(encoding="utf-8")) or {}

    def save(self) -> None:
        with self._lock:
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(yaml.dump(self._data, allow_unicode=True, sort_keys=False), encoding="utf-8")
            tmp.replace(self._path)

    # -- paths -------------------------------------------------------------

    @property
    def output_dir(self) -> Path:
        return Path(self._data.get("output_dir", "./output")).resolve()

    @output_dir.setter
    def output_dir(self, value: str) -> None:
        self._data["output_dir"] = value
        self.save()

    # -- channel_ids -------------------------------------------------------

    @property
    def channel_ids(self) -> list[str]:
        return [str(c) for c in self._data.get("channel_ids", [])]

    @channel_ids.setter
    def channel_ids(self, ids: list[str]) -> None:
        self._data["channel_ids"] = ids
        self.save()

    def add_channel(self, channel_id: str) -> bool:
        ids = self.channel_ids
        if channel_id in ids:
            return False
        self.channel_ids = [*ids, channel_id]
        return True

    def remove_channel(self, channel_id: str) -> bool:
        ids = self.channel_ids
        if channel_id not in ids:
            return False
        self.channel_ids = [c for c in ids if c != channel_id]
        return True

    # -- git ---------------------------------------------------------------

    @property
    def git_remote_url(self) -> str:
        return self._data.get("git", {}).get("remote_url", "")

    @git_remote_url.setter
    def git_remote_url(self, value: str) -> None:
        self._data.setdefault("git", {})["remote_url"] = value
        self.save()

    @property
    def git_user_name(self) -> str:
        return self._data.get("git", {}).get("user_name", "Arborist Bot")

    @property
    def git_user_email(self) -> str:
        return self._data.get("git", {}).get("user_email", "arborist@example.com")

    @property
    def git_branch(self) -> str:
        return self._data.get("git", {}).get("branch", "gh-pages")


# -- singleton -----------------------------------------------------------

_ensure_config()
_store = ConfigStore(_CONFIG_PATH)
_store.load()


def get_config() -> ConfigStore:
    return _store


# -- env-only (never in YAML) ---------------------------------------------

@cache
def get_discord_token() -> str:
    value = os.getenv("DISCORD_TOKEN", "").strip()
    if not value:
        raise ValueError("Missing required env var: DISCORD_TOKEN")
    return value


@cache
def get_site_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "site"
