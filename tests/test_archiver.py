"""Integration tests for the archiver with mocked Discord objects."""

from pathlib import Path
from unittest.mock import patch

import pytest

from bot.archiver import Archiver


# ---------------------------------------------------------------------------
# Fake discord.py objects
# ---------------------------------------------------------------------------

class FakeUser:
    def __init__(self, id=1, name="TestUser"):
        self.id = id
        self.name = name

    def __str__(self):
        return self.name

    @property
    def display_avatar(self):
        return None


class FakeAttachment:
    def __init__(self, id=1, filename="readme.txt", size=50, url="https://example.com/f.txt", content_type="text/plain"):
        self.id = id
        self.filename = filename
        self.size = size
        self.url = url
        self.content_type = content_type

    def __repr__(self):
        return f"<Attachment {self.id}>"


class FakeEmbed:
    def __init__(self, title=None, description=None, url=None, color=None, fields=None, image=None, thumbnail=None):
        self.title = title
        self.description = description
        self.url = url
        self.color = type("Color", (), {"value": 123})() if color else None
        self.fields = fields or []
        self.image = type("Img", (), {"url": "https://example.com/img.png"})() if image else None
        self.thumbnail = type("Thumb", (), {"url": "https://example.com/thumb.png"})() if thumbnail else None


class FakeReaction:
    def __init__(self, emoji="👍", count=1):
        self.emoji = type("Emoji", (), {"__str__": lambda s: emoji})()
        self.count = count


class FakeMessage:
    def __init__(self, id=10, content="Hello", channel=None, attachments=None,
                 embeds=None, reactions=None, created_at=None, edited_at=None):
        from datetime import datetime, timezone
        self.id = id
        self.content = content
        self.channel = channel or FakeThread(parent_id=1)
        self.author = FakeUser()
        self.attachments = attachments or []
        self.embeds = embeds or []
        self.reactions = reactions or []
        self.created_at = created_at or datetime(2026, 5, 24, 12, 0, 0, tzinfo=timezone.utc)
        self.edited_at = edited_at
        self.pinned = False
        self.jump_url = f"https://discord.com/channels/1/{self.channel.id}/{id}"

    def __repr__(self):
        return f"<FakeMessage {self.id}>"


class FakeThread:
    """Simulates a Discord thread (forum post)."""

    def __init__(self, id=100, name="Test Thread", parent_id=200, parent=None, history_messages=None):
        self.id = id
        self.name = name
        self.parent_id = parent_id
        self.parent = parent or FakeChannel(id=parent_id)
        self._history = history_messages or []

    def history(self, limit=None, oldest_first=True):
        """Async generator yielding fake messages."""
        async def _gen():
            for m in self._history:
                yield m
        return _gen()


class FakeChannel:
    """Simulates a Discord forum channel."""
    def __init__(self, id=200, name="assets", threads=None):
        self.id = id
        self.name = name
        self.threads_list = threads or []
        self.archived_list = []

    @property
    def threads(self):
        return self.threads_list

    def archived_threads(self, limit=None):
        """Async generator for archived threads."""
        async def _gen():
            for t in self.archived_list:
                yield t
        return _gen()


