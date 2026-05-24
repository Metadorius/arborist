"""Tests for the git manager."""

from pathlib import Path

import pytest

from bot.git_manager import GitManager

# These tests create real git repos in temp dirs so they're
# integration-level but self-contained (no network).


class TestGitManager:
    def test_ensure_repo_init(self, tmp_path):
        """Verify ensure_repo creates a git repo when none exists."""
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()

        mgr = GitManager(repo_dir, debounce_seconds=0)
        repo = mgr.ensure_repo()

        assert repo is not None
        assert (repo_dir / ".git").exists()
        assert not repo.bare

    def test_ensure_repo_idempotent(self, tmp_path):
        """Calling ensure_repo twice returns the same repo."""
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()

        mgr = GitManager(repo_dir)
        r1 = mgr.ensure_repo()
        r2 = mgr.ensure_repo()
        assert r1 is r2

    def test_mark_changed_commits_after_debounce(self, tmp_path):
        """After debounce period, mark_changed triggers a commit."""
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()

        mgr = GitManager(repo_dir, debounce_seconds=0)
        repo = mgr.ensure_repo()

        # Write a file
        (repo_dir / "test.txt").write_text("hello")
        mgr.mark_changed()

        # Check a commit was made
        assert repo.head.commit
        assert repo.head.commit.message.startswith("Archive update")

    def test_no_commit_without_changes(self, tmp_path):
        """mark_changed should not commit when nothing changed."""
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()

        mgr = GitManager(repo_dir, debounce_seconds=0)
        repo = mgr.ensure_repo()

        # Write and commit once
        (repo_dir / "a.txt").write_text("a")
        mgr.mark_changed()
        first = repo.head.commit

        # Call again with no changes
        mgr.mark_changed()
        assert repo.head.commit == first  # same commit

    def test_mark_changed_respects_debounce(self, tmp_path):
        """Multiple rapid calls within debounce should only commit once."""
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()

        mgr = GitManager(repo_dir, debounce_seconds=3600)  # 1 hour debounce
        repo = mgr.ensure_repo()

        (repo_dir / "a.txt").write_text("a")
        mgr.mark_changed()
        (repo_dir / "b.txt").write_text("b")
        mgr.mark_changed()

        # Force flush the accumulated changes
        mgr.flush_now()

        # Should see changes from both files in a single commit
        committed_files = list(repo.head.commit.stats.files.keys())
        assert "a.txt" in committed_files
        assert "b.txt" in committed_files

    def test_flush_now_bypasses_debounce(self, tmp_path):
        """flush_now commits immediately regardless of debounce."""
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()

        mgr = GitManager(repo_dir, debounce_seconds=3600)
        repo = mgr.ensure_repo()

        (repo_dir / "x.txt").write_text("x")
        mgr.mark_changed()
        (repo_dir / "y.txt").write_text("y")
        mgr.flush_now()

        # Check both files are in the latest commit
        committed_files = list(repo.head.commit.stats.files.keys())
        assert "x.txt" in committed_files
        assert "y.txt" in committed_files
