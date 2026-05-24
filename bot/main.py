import asyncio
import logging
from pathlib import Path

import aiohttp
import discord
from discord import app_commands

from .archiver import Archiver
from .config import get_discord_token, get_channel_ids, get_output_dir, get_site_dir
from .git_manager import GitManager

logger = logging.getLogger("arborist")


class ArboristClient(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        super().__init__(intents=intents)
        self._git = GitManager(get_output_dir())
        self._archiver = Archiver(self, get_output_dir(), git_manager=self._git)
        self._tree = app_commands.CommandTree(self)

    async def setup_hook(self) -> None:
        self._tree.add_command(_make_archive_command(self._archiver, get_channel_ids()))

    async def on_ready(self) -> None:
        user_info = self.user
        logger.info("Logged in as %s (ID: %s)", getattr(user_info, "name", "?"), getattr(user_info, "id", "?"))
        logger.info("Connected to %d guild(s)", len(self.guilds))
        logger.info("Watching channel IDs: %s", get_channel_ids())

        await self._tree.sync()
        _copy_site_files(get_site_dir(), get_output_dir())

        for cid in get_channel_ids():
            ch = self.get_channel(int(cid))
            if ch is None:
                logger.warning("  Channel %s not found", cid)
            elif isinstance(ch, (discord.TextChannel, discord.ForumChannel)):
                logger.info("  Channel %s: %s (%s)", cid, ch.name, type(ch).__name__)
            else:
                logger.info("  Channel %s: type %s", cid, type(ch).__name__)

    # ------------------------------------------------------------------
    # Live event handlers
    # ------------------------------------------------------------------

    def _is_watched(self, channel_id: int) -> bool:
        return str(channel_id) in get_channel_ids()

    def _is_watched_thread(self, thread: discord.Thread | None) -> bool:
        return thread is not None and self._is_watched(thread.parent_id)

    async def on_thread_create(self, thread: discord.Thread) -> None:
        if not self._is_watched(thread.parent_id):
            return
        logger.info("New thread: %s", thread.name)
        async with aiohttp.ClientSession() as session:
            await self._archiver.archive_thread(thread, session)

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        thread = message.channel if isinstance(message.channel, discord.Thread) else None
        if thread is None or not self._is_watched_thread(thread):
            return
        logger.debug("New message in %s", thread.name)
        thread_dir = get_output_dir() / "channels" / str(thread.parent_id) / str(thread.id)
        thread_dir.mkdir(parents=True, exist_ok=True)
        channel_name = thread.parent.name if isinstance(thread.parent, discord.ForumChannel) else ""
        async with aiohttp.ClientSession() as session:
            await self._archiver._archive_message(
                message, thread_dir, session, channel_name, thread.name
            )
        messages = [msg async for msg in thread.history(limit=None, oldest_first=True)]
        self._archiver._write_thread_index(thread, messages)

    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        thread = after.channel if isinstance(after.channel, discord.Thread) else None
        if thread is None or not self._is_watched_thread(thread) or after.author.bot:
            return
        logger.debug("Message edited in %s", thread.name)
        thread_dir = get_output_dir() / "channels" / str(thread.parent_id) / str(thread.id)
        channel_name = thread.parent.name if isinstance(thread.parent, discord.ForumChannel) else ""
        async with aiohttp.ClientSession() as session:
            await self._archiver._archive_message(after, thread_dir, session, channel_name, thread.name)

    async def on_message_delete(self, message: discord.Message) -> None:
        channel = message.channel
        if not isinstance(channel, discord.Thread):
            return
        if not self._is_watched(channel.parent_id):
            return
        md_path = get_output_dir() / "channels" / str(channel.parent_id) / str(channel.id) / f"{message.id}.md"
        if md_path.exists():
            md_path.unlink()
            self._git.mark_changed()
            logger.info("Deleted archived message: %s", message.id)

    async def on_thread_update(self, before: discord.Thread, after: discord.Thread) -> None:
        if not self._is_watched(after.parent_id):
            return
        if before.name != after.name:
            logger.info("Thread renamed: %s -> %s", before.name, after.name)
            messages = [msg async for msg in after.history(limit=None, oldest_first=True)]
            self._archiver._write_thread_index(after, messages)


# ------------------------------------------------------------------
# Slash command: /archive channel
# ------------------------------------------------------------------

def _make_archive_command(archiver: Archiver, channel_ids: list[str]) -> app_commands.Command:
    @app_commands.command(name="archive", description="Archive forum channel posts")
    @app_commands.describe(channel="Channel ID or 'all'")
    async def archive(interaction: discord.Interaction, channel: str) -> None:
        await interaction.response.defer(ephemeral=True)
        ids_to_archive = channel_ids if channel.lower() == "all" else [channel]
        for cid_str in ids_to_archive:
            await interaction.followup.send(f"Archiving {cid_str}...", ephemeral=True)
            await archiver.archive_channel(int(cid_str))
        await interaction.followup.send("Archive complete.", ephemeral=True)
    return archive


def _copy_site_files(site_dir: Path, output_dir: Path) -> None:
    import shutil
    output_dir.mkdir(parents=True, exist_ok=True)
    for item in site_dir.iterdir():
        if item.is_file():
            dest = output_dir / item.name
            if not dest.exists() or dest.stat().st_mtime < item.stat().st_mtime:
                shutil.copy2(item, dest)
                logger.debug("Copied %s -> %s", item.name, dest)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    client = ArboristClient()
    async with client:
        await client.start(get_discord_token())


if __name__ == "__main__":
    asyncio.run(main())
