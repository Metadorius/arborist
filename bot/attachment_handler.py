"""Download Discord attachments with rate-limit awareness."""

import asyncio
import logging
from pathlib import Path

import aiohttp
import discord

logger = logging.getLogger("arborist.attachments")

_MAX_PARALLEL = 8
_MAX_RETRY_WAIT_S = 60.0
_CHUNK_SIZE = 64 * 1024

# Module-level semaphore; one event loop per process so this is safe.
_download_sem = asyncio.Semaphore(_MAX_PARALLEL)


def _safe_filename(name: str) -> str | None:
    """Return a basename safe for filesystem use, or None if rejected.

    Reject anything containing path separators or traversal — we don't want
    to silently flatten `../evil.txt` to `evil.txt` and accept it.
    """
    if not name or "/" in name or "\\" in name or name in (".", ".."):
        return None
    base = Path(name).name
    if not base or base in (".", ".."):
        return None
    return base


async def download_attachment(
    attachment: discord.Attachment,
    dest_dir: Path,
    session: aiohttp.ClientSession,
    max_retries: int = 3,
) -> Path | None:
    """Download a single attachment. Returns the saved file path or None on failure."""
    safe_name = _safe_filename(attachment.filename)
    if safe_name is None:
        logger.warning("Rejected unsafe attachment filename: %r", attachment.filename)
        return None

    # Each attachment gets its own subfolder: {attachment_id}/{filename}
    attach_dir = dest_dir / str(attachment.id)
    dest_path = attach_dir / safe_name

    # Skip if already downloaded with matching size
    if dest_path.exists() and dest_path.stat().st_size == attachment.size:
        logger.debug("Skipping %s (already downloaded)", dest_path)
        return dest_path

    attach_dir.mkdir(parents=True, exist_ok=True)

    cumulative_wait = 0.0
    async with _download_sem:
        for attempt in range(max_retries):
            try:
                async with session.get(attachment.url) as resp:
                    if resp.status == 429:
                        retry_after = float(resp.headers.get("Retry-After", "5"))
                        if cumulative_wait + retry_after > _MAX_RETRY_WAIT_S:
                            logger.error(
                                "Rate limit wait would exceed cap (%.1fs); giving up on %s",
                                _MAX_RETRY_WAIT_S, attachment.filename,
                            )
                            return None
                        cumulative_wait += retry_after
                        logger.warning("Rate limited, waiting %.1fs", retry_after)
                        await asyncio.sleep(retry_after)
                        continue  # 429 doesn't consume an attempt
                    resp.raise_for_status()
                    bytes_written = 0
                    tmp_path = dest_path.with_suffix(dest_path.suffix + ".part")
                    with tmp_path.open("wb") as f:
                        async for chunk in resp.content.iter_chunked(_CHUNK_SIZE):
                            f.write(chunk)
                            bytes_written += len(chunk)
                    tmp_path.replace(dest_path)
                    logger.debug("Downloaded %s (%d bytes)", dest_path, bytes_written)
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
    """Download multiple attachments in parallel (bounded by a module-level semaphore)."""
    tasks = [download_attachment(a, dest_dir, session) for a in attachments]
    results = await asyncio.gather(*tasks)
    return [p for p in results if p is not None]
