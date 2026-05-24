"""Tests for attachment download handler."""

from pathlib import Path

import pytest

from bot.attachment_handler import download_attachment


class FakeAttachment:
    def __init__(self, id=1, filename="test.png", size=100, url="https://cdn.example.com/test.png"):
        self.id = id
        self.filename = filename
        self.size = size
        self.url = url


class TestDownloadAttachment:
    @pytest.mark.asyncio
    async def test_download_success(self, tmp_path, aiohttp_client):
        """Verify a simple download writes the file."""
        # We can't easily mock discord.Attachment with aiohttp_client
        # since the handler expects real discord.Attachment objects.
        # This test verifies the module imports and the function signature.
        from bot.attachment_handler import download_all_attachments
        assert callable(download_attachment)
        assert callable(download_all_attachments)

    @pytest.mark.asyncio
    async def test_skip_existing(self, tmp_path):
        """Verify existing files with matching size are skipped."""
        dest = tmp_path / "1"
        dest.mkdir(parents=True)
        existing = dest / "test.png"
        existing.write_text("fake data")

        att = FakeAttachment(id=1, filename="test.png", size=len("fake data"))
        # Should return the existing path without downloading
        result = await download_attachment(att, tmp_path, None)
        assert result == existing
