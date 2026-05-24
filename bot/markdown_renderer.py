"""Convert Discord messages to markdown with YAML frontmatter."""

import datetime
from typing import Any

import discord
from jinja2 import Environment, FileSystemLoader, select_autoescape

_tmpl_env: Environment | None = None


def _get_env() -> Environment:
    global _tmpl_env
    if _tmpl_env is None:
        loader = FileSystemLoader("bot/templates")
        _tmpl_env = Environment(loader=loader, autoescape=select_autoescape())
    return _tmpl_env


def _format_timestamp(dt: datetime.datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.isoformat()


def _attachment_info(att: discord.Attachment, base_url: str = "") -> dict[str, Any]:
    return {
        "id": str(att.id),
        "filename": att.filename,
        "url": f"{base_url}/attachments/{att.id}/{att.filename}",
        "size": att.size,
        "content_type": att.content_type or "application/octet-stream",
        "is_image": att.content_type is not None and att.content_type.startswith("image/"),
        "is_video": att.content_type is not None and att.content_type.startswith("video/"),
    }


def render_message(
    message: discord.Message,
    channel_name: str = "",
    thread_name: str = "",
) -> str:
    """Render a single Discord message as markdown with YAML frontmatter."""
    env = _get_env()
    tmpl = env.get_template("message.md.j2")

    embeds = []
    for embed in message.embeds:
        e: dict[str, Any] = {
            "title": embed.title,
            "description": embed.description,
            "url": embed.url,
            "color": embed.color.value if embed.color else None,
            "fields": [
                {"name": f.name, "value": f.value, "inline": f.inline}
                for f in embed.fields
            ],
            "image_url": str(embed.image.url) if embed.image and embed.image.url else None,
            "thumbnail_url": str(embed.thumbnail.url) if embed.thumbnail and embed.thumbnail.url else None,
        }
        embeds.append(e)

    attachments = [_attachment_info(a) for a in message.attachments]

    ctx = {
        "message_id": str(message.id),
        "channel_id": str(message.channel.id),
        "channel_name": channel_name,
        "thread_id": None,
        "thread_name": thread_name,
        "author": str(message.author),
        "author_id": str(message.author.id),
        "author_avatar": str(message.author.display_avatar.url) if message.author.display_avatar else None,
        "timestamp": _format_timestamp(message.created_at),
        "edited": _format_timestamp(message.edited_at) if message.edited_at else None,
        "content": message.content,
        "embeds": embeds,
        "attachments": attachments,
        "reactions": [
            {"emoji": str(r.emoji), "count": r.count}
            for r in message.reactions
        ],
        "pinned": message.pinned,
        "jump_url": message.jump_url,
    }

    # Set thread info from the message's thread
    if isinstance(message.channel, discord.Thread):
        ctx["thread_id"] = str(message.channel.id)
        ctx["thread_name"] = thread_name or message.channel.name

    return tmpl.render(**ctx)
