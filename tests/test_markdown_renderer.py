"""Tests for Discord message → markdown rendering."""

from bot.markdown_renderer import parse_frontmatter, render_message


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
        self.author = None
        self.provider = None


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
        fm = parse_frontmatter(result)
        body = result.split("---", 2)[2].lstrip("\n")
        assert body == "Hello world\n"
        assert fm["message_id"] == "111"
        assert fm["channel_name"] == "assets"
        assert fm["thread_name"] == "cool-pack"
        assert fm["author"] == "TestUser"

    def test_yaml_frontmatter(self):
        msg = FakeMessage(id=42, content="Test")
        result = render_message(msg, channel_name="ch", thread_name="th")
        fm = parse_frontmatter(result)
        body = result.split("---", 2)[2].lstrip("\n")
        assert fm["message_id"] == "42"
        assert body == "Test\n"

    def test_with_attachments(self):
        att = FakeAttachment(id=77, filename="doc.pdf", size=2048, content_type="application/pdf")
        msg = FakeMessage(content="See attached", attachments=[att])
        result = render_message(msg)
        fm = parse_frontmatter(result)
        body = result.split("---", 2)[2].lstrip("\n")
        assert body == "See attached\n\n[doc.pdf](/attachments/77/doc.pdf)\n"
        assert fm["attachments"][0]["id"] == "77"
        assert fm["attachments"][0]["size"] == 2048

    def test_with_image_attachment(self):
        att = FakeAttachment(id=88, filename="pic.png", content_type="image/png")
        msg = FakeMessage(content="Look", attachments=[att])
        result = render_message(msg)
        fm = parse_frontmatter(result)
        body = result.split("---", 2)[2].lstrip("\n")
        assert fm["attachments"][0]["is_image"] is True
        assert body == "Look\n\n![pic.png](/attachments/88/pic.png)\n"

    def test_with_embeds(self):
        embed = FakeEmbed(title="Embed Title", description="Embed description")
        msg = FakeMessage(content="Check embed", embeds=[embed])
        result = render_message(msg)
        body = result.split("---", 2)[2].lstrip("\n")
        assert "Embed Title" in body
        assert "Embed description" in body

    def test_with_reactions(self):
        r1 = FakeReaction(emoji="👍", count=3)
        r2 = FakeReaction(emoji="❤️", count=1)
        msg = FakeMessage(content="Nice", reactions=[r1, r2])
        result = render_message(msg)
        fm = parse_frontmatter(result)
        assert fm["reactions"][0]["emoji"] == "👍"
        assert fm["reactions"][0]["count"] == 3
        assert fm["reactions"][1]["emoji"] == "❤️"

    def test_empty_content(self):
        msg = FakeMessage(content="")
        result = render_message(msg)
        fm = parse_frontmatter(result)
        body = result.split("---", 2)[2]
        assert fm["message_id"] is not None
        assert body in ("\n", "\n\n")

    def test_channel_and_thread_in_frontmatter(self):
        msg = FakeMessage()
        result = render_message(msg, channel_name="assets", thread_name="cool-pack")
        fm = parse_frontmatter(result)
        assert fm["channel_name"] == "assets"
        assert fm["thread_name"] == "cool-pack"
