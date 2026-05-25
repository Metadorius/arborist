"""Tests for Discord message → markdown rendering."""

from bot.markdown_renderer import render_message


class FakeAuthor:
    def __init__(self, name="TestUser", id=12345):
        self.name = name
        self.id = id
        self.display_avatar = None

    def __str__(self):
        return self.name


class FakeAttachment:
    def __init__(self, id=1, filename="file.png", size=1024, content_type="image/png"):
        self.id = id
        self.filename = filename
        self.size = size
        self.content_type = content_type

    def __repr__(self):
        return f"<Attachment {self.id}>"


class FakeEmbed:
    def __init__(self, title=None, description=None, url=None, color=None, fields=None, image=None, thumbnail=None):
        self.title = title
        self.description = description
        self.url = url
        self.color = color
        self.fields = fields or []
        self.image = image
        self.thumbnail = thumbnail


class FakeReaction:
    def __init__(self, emoji="👍", count=1):
        self.emoji = emoji
        self.count = count


class FakeMessage:
    def __init__(self, id=111, content="Hello", channel=None, author=None, attachments=None,
                 embeds=None, reactions=None, created_at=None, edited_at=None, pinned=False):
        self.id = id
        self.content = content
        self.channel = channel or FakeThread()
        self.author = author or FakeAuthor()
        self.attachments = attachments or []
        self.embeds = embeds or []
        self.reactions = reactions or []
        self.created_at = created_at
        self.edited_at = edited_at
        self.pinned = pinned
        self.jump_url = f"https://discord.com/channels/1/{self.channel.id}/{id}"


class FakeThread:
    def __init__(self, id=999, name="thread", parent=None, parent_id=888):
        self.id = id
        self.name = name
        self.parent = parent
        self.parent_id = parent_id


class FakeChannel:
    def __init__(self, id=888, name="channel"):
        self.id = id
        self.name = name


def _fake_dt(year=2026, month=5, day=24):
    """Create a fake datetime for testing."""
    from datetime import datetime, timezone
    return datetime(year, month, day, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Basic rendering
# ---------------------------------------------------------------------------

class TestRenderMessage:
    def test_basic_content(self):
        msg = FakeMessage(content="Hello world")
        result = render_message(msg, channel_name="assets", thread_name="cool-pack")
        assert "Hello world" in result
        assert 'message_id: "111"' in result
        assert 'channel_name: "assets"' in result
        assert 'thread_name: "cool-pack"' in result
        assert 'author: "TestUser"' in result

    def test_yaml_frontmatter(self):
        msg = FakeMessage(id=42, content="Test")
        result = render_message(msg, channel_name="ch", thread_name="th")
        assert result.startswith("---")
        assert "---" in result[3:]
        assert 'message_id: "42"' in result

    def test_with_attachments(self):
        att = FakeAttachment(id=77, filename="doc.pdf", size=2048, content_type="application/pdf")
        msg = FakeMessage(content="See attached", attachments=[att])
        result = render_message(msg)
        assert "doc.pdf" in result
        assert 'id: "77"' in result
        assert "size: 2048" in result

    def test_with_image_attachment(self):
        att = FakeAttachment(id=88, filename="pic.png", content_type="image/png")
        msg = FakeMessage(content="Look", attachments=[att])
        result = render_message(msg)
        assert "pic.png" in result
        assert "is_image: true" in result

    def test_with_embeds(self):
        embed = FakeEmbed(title="Embed Title", description="Embed description")
        msg = FakeMessage(content="Check embed", embeds=[embed])
        result = render_message(msg)
        assert "Embed Title" in result
        assert "Embed description" in result

    def test_with_reactions(self):
        r1 = FakeReaction(emoji="👍", count=3)
        r2 = FakeReaction(emoji="❤️", count=1)
        msg = FakeMessage(content="Nice", reactions=[r1, r2])
        result = render_message(msg)
        assert "👍" in result
        assert "3" in result
        assert "❤️" in result

    def test_empty_content(self):
        msg = FakeMessage(content="")
        result = render_message(msg)
        assert "message_id:" in result

    def test_channel_and_thread_in_frontmatter(self):
        msg = FakeMessage()
        result = render_message(msg, channel_name="assets", thread_name="cool-pack")
        assert 'channel_name: "assets"' in result
        assert 'thread_name: "cool-pack"' in result
