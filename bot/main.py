import asyncio
import logging
from collections import OrderedDict
from pathlib import Path

import aiohttp
import discord
from discord import app_commands

from .archiver import Archiver
from .config import get_discord_token, get_site_dir, get_config
from .git_manager import GitManager

logger = logging.getLogger("arborist")

_THREAD_CACHE_MAX = 50
_HTTP_TIMEOUT = aiohttp.ClientTimeout(total=120, sock_read=60)


class ArboristClient(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        super().__init__(intents=intents)
        self._output = get_config().output_dir
        self._git = GitManager(self._output)
        self._archiver = Archiver(self, self._output, git_manager=self._git)
        self._tree = app_commands.CommandTree(self)
        self._synced = False
        self._http: aiohttp.ClientSession | None = None
        self._flusher_task: asyncio.Task | None = None
        self._thread_msgs: OrderedDict[int, list[discord.Message]] = OrderedDict()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def setup_hook(self) -> None:
        self._http = aiohttp.ClientSession(timeout=_HTTP_TIMEOUT)
        self._archiver.set_session(self._http)
        self._tree.add_command(_make_archive_command(self._archiver, get_config().channel_ids))
        for cmd in _make_config_commands():
            self._tree.add_command(cmd)
        self._flusher_task = asyncio.create_task(self._git.run_flusher())

    async def close(self) -> None:
        if self._flusher_task is not None:
            self._flusher_task.cancel()
            try:
                await self._flusher_task
            except (asyncio.CancelledError, Exception):
                pass
        try:
            self._git.flush_now()
        except Exception:
            logger.exception("Final git flush failed")
        if self._http is not None:
            await self._http.close()
        await super().close()

    async def on_ready(self) -> None:
        user_info = self.user
        logger.info("Logged in as %s (ID: %s)", getattr(user_info, "name", "?"), getattr(user_info, "id", "?"))
        logger.info("Connected to %d guild(s)", len(self.guilds))
        logger.info("Watching channel IDs: %s", get_config().channel_ids)

        if not self._synced:
            await self._tree.sync()
            self._synced = True
        _copy_site_files(get_site_dir(), self._output)

        for cid in get_config().channel_ids:
            ch = self.get_channel(int(cid))
            if ch is None:
                logger.warning("  Channel %s not found", cid)
            elif isinstance(ch, (discord.TextChannel, discord.ForumChannel)):
                logger.info("  Channel %s: %s (%s)", cid, ch.name, type(ch).__name__)
            else:
                logger.info("  Channel %s: type %s", cid, type(ch).__name__)

    # ------------------------------------------------------------------
    # Watch predicates
    # ------------------------------------------------------------------

    def _is_watched(self, channel_id: int) -> bool:
        return str(channel_id) in get_config().channel_ids

    def _is_watched_thread(self, thread: discord.Thread | None) -> bool:
        return thread is not None and self._is_watched(thread.parent_id)

    # ------------------------------------------------------------------
    # Thread message cache (LRU)
    # ------------------------------------------------------------------

    async def _get_thread_messages(self, thread: discord.Thread) -> list[discord.Message]:
        cached = self._thread_msgs.get(thread.id)
        if cached is not None:
            self._thread_msgs.move_to_end(thread.id)
            return cached
        messages = [msg async for msg in thread.history(limit=None, oldest_first=True)]
        self._thread_msgs[thread.id] = messages
        self._thread_msgs.move_to_end(thread.id)
        while len(self._thread_msgs) > _THREAD_CACHE_MAX:
            self._thread_msgs.popitem(last=False)
        return messages

    def _drop_thread_cache(self, thread_id: int) -> None:
        self._thread_msgs.pop(thread_id, None)

    # ------------------------------------------------------------------
    # Live event handlers
    # ------------------------------------------------------------------

    async def on_thread_create(self, thread: discord.Thread) -> None:
        if not self._is_watched(thread.parent_id):
            return
        if self._http is None:
            return
        logger.info("New thread: %s", thread.name)
        await self._archiver.archive_thread(thread, self._http)

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        thread = message.channel if isinstance(message.channel, discord.Thread) else None
        if thread is None or not self._is_watched_thread(thread) or self._http is None:
            return
        logger.debug("New message in %s", thread.name)
        guild_id = str(thread.guild.id) if thread.guild else "0"
        thread_dir = self._output / "channels" / guild_id / str(thread.parent_id) / str(thread.id)
        thread_dir.mkdir(parents=True, exist_ok=True)
        channel_name = thread.parent.name if isinstance(thread.parent, discord.ForumChannel) else ""

        await self._archiver.archive_message(
            message, thread_dir, self._http, channel_name, thread.name
        )

        messages = await self._get_thread_messages(thread)
        # New message — append to cache (history fetch above already includes it
        # when the cache was cold, so guard on the last id to avoid dupes).
        if not messages or messages[-1].id != message.id:
            messages.append(message)
        self._archiver.rebuild_thread_index(thread, messages)

    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        thread = after.channel if isinstance(after.channel, discord.Thread) else None
        if thread is None or not self._is_watched_thread(thread) or after.author.bot:
            return
        if self._http is None:
            return
        logger.debug("Message edited in %s", thread.name)
        guild_id = str(thread.guild.id) if thread.guild else "0"
        thread_dir = self._output / "channels" / guild_id / str(thread.parent_id) / str(thread.id)
        channel_name = thread.parent.name if isinstance(thread.parent, discord.ForumChannel) else ""
        await self._archiver.archive_message(after, thread_dir, self._http, channel_name, thread.name)

        messages = await self._get_thread_messages(thread)
        for i, m in enumerate(messages):
            if m.id == after.id:
                messages[i] = after
                break
        self._archiver.rebuild_thread_index(thread, messages)

    async def on_message_delete(self, message: discord.Message) -> None:
        channel = message.channel
        if not isinstance(channel, discord.Thread):
            return
        if not self._is_watched(channel.parent_id):
            return
        guild_id = str(channel.guild.id) if channel.guild else "0"
        md_path = self._output / "channels" / guild_id / str(channel.parent_id) / str(channel.id) / f"{message.id}.md"
        if md_path.exists():
            md_path.unlink()
            self._git.mark_changed()
            logger.info("Deleted archived message: %s", message.id)
        cached = self._thread_msgs.get(channel.id)
        if cached is not None:
            self._thread_msgs[channel.id] = [m for m in cached if m.id != message.id]
            self._archiver.rebuild_thread_index(channel, self._thread_msgs[channel.id])

    async def on_thread_update(self, before: discord.Thread, after: discord.Thread) -> None:
        if not self._is_watched(after.parent_id):
            return
        if before.name != after.name:
            logger.info("Thread renamed: %s -> %s", before.name, after.name)
            messages = await self._get_thread_messages(after)
            self._archiver.rebuild_thread_index(after, messages)


# ------------------------------------------------------------------
# Slash command: /archive channel
# ------------------------------------------------------------------

def _make_archive_command(archiver: Archiver, channel_ids: list[str]) -> app_commands.Command:
    @app_commands.command(name="archive", description="Archive forum channel posts")
    @app_commands.describe(channel="Channel ID or 'all'")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def archive(interaction: discord.Interaction, channel: str) -> None:
        await interaction.response.defer(ephemeral=True)
        ids_to_archive = channel_ids if channel.lower() == "all" else [channel]
        for cid_str in ids_to_archive:
            await interaction.followup.send(f"Archiving {cid_str}...", ephemeral=True)
            await archiver.archive_channel(int(cid_str))
        await interaction.followup.send("Archive complete.", ephemeral=True)
    return archive


# ------------------------------------------------------------------
# Slash commands: /config
# ------------------------------------------------------------------

def _make_config_commands() -> list[app_commands.Command]:
    from .config import get_config

    @app_commands.command(name="config-show", description="Show current configuration")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def config_show(interaction: discord.Interaction) -> None:
        cfg = get_config()
        lines = [
            f"**Output dir:** `{cfg.output_dir}`",
            f"**Watched channels:** {', '.join(f'`{c}`' for c in cfg.channel_ids) or '*none*'}",
            f"**Git remote:** `{cfg.git_remote_url or '*not set*'}`",
            f"**Git branch:** `{cfg.git_branch}`",
            f"**Git user:** `{cfg.git_user_name} <{cfg.git_user_email}>`",
        ]
        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    @app_commands.command(name="config-watch", description="Add a forum channel to the watchlist")
    @app_commands.describe(channel_id="Channel ID to watch")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def config_watch(interaction: discord.Interaction, channel_id: str) -> None:
        cfg = get_config()
        if cfg.add_channel(channel_id):
            await interaction.response.send_message(f"Now watching channel `{channel_id}`.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Channel `{channel_id}` is already watched.", ephemeral=True)

    @app_commands.command(name="config-unwatch", description="Remove a forum channel from the watchlist")
    @app_commands.describe(channel_id="Channel ID to stop watching")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def config_unwatch(interaction: discord.Interaction, channel_id: str) -> None:
        cfg = get_config()
        if cfg.remove_channel(channel_id):
            await interaction.response.send_message(f"Stopped watching channel `{channel_id}`.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Channel `{channel_id}` was not in the watchlist.", ephemeral=True)

    @app_commands.command(name="config-git-remote", description="Set the git remote URL for pushing")
    @app_commands.describe(url="Git remote URL (e.g. https://github.com/user/repo.git)")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def config_git_remote(interaction: discord.Interaction, url: str) -> None:
        cfg = get_config()
        cfg.git_remote_url = url
        await interaction.response.send_message(f"Git remote set to `{url}`.", ephemeral=True)

    return [config_show, config_watch, config_unwatch, config_git_remote]


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