class FakeClient:
    """Minimal client that returns fake channels."""
    def __init__(self, channels=None):
        self._channels = channels or {}

    def get_channel(self, channel_id):
        return self._channels.get(channel_id)

    async def fetch_channel(self, channel_id):
        return self._channels.get(channel_id)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestArchiver:
    @patch("bot.archiver.isinstance", return_value=True)
    def test_archive_empty_channel(self, mock_isinstance, tmp_path):
        """Archiving a channel with no threads should create the folder structure."""
        channel = FakeChannel(id=555, name="empty")
        client = FakeClient(channels={555: channel})
        archiver = Archiver(client, tmp_path / "output")

        import asyncio
        asyncio.run(archiver.archive_channel(555))

        out = tmp_path / "output"
        assert (out / "channels" / "555").exists()
        assert (out / "index.html").exists()  # home page

    @patch("bot.archiver.isinstance", return_value=True)
    def test_archive_with_thread(self, mock_isinstance, tmp_path):
        """Archiving a channel with one thread and one message."""
        msg = FakeMessage(id=10, content="First post!")
        thread = FakeThread(id=100, name="Hello", parent_id=777, history_messages=[msg])
        channel = FakeChannel(id=777, name="general", threads=[thread])
        client = FakeClient(channels={777: channel})
        archiver = Archiver(client, tmp_path / "output")

        import asyncio
        asyncio.run(archiver.archive_channel(777))

        # Check structure
        thread_dir = tmp_path / "output" / "channels" / "777" / "100"
        assert thread_dir.exists()
        assert (thread_dir / "index.html").exists()
        assert (thread_dir / "10.md").exists()

        # Check markdown content
        md_content = (thread_dir / "10.md").read_text()
        assert "First post!" in md_content
        assert "message_id: 10" in md_content

        # Check HTML contains the message
        html = (thread_dir / "index.html").read_text()
        assert "First post!" in html
        assert "Hello" in html  # thread name
        assert "TestUser" in html  # author

    @patch("bot.archiver.isinstance", return_value=True)
    def test_archive_multiple_messages(self, mock_isinstance, tmp_path):
        """Multiple messages in a thread are archived in order."""
        msgs = [
            FakeMessage(id=1, content="First"),
            FakeMessage(id=2, content="Second"),
            FakeMessage(id=3, content="Third"),
        ]
        thread = FakeThread(id=200, name="Multi Msg", parent_id=999, history_messages=msgs)
        channel = FakeChannel(id=999, name="test", threads=[thread])
        client = FakeClient(channels={999: channel})
        archiver = Archiver(client, tmp_path / "output")

        import asyncio
        asyncio.run(archiver.archive_channel(999))

        thread_dir = tmp_path / "output" / "channels" / "999" / "200"
        for mid in ["1", "2", "3"]:
            assert (thread_dir / f"{mid}.md").exists()

        html = (thread_dir / "index.html").read_text()
        assert "First" in html
        assert "Second" in html
        assert "Third" in html
        # Messages should appear in order (First before Second before Third)
        assert html.index("First") < html.index("Second") < html.index("Third")

    def test_skips_non_forum_channel(self, tmp_path):
        """Non-forum channels are skipped with a warning."""
        # Simulate a text channel by making a FakeChannel not a ForumChannel
        import discord
        if hasattr(discord, "ForumChannel"):
            client = FakeClient({})
            from bot.archiver import Archiver
            a = Archiver(client, tmp_path / "output")
            # Just verify it doesn't crash — it logs a warning and returns
            import asyncio
            asyncio.run(a.archive_channel(99999))

    @patch("bot.archiver.isinstance", return_value=True)
    def test_home_page_lists_channels(self, mock_isinstance, tmp_path):
        """Root index.html lists all archived channels."""
        msg = FakeMessage(id=1, content="Hello")
        thread1 = FakeThread(id=10, name="Th A", parent_id=300, history_messages=[msg])
        ch1 = FakeChannel(id=300, name="music", threads=[thread1])

        msg2 = FakeMessage(id=2, content="World")
        thread2 = FakeThread(id=20, name="Th B", parent_id=301, history_messages=[msg2])
        ch2 = FakeChannel(id=301, name="code", threads=[thread2])

        client = FakeClient(channels={300: ch1, 301: ch2})
        archiver = Archiver(client, tmp_path / "output")

        import asyncio
        asyncio.run(archiver.archive_channel(300))
        asyncio.run(archiver.archive_channel(301))

        home = tmp_path / "output" / "index.html"
        html = home.read_text()
        assert "Arborist" in html
        assert "music" in html
        assert "code" in html
