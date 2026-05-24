"""Tests for the Discord markdown → HTML converter."""

import pytest
from bot.discord_markdown import make_converter, DiscordRenderer


@pytest.fixture
def conv():
    return make_converter()


# ---------------------------------------------------------------------------
# Standard markdown
# ---------------------------------------------------------------------------

class TestStandardMarkdown:
    def test_bold(self, conv):
        assert conv("**hello**") == "<p><strong>hello</strong></p>\n"

    def test_italic(self, conv):
        assert conv("*hello*") == "<p><em>hello</em></p>\n"

    def test_strikethrough(self, conv):
        assert conv("~~strike~~") == "<p><del>strike</del></p>\n"

    def test_code_block(self, conv):
        html = conv("```python\nprint(1)\n```")
        assert '<div class="highlight">' in html
        assert "print" in html
        assert "<span" in html  # Pygments highlighting spans

    def test_code_block_no_lang(self, conv):
        html = conv("```\nplain\n```")
        assert "<pre><code>" in html
        assert "plain" in html

    def test_inline_code(self, conv):
        assert conv("use `code` here") == "<p>use <code>code</code> here</p>\n"

    def test_link(self, conv):
        assert conv("[text](https://x.com)") == '<p><a href="https://x.com">text</a></p>\n'

    def test_url_autolink(self, conv):
        html = conv("https://example.com")
        assert '<a href="https://example.com">' in html

    def test_table(self, conv):
        md = "| A | B |\n|---|---|\n| 1 | 2 |"
        html = conv(md)
        assert "<table>" in html
        assert "<th>" in html
        assert "<td>" in html

    def test_task_list(self, conv):
        md = "- [x] done\n- [ ] todo"
        html = conv(md)
        assert 'class="task-list-item"' in html
        assert 'checked' in html
        assert 'disabled' in html

    def test_blockquote(self, conv):
        assert conv("> quote") == "<blockquote>\n<p>quote</p>\n</blockquote>\n"

    def test_heading(self, conv):
        assert conv("## h2") == "<h2>h2</h2>\n"

    def test_list(self, conv):
        assert conv("- a\n- b") == "<ul>\n<li>a</li>\n<li>b</li>\n</ul>\n"


# ---------------------------------------------------------------------------
# Discord syntax
# ---------------------------------------------------------------------------

class TestDiscordSpoiler:
    def test_basic(self, conv):
        assert conv("||secret||") == '<p><span class="spoiler">secret</span></p>\n'

    def test_multi_word(self, conv):
        assert conv("||hidden text||") == '<p><span class="spoiler">hidden text</span></p>\n'

    def test_with_punctuation(self, conv):
        assert conv("||a b c!?||") == '<p><span class="spoiler">a b c!?</span></p>\n'

    def test_in_sentence(self, conv):
        html = conv("this is ||spoiler|| here")
        assert '<span class="spoiler">spoiler</span>' in html


class TestDiscordSmallText:
    def test_basic(self, conv):
        assert conv("-# small") == "<p><small>small</small></p>\n"

    def test_multi_word(self, conv):
        assert conv("-# some small text") == "<p><small>some small text</small></p>\n"


class TestDiscordEmoji:
    def test_custom_emoji(self, conv):
        html = conv("<:pepe:123456789>")
        assert '<span class="emoji emoji-custom">:pepe:</span>' in html

    def test_animated_emoji(self, conv):
        html = conv("<a:party:98765>")
        assert '<span class="emoji emoji-animated">:party:</span>' in html


class TestDiscordMentions:
    def test_user_mention(self, conv):
        html = conv("hey <@12345>!")
        assert '<span class="mention user-mention">@12345</span>' in html

    def test_user_mention_nick(self, conv):
        html = conv("<@!67890>")
        assert '<span class="mention user-mention">@67890</span>' in html

    def test_channel_mention(self, conv):
        html = conv("see <#999>")
        assert '<span class="mention channel-mention">#999</span>' in html

    def test_role_mention(self, conv):
        html = conv("ping <@&555>")
        assert '<span class="mention role-mention">@555</span>' in html

    def test_multiple(self, conv):
        html = conv("<@1> and <#2>")
        assert '@1' in html
        assert '#2' in html


class TestDiscordTimestamp:
    def test_basic(self, conv):
        html = conv("see <t:1234567890>")
        assert '<span class="discord-timestamp">' in html

    def test_with_style(self, conv):
        html = conv("<t:1234567890:R>")
        assert '<span class="discord-timestamp">' in html


class TestDiscordCombined:
    def test_bold_with_mention(self, conv):
        html = conv("**Hi** <@1>")
        assert "<strong>Hi</strong>" in html
        assert '@1' in html

    def test_spoiler_with_emoji(self, conv):
        html = conv("||<:sad:1>||")
        assert '<span class="spoiler">' in html
        assert ':sad:' in html


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------

class TestDiscordRenderer:
    def test_pygments_fallback(self):
        """When pygments lookup fails, render plain code block."""
        r = DiscordRenderer()
        result = r.block_code("x = 1", "nonexistent_lang_xyz")
        assert "<pre><code" in result
        assert "x = 1" in result
