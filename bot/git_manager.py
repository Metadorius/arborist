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


class GitManager:
    """Manages a git repo for the output directory with debounced commits."""

    def __init__(self, repo_dir: Path, debounce_seconds: int = 300) -> None:
        self._repo_dir = repo_dir
        self._debounce = debounce_seconds
        self._last_commit = time.time()  # prevent immediate flush on first call
        self._pending = False
        self._repo: git.Repo | None = None
        self._has_unpushed = False

        # Resolve remote/branch once up front so logging never NameErrors.
        try:
            from .config import get_git_remote_url, get_git_branch
            self._remote_url = get_git_remote_url()
            self._branch = get_git_branch()
        except ValueError:
            self._remote_url = None
            self._branch = "main"
            logger.info("No remote configured, working locally")

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

            if self._remote_url:
                try:
                    self._repo.create_remote("origin", self._remote_url)
                except git.GitCommandError as e:
                    logger.warning("Failed to create remote: %s", e)

        self._set_user_config()
        return self._repo

    def _set_user_config(self) -> None:
        from .config import get_git_user_name, get_git_user_email
        if self._repo is None:
            return
        with self._repo.config_writer() as cw:
            cw.set_value("user", "name", get_git_user_name())
            cw.set_value("user", "email", get_git_user_email())

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

            # Push (skip if no remote, e.g. in tests)
            if repo.remotes:
                origin = repo.remotes.origin
                origin.push()
                logger.info("Pushed to %s (%s)", _redact_url(self._remote_url), self._branch)

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
