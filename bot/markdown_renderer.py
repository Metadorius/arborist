"""Convert Discord messages to markdown with YAML frontmatter."""

import datetime
from typing import Any

import discord
import yaml


def parse_frontmatter(text: str) -> dict:
    """Parse YAML frontmatter from a markdown string. Returns {} if absent or invalid."""
    if not text.startswith("---"):
        return {}
    try:
        _, fm_block, _ = text.split("---", 2)
    except ValueError:
        return {}
    try:
        data = yaml.safe_load(fm_block)
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


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


def _dump_frontmatter(data: dict) -> str:
    """Serialize a dict as YAML, dropping None values and empty lists."""
    cleaned = {}
    for k, v in data.items():
        if v is None:
            continue
        if isinstance(v, list) and len(v) == 0:
            continue
        cleaned[k] = v
    return yaml.dump(cleaned, sort_keys=False, allow_unicode=True, default_flow_style=False)


def render_message(
    message: discord.Message,
    channel_name: str = "",
    thread_name: str = "",
) -> str:
    """Render a single Discord message as markdown with YAML frontmatter."""
    embeds = []
    for embed in message.embeds:
        e: dict[str, Any] = {
            "title": embed.title,
            "description": embed.description,
            "url": embed.url,
            "color": embed.color.value if embed.color else None,
            "author_name": embed.author.name if embed.author else None,
            "author_url": embed.author.url if embed.author else None,
            "author_icon": str(embed.author.icon_url) if embed.author and embed.author.icon_url else None,
            "provider_name": embed.provider.name if embed.provider else None,
            "provider_url": embed.provider.url if embed.provider else None,
            "fields": [
                {"name": f.name, "value": f.value, "inline": f.inline}
                for f in embed.fields
            ],
            "image_url": str(embed.image.url) if embed.image and embed.image.url else None,
            "thumbnail_url": str(embed.thumbnail.url) if embed.thumbnail and embed.thumbnail.url else None,
        }
        embeds.append(e)

    attachments = [_attachment_info(a) for a in message.attachments]

    # Build frontmatter — only non-None / non-empty values
    frontmatter: dict[str, Any] = {
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
        "pinned": message.pinned,
        "jump_url": message.jump_url,
        "attachments": attachments,
        "reactions": [
            {"emoji": str(r.emoji), "count": r.count}
            for r in message.reactions
        ],
        "embeds": embeds,
    }

    if isinstance(message.channel, discord.Thread):
        frontmatter["thread_id"] = str(message.channel.id)
        frontmatter["thread_name"] = thread_name or message.channel.name

    # Body is the raw message content
    body = (message.content or "").strip("\n")
    if body:
        body += "\n"

    return f"---\n{_dump_frontmatter(frontmatter)}---\n{body}"
