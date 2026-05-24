"""Git operations: stage, commit (debounced), push."""

import logging
import time
from pathlib import Path

import git

logger = logging.getLogger("arborist.git")


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

            # Try to set remote if configured
            try:
                from .config import get_git_remote_url, get_git_branch
                self._remote_url = get_git_remote_url()
                self._branch = get_git_branch()
                origin = self._repo.create_remote("origin", self._remote_url)
            except (ValueError, Exception):
                self._remote_url = "local"
                self._branch = "main"
                logger.info("No remote configured, working locally")

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
            # Stage all changes
            repo.index.add("*")

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
            if hasattr(repo, "remotes") and repo.remotes:
                origin = repo.remotes.origin
                origin.push()
                logger.info("Pushed to %s (%s)", self._remote_url, self._branch)

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
