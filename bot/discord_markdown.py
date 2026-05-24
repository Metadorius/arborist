"""Discord markdown to HTML — all Discord-specific syntax as proper mistune plugins.

Standard plugins: strikethrough, table, url, task_lists, footnotes

Discord plugins (all registered as inline parsers so mistune doesn't escape them):
- `||spoiler||`       -> <span class="spoiler">...</span>
- `-# small text`     -> <small>...</small>
- `<:name:id>`        -> <span class="emoji">:name:</span>
- `<a:name:id>`       -> <span class="emoji emoji-animated">:name:</span>
- `<@id>` / `<@!id>`  -> <span class="mention user-mention">@id</span>
- `<#id>`             -> <span class="mention channel-mention">#id</span>
- `<@&id>`            -> <span class="mention role-mention">@id</span>
- `<t:unix>`/`<t:unix:S>` -> <span class="discord-timestamp" ...>...</span>

Code blocks get syntax highlighting via custom DiscordRenderer (Pygments).
"""

import mistune
from mistune import escape as _escape


# ---------------------------------------------------------------------------
# Custom renderer
# ---------------------------------------------------------------------------

class DiscordRenderer(mistune.HTMLRenderer):
    """HTML renderer with Pygments code highlighting."""

    def block_code(self, code: str, info: str | None = None) -> str:
        if not info:
            return f"<pre><code>{_escape(code)}</code></pre>\n"
        try:
            from pygments import highlight as _highlight
            from pygments.formatters import HtmlFormatter
            from pygments.lexers import get_lexer_by_name
            lexer = get_lexer_by_name(info, stripall=True)
            return _highlight(code, lexer, HtmlFormatter())
        except Exception:
            return (
                f'<pre><code class="language-{_escape(info)}"'
                f"{_escape(code)}</code></pre>\n"
            )


# ---------------------------------------------------------------------------
# Plugin: ||spoiler||  (inline)
# ---------------------------------------------------------------------------

_SPOILER_RE = r"\|\|(?P<discord_spoiler_text>.+?)\|\|"


def _parse_spoiler(_, m, state):
    state.append_token({"type": "discord_spoiler", "raw": m.group("discord_spoiler_text")})
    return m.end()


def _render_spoiler(_, text):
    return f'<span class="spoiler">{text}</span>'


def spoiler_plugin(md):
    md.inline.register("discord_spoiler", _SPOILER_RE, _parse_spoiler, before="linebreak")
    if md.renderer and md.renderer.NAME == "html":
        md.renderer.register("discord_spoiler", _render_spoiler)


# ---------------------------------------------------------------------------
# Plugin: -# small text  (inline, line-level)
# ---------------------------------------------------------------------------

_SMALL_RE = r"^-#\s+(?P<discord_small_text>.+)$"


def _parse_small(_, m, state):
    state.append_token({"type": "discord_small", "raw": m.group("discord_small_text")})
    return m.end()


def _render_small(_, text):
    return f"<small>{text}</small>"


def small_text_plugin(md):
    md.inline.register("discord_small", _SMALL_RE, _parse_small, before="linebreak")
    if md.renderer and md.renderer.NAME == "html":
        md.renderer.register("discord_small", _render_small)


# ---------------------------------------------------------------------------
# Plugin: custom emoji  <:name:id>
# ---------------------------------------------------------------------------

_EMOJI_RE = r"<:(?P<discord_emoji_text>[a-zA-Z0-9_]+):\d+>"


def _parse_emoji(_, m, state):
    state.append_token({"type": "discord_emoji", "raw": m.group("discord_emoji_text")})
    return m.end()


def _render_emoji(_, text):
    return f'<span class="emoji emoji-custom">:{text}:</span>'


def emoji_plugin(md):
    md.inline.register("discord_emoji", _EMOJI_RE, _parse_emoji, before="linebreak")
    if md.renderer and md.renderer.NAME == "html":
        md.renderer.register("discord_emoji", _render_emoji)


# ---------------------------------------------------------------------------
# Plugin: animated emoji  <a:name:id>
# ---------------------------------------------------------------------------

_ANIM_EMOJI_RE = r"<a:(?P<discord_anim_emoji_text>[a-zA-Z0-9_]+):\d+>"


def _parse_anim_emoji(_, m, state):
    state.append_token({"type": "discord_emoji_animated", "raw": m.group("discord_anim_emoji_text")})
    return m.end()


