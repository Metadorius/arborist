"""Download Discord attachments with rate-limit awareness."""

import asyncio
import logging
from pathlib import Path

import aiohttp
import discord

logger = logging.getLogger("arborist.attachments")


async def download_attachment(
    attachment: discord.Attachment,
    dest_dir: Path,
    session: aiohttp.ClientSession,
    max_retries: int = 3,
) -> Path | None:
    """Download a single attachment. Returns the saved file path or None on failure."""
    # Each attachment gets its own subfolder: {attachment_id}/{filename}
    attach_dir = dest_dir / str(attachment.id)
    dest_path = attach_dir / attachment.filename

    # Skip if already downloaded with matching size
    if dest_path.exists() and dest_path.stat().st_size == attachment.size:
        logger.debug("Skipping %s (already downloaded)", dest_path)
        return dest_path

    attach_dir.mkdir(parents=True, exist_ok=True)

    for attempt in range(max_retries):
        try:
            async with session.get(attachment.url) as resp:
                if resp.status == 429:
                    retry_after = float(resp.headers.get("Retry-After", "5"))
                    logger.warning("Rate limited, waiting %.1fs", retry_after)
                    await asyncio.sleep(retry_after)
                    continue
                resp.raise_for_status()
                data = await resp.read()
                dest_path.write_bytes(data)
                logger.debug("Downloaded %s (%d bytes)", dest_path, len(data))
                return dest_path
        except aiohttp.ClientError as e:
            logger.warning("Download attempt %d/%d failed: %s", attempt + 1, max_retries, e)
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)

    logger.error("Failed to download %s after %d attempts", attachment.filename, max_retries)
    return None


async def download_all_attachments(
    attachments: list[discord.Attachment],
    dest_dir: Path,
    session: aiohttp.ClientSession,
) -> list[Path]:
    """Download multiple attachments in parallel. Returns list of saved paths."""
    tasks = [download_attachment(a, dest_dir, session) for a in attachments]
    results = await asyncio.gather(*tasks)
    return [p for p in results if p is not None]
