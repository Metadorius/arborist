"""Git operations: stage, commit (debounced), push."""

import asyncio
import logging
import time
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import git

logger = logging.getLogger("arborist.git")


def _redact_url(url: str | None) -> str:
    """Strip userinfo (user:password) from a URL for safe logging."""
    if not url:
        return "<unset>"
    try:
        parts = urlsplit(url)
    except ValueError:
        return "<unparseable>"
    if parts.username or parts.password:
        netloc = parts.hostname or ""
        if parts.port:
            netloc = f"{netloc}:{parts.port}"
        parts = parts._replace(netloc=netloc)
    return urlunsplit(parts)


def _ensure_origin(repo: git.Repo, url: str) -> None:
    """Create or update the 'origin' remote."""
    try:
        origin = repo.remotes.origin
        if list(origin.urls) != [url]:
            origin.set_url(url)
            logger.info("Updated origin remote to %s", _redact_url(url))
    except (AttributeError, ValueError):
        repo.create_remote("origin", url)
        logger.info("Created origin remote: %s", _redact_url(url))


def _checkout_or_create(repo: git.Repo, branch: str) -> None:
    """Checkout `branch`, creating it from HEAD if it doesn't exist."""
    if branch in repo.heads:
        repo.heads[branch].checkout()
    else:
        repo.git.checkout("-b", branch)
        logger.info("Created branch: %s", branch)


class GitManager:
    """Manages a git repo for the output directory with debounced commits."""

    def __init__(self, repo_dir: Path, debounce_seconds: int = 300) -> None:
        self._repo_dir = repo_dir
        self._debounce = debounce_seconds
        self._last_commit = time.time()  # prevent immediate flush on first call
        self._pending = False
        self._repo: git.Repo | None = None
        self._has_unpushed = False

    def ensure_repo(self) -> git.Repo:
        """Open or init a git repo in the output directory."""
        if self._repo is not None:
            return self._repo

        git_dir = self._repo_dir / ".git"

        if git_dir.exists():
            logger.info("Opening existing repo at %s", self._repo_dir)
            self._repo = git.Repo(self._repo_dir)
        else:
            logger.info("Initializing repo at %s", self._repo_dir)
            self._repo_dir.mkdir(parents=True, exist_ok=True)
            self._repo = git.Repo.init(self._repo_dir, initial_branch="main")

            # Create initial empty commit so HEAD resolves
            self._repo.index.commit("Initialize repository")

            # Rename branch if target differs from "main"
            from .config import get_config
            target_branch = get_config().git_branch
            if target_branch != "main":
                try:
                    self._repo.git.branch("-m", "main", target_branch)
                    logger.info("Renamed branch: main -> %s", target_branch)
                except git.GitCommandError as e:
                    logger.warning("Could not rename branch: %s", e)

        self._set_user_config()
        return self._repo

    def _set_user_config(self) -> None:
        from .config import get_config
        if self._repo is None:
            return
        cfg = get_config()
        with self._repo.config_writer() as cw:
            cw.set_value("user", "name", cfg.git_user_name)
            cw.set_value("user", "email", cfg.git_user_email)

    def mark_changed(self) -> None:
        """Signal that content has changed. Triggers a debounced commit."""
        self._pending = True
        elapsed = time.time() - self._last_commit

        if elapsed >= self._debounce:
            self._flush()

    def _flush(self) -> None:
        """Commit pending changes and push."""
        if not self._pending:
            return

        from .config import get_config
        cfg = get_config()
        remote_url = cfg.git_remote_url or None
        push_branch = cfg.git_branch

        repo = self.ensure_repo()

        try:
            # Stage all changes (porcelain `git add -A`)
            repo.git.add(A=True)

            # Check if anything changed — skip if first commit (no HEAD)
            try:
                if not repo.index.diff("HEAD"):
                    logger.debug("Nothing to commit")
                    self._pending = False
                    return
            except (ValueError, git.GitCommandError):
                # Fresh repo with no commits yet — proceed
                pass

            # Commit
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
            commit_msg = f"Archive update — {timestamp}"
            repo.index.commit(commit_msg)
            logger.info("Committed: %s", commit_msg)

            # Push
            if remote_url:
                _ensure_origin(repo, remote_url)
                origin = repo.remotes.origin
                # switch to target branch if needed, then push with upstream
                if repo.active_branch.name != push_branch:
                    _checkout_or_create(repo, push_branch)
                origin.push(f"{push_branch}:{push_branch}", set_upstream=True)
                logger.info("Pushed to %s (%s)", _redact_url(remote_url), push_branch)

            self._last_commit = time.time()
            self._pending = False
            self._has_unpushed = False
        except Exception as e:
            logger.error("Git operation failed: %s", e)
            self._has_unpushed = True

    def flush_now(self) -> None:
        """Force an immediate commit and push regardless of debounce."""
        self._pending = True
        self._debounce = 0
        self._flush()

    async def run_flusher(self) -> None:
        """Background task: periodically flush pending changes after the debounce window."""
        while True:
            await asyncio.sleep(max(self._debounce, 1))
            if self._pending and (time.time() - self._last_commit) >= self._debounce:
                # Run the (sync, blocking) flush in a worker thread so we don't
                # stall the event loop on git operations / network push.
                await asyncio.to_thread(self._flush)