def _render_anim_emoji(_, text):
    return f'<span class="emoji emoji-animated">:{text}:</span>'


def animated_emoji_plugin(md):
    md.inline.register("discord_emoji_animated", _ANIM_EMOJI_RE, _parse_anim_emoji, before="linebreak")
    if md.renderer and md.renderer.NAME == "html":
        md.renderer.register("discord_emoji_animated", _render_anim_emoji)


# ---------------------------------------------------------------------------
# Plugin: user mention  <@id> / <@!id>
# ---------------------------------------------------------------------------

_USER_MENTION_RE = r"<@!?(?P<discord_user_mention_text>\d+)>"


def _parse_user_mention(_, m, state):
    state.append_token({"type": "discord_user_mention", "raw": m.group("discord_user_mention_text")})
    return m.end()


def _render_user_mention(_, text):
    return f'<span class="mention user-mention">@{text}</span>'


def user_mention_plugin(md):
    md.inline.register("discord_user_mention", _USER_MENTION_RE, _parse_user_mention, before="linebreak")
    if md.renderer and md.renderer.NAME == "html":
        md.renderer.register("discord_user_mention", _render_user_mention)


# ---------------------------------------------------------------------------
# Plugin: channel mention  <#id>
# ---------------------------------------------------------------------------

_CHANNEL_MENTION_RE = r"<#(?P<discord_channel_mention_text>\d+)>"


def _parse_channel_mention(_, m, state):
    state.append_token({"type": "discord_channel_mention", "raw": m.group("discord_channel_mention_text")})
    return m.end()


def _render_channel_mention(_, text):
    return f'<span class="mention channel-mention">#{text}</span>'


def channel_mention_plugin(md):
    md.inline.register("discord_channel_mention", _CHANNEL_MENTION_RE, _parse_channel_mention, before="linebreak")
    if md.renderer and md.renderer.NAME == "html":
        md.renderer.register("discord_channel_mention", _render_channel_mention)


# ---------------------------------------------------------------------------
# Plugin: role mention  <@&id>
# ---------------------------------------------------------------------------

_ROLE_MENTION_RE = r"<@&(?P<discord_role_mention_text>\d+)>"


def _parse_role_mention(_, m, state):
    state.append_token({"type": "discord_role_mention", "raw": m.group("discord_role_mention_text")})
    return m.end()


def _render_role_mention(_, text):
    return f'<span class="mention role-mention">@{text}</span>'


def role_mention_plugin(md):
    md.inline.register("discord_role_mention", _ROLE_MENTION_RE, _parse_role_mention, before="linebreak")
    if md.renderer and md.renderer.NAME == "html":
        md.renderer.register("discord_role_mention", _render_role_mention)


# ---------------------------------------------------------------------------
# Plugin: timestamp  <t:unix> / <t:unix:style>
# ---------------------------------------------------------------------------

_TIMESTAMP_RE = r"<t:(?P<discord_timestamp_ts>\d+)(?::(?P<discord_timestamp_style>[a-zA-Z]))?>"


def _parse_timestamp(_, m, state):
    state.append_token({
        "type": "discord_timestamp",
        "raw": m.group("discord_timestamp_ts"),
        "attrs": {"style": m.group("discord_timestamp_style") or "f"},
    })
    return m.end()


def _render_timestamp(renderer, text, **kwargs):
    return '<span class="discord-timestamp">t</span>'

def timestamp_plugin(md):
    md.inline.register("discord_timestamp", _TIMESTAMP_RE, _parse_timestamp, before="linebreak")
    if md.renderer and md.renderer.NAME == "html":
        md.renderer.register("discord_timestamp", _render_timestamp)


# ---------------------------------------------------------------------------
# Public factory
# ---------------------------------------------------------------------------

__all__ = ["DiscordRenderer", "make_converter"]


def make_converter():
    """Create a function that converts Discord markdown text -> HTML."""
    renderer = DiscordRenderer()
    md = mistune.create_markdown(
        renderer=renderer,
        plugins=[
            "strikethrough",
            "table",
            "url",
            "task_lists",
            "footnotes",
            spoiler_plugin,
            small_text_plugin,
            emoji_plugin,
            animated_emoji_plugin,
            user_mention_plugin,
            channel_mention_plugin,
            role_mention_plugin,
            timestamp_plugin,
        ],
    )
    return md
