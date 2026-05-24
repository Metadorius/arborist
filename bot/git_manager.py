"""Git operations: stage, commit (debounced), push."""

import logging
import time
from pathlib import Path

import git

from .config import GIT_USER_NAME, GIT_USER_EMAIL, GIT_REMOTE_URL, GIT_BRANCH

logger = logging.getLogger("arborist.git")


class GitManager:
    """Manages a git repo for the output directory with debounced commits."""

    def __init__(self, repo_dir: Path, debounce_seconds: int = 300) -> None:
        self._repo_dir = repo_dir
        self._debounce = debounce_seconds
        self._last_commit = 0.0
        self._pending = False
        self._repo: git.Repo | None = None
        self._has_unpushed = False

    def ensure_repo(self) -> git.Repo:
        """Clone or open the git repo in the output directory."""
        if self._repo is not None:
            return self._repo

        git_dir = self._repo_dir / ".git"

        if git_dir.exists():
            logger.info("Opening existing repo at %s", self._repo_dir)
            self._repo = git.Repo(self._repo_dir)
        else:
            logger.info("Cloning %s into %s", GIT_REMOTE_URL, self._repo_dir)
            self._repo_dir.mkdir(parents=True, exist_ok=True)
            self._repo = git.Repo.clone_from(GIT_REMOTE_URL, self._repo_dir, branch=GIT_BRANCH)

        with self._repo.config_writer() as cw:
            cw.set_value("user", "name", GIT_USER_NAME)
            cw.set_value("user", "email", GIT_USER_EMAIL)

        return self._repo

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
            # Stage all changes
            repo.index.add("*")

            # Skip if nothing changed
            if not repo.index.diff("HEAD"):
                logger.debug("Nothing to commit")
                self._pending = False
                return

            # Commit
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
            commit_msg = f"Archive update — {timestamp}"
            repo.index.commit(commit_msg)
            logger.info("Committed: %s", commit_msg)

            # Push
            origin = repo.remotes.origin
            origin.push()
            logger.info("Pushed to %s (%s)", GIT_REMOTE_URL, GIT_BRANCH)

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
