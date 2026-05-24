"""Core archiver: fetch Discord threads/messages, write markdown, download attachments."""

import logging
from pathlib import Path
from typing import Any

import aiohttp
import discord
from jinja2 import Environment, FileSystemLoader, select_autoescape

from .attachment_handler import download_all_attachments
from .discord_markdown import make_converter
from .markdown_renderer import render_message

logger = logging.getLogger("arborist.archiver")

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def _get_jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(),
    )


class Archiver:
    """Orchestrates archiving Discord forum channels to a local folder structure."""

    def __init__(self, client: discord.Client, output_dir: Path, git_manager=None) -> None:
        self._client = client
        self._output = output_dir
        self._channels_dir = output_dir / "channels"
        self._attachments_dir = output_dir / "attachments"
        self._env = _get_jinja_env()
        self._git = git_manager
        self._markdown_convert = make_converter()

    @staticmethod
    def _root(file_path: Path, base: Path) -> str:
        """Return relative path prefix to reach base from file_path."""
        depth = len(file_path.resolve().relative_to(base.resolve()).parents) - 1
        return "../" * max(depth, 0)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def archive_channel(self, channel_id: int, tree: list | None = None) -> None:
        """Fetch and archive all threads in a forum channel."""
        ch = self._client.get_channel(channel_id)
        if ch is None:
            ch = await self._client.fetch_channel(channel_id)

        if not isinstance(ch, discord.ForumChannel):
            logger.warning("Channel %s is not a ForumChannel, skipping", channel_id)
            return

        logger.info("Archiving forum channel: %s (ID: %s)", ch.name, ch.id)

        seen = set()
        all_threads: list[discord.Thread] = []

        for thread in ch.threads:
            if thread.id not in seen:
                seen.add(thread.id)
                all_threads.append(thread)

        async for thread in ch.archived_threads(limit=None):
            if thread.id not in seen:
                seen.add(thread.id)
                all_threads.append(thread)

        logger.info("Found %d threads in %s", len(all_threads), ch.name)

        async with aiohttp.ClientSession() as session:
            for thread in all_threads:
                await self.archive_thread(thread, session, tree)

        self._write_channel_index(ch, tree)
        self._write_home_index(tree)

    async def archive_thread(
        self, thread: discord.Thread, session: aiohttp.ClientSession, tree: list | None = None
    ) -> None:
        """Fetch all messages in a thread and archive them."""
        logger.info("Archiving thread: %s (ID: %s)", thread.name, thread.id)

        thread_dir = self._channels_dir / str(thread.parent_id) / str(thread.id)
        thread_dir.mkdir(parents=True, exist_ok=True)

        channel_name = ""
        if isinstance(thread.parent, discord.ForumChannel):
            channel_name = thread.parent.name

        messages = [msg async for msg in thread.history(limit=None, oldest_first=True)]
        logger.info("  %d messages in thread %s", len(messages), thread.name)

        for msg in messages:
            await self._archive_message(msg, thread_dir, session, channel_name, thread.name)

        self._write_thread_index(thread, messages, tree)
        logger.info("  Finished thread: %s", thread.name)

    # ------------------------------------------------------------------
    # Internal: message processing
    # ------------------------------------------------------------------

    async def _archive_message(
        self,
        message: discord.Message,
        thread_dir: Path,
        session: aiohttp.ClientSession,
        channel_name: str,
        thread_name: str,
    ) -> None:
        """Render and write a single message as markdown, download attachments."""
        md_content = render_message(message, channel_name=channel_name, thread_name=thread_name)
        md_path = thread_dir / f"{message.id}.md"
        md_path.write_text(md_content, encoding="utf-8")

        if message.attachments:
            attach_dir = self._attachments_dir / str(message.channel.id)
            await download_all_attachments(message.attachments, attach_dir, session)

        if self._git:
            self._git.mark_changed()

    # ------------------------------------------------------------------
    # Internal: HTML page generation
    # ------------------------------------------------------------------

    def _tree_or_build(self, tree: list | None = None) -> list:
        return tree if tree is not None else self._build_tree()

    def _write_thread_index(
        self, thread: discord.Thread, messages: list[discord.Message], tree: list | None = None
    ) -> None:
        """Generate the thread page (index.html) with all messages."""
        channel = thread.parent
        if channel is None:
            channel_name = str(thread.parent_id)
        elif isinstance(channel, discord.ForumChannel):
            channel_name = channel.name
        else:
            channel_name = str(channel.id)

        msg_data = []
        for m in messages:
            attachments = []
            for a in m.attachments:
                is_image = a.content_type is not None and a.content_type.startswith("image/")
                attachments.append({
                    "filename": a.filename,
                    "url": f"../../../attachments/{thread.parent_id}/{a.id}/{a.filename}",
                    "is_image": is_image,
                })

            msg_data.append({
                "id": str(m.id),
                "author": str(m.author),
                "timestamp": m.created_at.isoformat(),
                "edited": m.edited_at.isoformat() if m.edited_at else None,
                "content": self._markdown_convert(m.content or ""),
                "embeds": self._embeds_for_template(m.embeds),
                "attachments": attachments,
                "reactions": [{"emoji": str(r.emoji), "count": r.count} for r in m.reactions],
            })

        tmpl = self._env.get_template("thread.html.j2")
        thread_dir = self._channels_dir / str(thread.parent_id) / str(thread.id)
        thread_dir.mkdir(parents=True, exist_ok=True)
        index_path = thread_dir / "index.html"
        html = tmpl.render(
            root=self._root(index_path, self._output),
            tree=self._tree_or_build(tree),
            thread={"id": str(thread.id), "name": thread.name},
            channel={"id": str(thread.parent_id), "name": channel_name},
            messages=msg_data,
        )
        index_path.write_text(html, encoding="utf-8")

    def _write_channel_index(self, channel: discord.ForumChannel, tree: list | None = None) -> None:
        """Generate the channel page (index.html) listing its threads."""
        ch_dir = self._channels_dir / str(channel.id)
        ch_dir.mkdir(parents=True, exist_ok=True)

        threads = []
        for th_dir in sorted(ch_dir.iterdir()):
            if not th_dir.is_dir():
                continue
            thread_id = th_dir.name
            thread_name = thread_id
            md_files = list(th_dir.glob("*.md"))
            if md_files:
                first_md = md_files[0].read_text(encoding="utf-8")
                for line in first_md.splitlines():
                    if line.startswith("thread_name:"):
                        thread_name = line.split(":", 1)[1].strip().strip('"')
                        break
            msg_count = len(md_files)
            threads.append({
                "id": thread_id,
                "name": thread_name,
                "folder": thread_id,
                "message_count": msg_count,
                "updated": "",
            })

        index_path = ch_dir / "index.html"
        tmpl = self._env.get_template("channel.html.j2")
        html = tmpl.render(
            root=self._root(index_path, self._output),
            tree=self._tree_or_build(tree),
            channel={"id": str(channel.id), "name": channel.name, "thread_count": len(threads)},
            threads=threads,
            thread_id=None,
        )
        index_path.write_text(html, encoding="utf-8")

    def _write_home_index(self, tree: list | None = None) -> None:
        """Generate the root index.html listing all channels."""
        self._output.mkdir(parents=True, exist_ok=True)

        channels = []
        if self._channels_dir.exists():
            for ch_dir in sorted(self._channels_dir.iterdir()):
                if not ch_dir.is_dir():
                    continue
                channel_index = ch_dir / "index.html"
                if not channel_index.exists():
                    continue
                channel_id = ch_dir.name

                channel_name = channel_id
                index_html = channel_index.read_text(encoding="utf-8")
                for line in index_html.splitlines():
                    if line.strip().startswith("<h1>#"):
                        channel_name = line.strip().replace("<h1>#", "").replace("</h1>", "").strip()
                        break

                thread_count = sum(1 for p in ch_dir.iterdir() if p.is_dir())
                channels.append({
                    "name": channel_name,
                    "folder": f"channels/{channel_id}",
                    "thread_count": thread_count,
                })

        index_path = self._output / "index.html"
        tmpl = self._env.get_template("home.html.j2")
        html = tmpl.render(root=self._root(index_path, self._output), tree=self._build_tree(), channels=channels)
        index_path.write_text(html, encoding="utf-8")

        if self._git:
            self._git.mark_changed()

    # ------------------------------------------------------------------
    # Internal: helpers
    # ------------------------------------------------------------------


    async def archive_all_from_ids(self, channel_ids: list[int]) -> None:
        """Enumerate all channels first, build full tree, then archive."""
        tree = self._build_tree_from_ids(channel_ids)
        async with aiohttp.ClientSession() as session:
            for cid in channel_ids:
                ch = self._client.get_channel(cid) or await self._client.fetch_channel(cid)
                if not isinstance(ch, discord.ForumChannel):
                    continue
                all_threads = []
                seen = set()
                for thread in ch.threads:
                    if thread.id not in seen:
                        seen.add(thread.id)
                        all_threads.append(thread)
                async for thread in ch.archived_threads(limit=None):
                    if thread.id not in seen:
                        seen.add(thread.id)
                        all_threads.append(thread)
                for thread in all_threads:
                    await self.archive_thread(thread, session, tree)
                self._write_channel_index(ch, tree)
        self._write_home_index(tree)

    def _build_tree_from_ids(self, channel_ids: list[int]) -> list[dict]:
        """Build complete tree from Discord objects (before writing to disk)."""
        tree = []
        for cid in channel_ids:
            ch = self._client.get_channel(cid)
            if ch is None or not hasattr(ch, "threads"):
                continue
            threads = [{"id": str(t.id), "name": t.name, "folder": f"{cid}/{t.id}"}
                       for t in ch.threads]
            tree.append({"id": str(cid), "name": ch.name, "folder": str(cid), "threads": threads})
        return tree

    def regenerate_all(self) -> None:
        """Re-render channel + home pages. Do NOT touch thread pages —
        they keep their existing content (the tree sidebar on thread pages
        is a best-effort that gets fixed on next full archive)."""
        tree = self._build_tree()
        if not self._channels_dir.exists():
            return
        for ch_dir in sorted(self._channels_dir.iterdir()):
            if not ch_dir.is_dir():
                continue
            threads = []
            for th_dir in sorted(ch_dir.iterdir()):
                if not th_dir.is_dir():
                    continue
                th_name = self._read_thread_name(th_dir)
                threads.append({"id": th_dir.name, "name": th_name,
                                "folder": th_dir.name, "message_count": len(list(th_dir.glob("*.md"))), "updated": ""})
            idx = ch_dir / "index.html"
            t = self._env.get_template("channel.html.j2")
            idx.write_text(t.render(root=self._root(idx, self._output), tree=tree,
                channel={"id": ch_dir.name, "name": self._read_channel_name(ch_dir), "thread_count": len(threads)},
                threads=threads, thread_id=None), encoding="utf-8")
        channels = []
        for ch_dir in sorted(self._channels_dir.iterdir()):
            if ch_dir.is_dir():
                channels.append({"name": self._read_channel_name(ch_dir), "folder": "channels/" + ch_dir.name,
                                 "thread_count": sum(1 for p in ch_dir.iterdir() if p.is_dir())})
        home = self._output / "index.html"
        t3 = self._env.get_template("home.html.j2")
        home.write_text(t3.render(root=self._root(home, self._output), tree=tree, channels=channels), encoding="utf-8")

    @staticmethod
    def _embeds_for_template(embeds: list[discord.Embed]) -> list[dict[str, Any]]:
        result = []
        for e in embeds:
            result.append({
                "title": e.title,
                "description": e.description,
                "url": e.url,
                "fields": [{"name": f.name, "value": f.value} for f in e.fields],
                "image_url": str(e.image.url) if e.image and e.image.url else None,
            })
        return result

    def _build_tree(self) -> list[dict]:
        """Build full channel/thread tree for the unified sidebar."""
        channels = []
        if not self._channels_dir.exists():
            return channels
        for ch_dir in sorted(self._channels_dir.iterdir()):
            if not ch_dir.is_dir():
                continue
            ch_id = ch_dir.name
            ch_name = self._read_channel_name(ch_dir)
            threads = []
            for th_dir in sorted(ch_dir.iterdir()):
                if not th_dir.is_dir():
                    continue
                th_id = th_dir.name
                th_name = self._read_thread_name(th_dir)
                threads.append({"id": th_id, "name": th_name, "folder": f"{ch_id}/{th_id}"})
            channels.append({"id": ch_id, "name": ch_name, "folder": ch_id, "threads": threads})
        return channels

    @staticmethod
    def _read_channel_name(ch_dir: Path) -> str:
        """Read channel name from any thread's .md frontmatter, then fallback to HTML."""
        for th_dir in sorted(ch_dir.iterdir()):
            if th_dir.is_dir():
                for md in th_dir.glob("*.md"):
                    for line in md.read_text(encoding="utf-8").splitlines():
                        if line.startswith("channel_name:"):
                            return line.split(":", 1)[1].strip().strip('"')
        idx = ch_dir / "index.html"
        if idx.exists():
            for line in idx.read_text(encoding="utf-8").splitlines():
                s = line.strip()
                if s.startswith("<h1>#"):
                    return s.replace("<h1>#", "").replace("</h1>", "").strip()
        return ch_dir.name

    @staticmethod
    def _read_thread_name(th_dir: Path) -> str:
        """Read thread name from first .md frontmatter."""
        for md in th_dir.glob("*.md"):
            for line in md.read_text(encoding="utf-8").splitlines():
                if line.startswith("thread_name:"):
                    return line.split(":", 1)[1].strip().strip('"')
        return th_dir.name
