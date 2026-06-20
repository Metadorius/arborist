"""Core archiver: fetch Discord threads/messages, write markdown, download attachments."""

import logging
from pathlib import Path
from typing import Any

import aiohttp
import discord
import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

from .attachment_handler import download_all_attachments
from .discord_markdown import make_converter
from .markdown_renderer import render_message

logger = logging.getLogger("arborist.archiver")

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def _format_size(size: int) -> str:
    """Format a byte count to a human-readable string. e.g. 5.2 MB."""
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}" if unit != "B" else f"{size} B"
        size /= 1024
    return f"{size:.1f} TB"


def _extract_tags(thread: discord.Thread) -> list[dict]:
    """Extract applied forum tags from a thread."""
    tags = []
    if hasattr(thread, "applied_tags") and thread.applied_tags:
        for t in thread.applied_tags:
            emoji = str(t.emoji) if t.emoji else None
            tags.append({"name": t.name, "emoji": emoji})
    return tags


def _get_jinja_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(),
    )
    env.filters["filesize"] = _format_size
    return env


def _read_frontmatter(md_path: Path) -> dict:
    """Parse YAML frontmatter from a `.md` file. Returns {} if absent or invalid."""
    try:
        text = md_path.read_text(encoding="utf-8")
    except OSError:
        return {}
    from .markdown_renderer import parse_frontmatter
    return parse_frontmatter(text)


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
        self._session: aiohttp.ClientSession | None = None

    def set_session(self, session: aiohttp.ClientSession) -> None:
        """Attach a long-lived aiohttp session for attachment downloads."""
        self._session = session

    @staticmethod
    def _root(file_path: Path, base: Path) -> str:
        """Return relative path prefix to reach base from file_path."""
        depth = len(file_path.resolve().relative_to(base.resolve()).parents) - 1
        return "../" * max(depth, 0)

    @staticmethod
    def _guild_id(thread: discord.Thread) -> str:
        """Extract guild ID from a thread, falling back to parent."""
        if thread.guild is not None:
            return str(thread.guild.id)
        if thread.parent and thread.parent.guild:
            return str(thread.parent.guild.id)
        return "0"

    @staticmethod
    def _channel_guild_id(channel: discord.ForumChannel) -> str:
        """Extract guild ID from a forum channel."""
        if channel.guild is not None:
            return str(channel.guild.id)
        return "0"

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

        all_threads = await self._collect_threads(ch)
        logger.info("Found %d threads in %s", len(all_threads), ch.name)

        # Build the sidebar tree up front so thread pages rendered mid-loop
        # already include every sibling thread.
        if tree is None:
            tree = self._merge_channel_into_tree(self._build_tree(), ch, all_threads)

        async with self._session_context() as session:
            for thread in all_threads:
                await self.archive_thread(thread, session, tree)

        self._write_channel_index(ch, tree)
        self._write_home_index(tree)

    def _session_context(self):
        """Yield self._session if set, else a fresh short-lived session."""
        outer = self._session

        class _Ctx:
            async def __aenter__(self_inner):
                if outer is not None:
                    return outer
                self_inner._created = aiohttp.ClientSession()
                return self_inner._created

            async def __aexit__(self_inner, *exc):
                created = getattr(self_inner, "_created", None)
                if created is not None:
                    await created.close()
                return False

        return _Ctx()

    async def archive_thread(
        self, thread: discord.Thread, session: aiohttp.ClientSession, tree: list | None = None
    ) -> None:
        """Fetch all messages in a thread and archive them."""
        logger.info("Archiving thread: %s (ID: %s)", thread.name, thread.id)

        guild_id = self._guild_id(thread)
        thread_dir = self._channels_dir / guild_id / str(thread.parent_id) / str(thread.id)
        thread_dir.mkdir(parents=True, exist_ok=True)

        channel_name = ""
        if isinstance(thread.parent, discord.ForumChannel):
            channel_name = thread.parent.name

        messages = [msg async for msg in thread.history(limit=None, oldest_first=True)]
        logger.info("  %d messages in thread %s", len(messages), thread.name)

        for msg in messages:
            await self.archive_message(msg, thread_dir, session, channel_name, thread.name)

        self._write_thread_index(thread, tree)
        logger.info("  Finished thread: %s", thread.name)

    # ------------------------------------------------------------------
    # Internal: message processing
    # ------------------------------------------------------------------

    async def archive_message(
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
    def check_stale(self) -> dict:
        """Check which pages are stale relative to their source files.

        Returns a dict with keys ``threads``, ``channels``, ``home``, ``site_files``
        — each a list of paths that need rebuilding.
        """
        stale_threads: list[Path] = []
        stale_channels: list[Path] = []
        home_stale = False
        site_stale: list[Path] = []

        # Collect template and bot source mtimes: any code change means all HTML is stale
        template_mtimes: list[float] = []
        src_dirs = [
            _TEMPLATES_DIR,  # Jinja2 templates
            _TEMPLATES_DIR.parent,  # bot/ Python sources
        ]
        for src_dir in src_dirs:
            if src_dir.exists():
                for f in src_dir.rglob("*.j2" if src_dir == _TEMPLATES_DIR else "*.py"):
                    template_mtimes.append(f.stat().st_mtime)

        # Collect site file mtimes (CSS etc.)
        site_dir = _TEMPLATES_DIR.parent.parent / "site"
        site_mtimes: dict[str, float] = {}
        if site_dir.exists():
            for f in site_dir.iterdir():
                if f.is_file():
                    site_mtimes[f.name] = f.stat().st_mtime
                    out_f = self._output / f.name
                    if out_f.exists() and out_f.stat().st_mtime < f.stat().st_mtime:
                        site_stale.append(out_f)
                    elif not out_f.exists():
                        site_stale.append(out_f)

        if not self._channels_dir.exists():
            return {
                "threads": stale_threads,
                "channels": stale_channels,
                "home": False,
                "site_files": site_stale,
            }

        max_template = max(template_mtimes) if template_mtimes else 0

        channel_deps: dict[Path, float] = {}  # path -> max dependency mtime
        home_max_dep = 0.0

        for guild_dir in sorted(self._channels_dir.iterdir()):
            if not guild_dir.is_dir():
                continue
            for ch_dir in sorted(guild_dir.iterdir()):
                if not ch_dir.is_dir():
                    continue
                ch_index = ch_dir / "index.html"
                ch_max_dep = max_template

                for th_dir in sorted(ch_dir.iterdir()):
                    if not th_dir.is_dir():
                        continue
                    th_index = th_dir / "index.html"
                    md_files = sorted(th_dir.glob("*.md"))
                    if not md_files:
                        continue

                    # Thread: check .md files + templates
                    max_md = max(f.stat().st_mtime for f in md_files)
                    th_dep = max(max_md, max_template)

                    if not th_index.exists() or th_index.stat().st_mtime < th_dep:
                        stale_threads.append(th_index)

                    # Track thread mtime for channel dependency
                    if th_index.exists():
                        ch_max_dep = max(ch_max_dep, th_index.stat().st_mtime, max_md)

                # Channel: depends on its thread pages + templates
                if ch_index.exists():
                    if ch_index.stat().st_mtime < ch_max_dep:
                        stale_channels.append(ch_index)
                    home_max_dep = max(home_max_dep, ch_index.stat().st_mtime)
                channel_deps[ch_index] = ch_max_dep

        # Home page
        home_index = self._output / "index.html"
        if home_index.exists() and home_index.stat().st_mtime < home_max_dep:
            home_stale = True

        return {
            "threads": stale_threads,
            "channels": stale_channels,
            "home": home_stale,
            "site_files": site_stale,
        }

    def rebuild_all(self) -> dict:
        """Rebuild all stale HTML pages from disk. Returns same shape as :meth:`check_stale`."""
        result = self.check_stale()

        for th_index in result["threads"]:
            self._render_thread(th_index.parent, self._build_tree(), tags=[])
        for ch_index in result["channels"]:
            self._render_channel(ch_index.parent, self._build_tree())
        if result["home"]:
            self._write_home_index()

        return result

    # ------------------------------------------------------------------
    # Core renderers (path-based, no Discord dependency)
    # ------------------------------------------------------------------

    def _render_thread(self, th_dir: Path, tree: list, *, tags: list[dict]) -> None:
        """Render a single thread page from .md files on disk."""
        from .markdown_renderer import parse_frontmatter

        md_files = sorted(th_dir.glob("*.md"))
        if not md_files:
            return

        channel_id = th_dir.parent.name
        guild_id = th_dir.parent.parent.name
        index_path = th_dir / "index.html"

        msg_data = []
        for md_path in md_files:
            text = md_path.read_text(encoding="utf-8")
            fm = parse_frontmatter(text)
            try:
                body = text.split("---", 2)[2].lstrip("\n")
            except IndexError:
                body = ""

            attachments = []
            for att in fm.get("attachments") or []:
                attachments.append({
                    "filename": att["filename"],
                    "channel_id": channel_id,
                    "id": str(att["id"]),
                    "is_image": att.get("is_image", False),
                    "size": att.get("size", 0),
                })

            msg_data.append({
                "id": fm.get("message_id", md_path.stem),
                "author": fm.get("author", ""),
                "timestamp": fm.get("timestamp", ""),
                "edited": fm.get("edited"),
                "content": self._markdown_convert(body),
                "embeds": self._embeds_from_frontmatter(fm.get("embeds") or []),
                "attachments": attachments,
                "reactions": fm.get("reactions") or [],
            })

        thread_name = self._read_thread_name(th_dir)
        channel_name = self._read_channel_name(th_dir.parent)
        tmpl = self._env.get_template("thread.html.j2")
        html = tmpl.render(
            root=self._root(index_path, self._output),
            tree=tree,
            thread={"id": th_dir.name, "name": thread_name, "tags": tags},
            channel={"id": channel_id, "name": channel_name, "guild_id": guild_id},
            messages=msg_data,
        )
        index_path.write_text(html, encoding="utf-8")

    def _render_channel(self, ch_dir: Path, tree: list) -> None:
        """Render a single channel page from .md files on disk."""
        guild_id = ch_dir.parent.name
        channel_id = ch_dir.name
        channel_name = self._read_channel_name(ch_dir)
        index_path = ch_dir / "index.html"

        threads = []
        for th_dir in sorted(ch_dir.iterdir()):
            if not th_dir.is_dir():
                continue
            md_files = sorted(th_dir.glob("*.md"))
            th_name = self._read_thread_name(th_dir) if md_files else th_dir.name
            meta = self._read_first_message_meta(th_dir) if md_files else {}
            first_image = meta.get("first_image")
            if first_image:
                first_image["channel_id"] = channel_id

            threads.append({
                "id": th_dir.name,
                "name": th_name,
                "folder": th_dir.name,
                "message_count": len(md_files),
                "updated": "",
                "author": meta.get("author", ""),
                "timestamp": meta.get("timestamp", ""),
                "first_image": first_image,
                "tags": [],
            })

        tmpl = self._env.get_template("channel.html.j2")
        html = tmpl.render(
            root=self._root(index_path, self._output),
            tree=tree,
            channel={"id": channel_id, "name": channel_name, "thread_count": len(threads)},
            threads=threads,
            thread_id=None,
        )
        index_path.write_text(html, encoding="utf-8")

        if self._git:
            self._git.mark_changed()

    # ------------------------------------------------------------------
    # Discord-aware wrappers (resolve paths, extract tags from live objects)
    # ------------------------------------------------------------------

    def _write_thread_index(
        self, thread: discord.Thread, tree: list | None = None
    ) -> None:
        """Generate the thread page (index.html) from .md files on disk."""
        guild_id = self._guild_id(thread)
        th_dir = self._channels_dir / guild_id / str(thread.parent_id) / str(thread.id)
        th_dir.mkdir(parents=True, exist_ok=True)
        self._render_thread(th_dir, self._tree_or_build(tree), tags=_extract_tags(thread))

    def _write_channel_index(
        self, channel: discord.ForumChannel, tree: list | None = None,
        all_threads: list[discord.Thread] | None = None,
    ) -> None:
        """Generate the channel page (index.html) listing its threads."""
        guild_id = self._channel_guild_id(channel)
        ch_dir = self._channels_dir / guild_id / str(channel.id)
        ch_dir.mkdir(parents=True, exist_ok=True)

        # Build a lookup for in-memory thread data (tags etc.)
        th_map: dict[int, discord.Thread] = {}
        if all_threads:
            th_map = {t.id: t for t in all_threads}

        threads = []
        for th_dir_inner in sorted(ch_dir.iterdir()):
            if not th_dir_inner.is_dir():
                continue
            thread_id = th_dir_inner.name
            md_files = sorted(th_dir_inner.glob("*.md"))
            thread_name = self._read_thread_name(th_dir_inner) if md_files else thread_id

            meta = self._read_first_message_meta(th_dir_inner) if md_files else {}
            first_image = meta.get("first_image")
            if first_image:
                first_image["channel_id"] = str(channel.id)

            tags = []
            if int(thread_id) in th_map:
                tags = _extract_tags(th_map[int(thread_id)])

            threads.append({
                "id": thread_id,
                "name": thread_name,
                "folder": thread_id,
                "message_count": len(md_files),
                "updated": "",
                "author": meta.get("author", ""),
                "timestamp": meta.get("timestamp", ""),
                "first_image": first_image,
                "tags": tags,
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
            for guild_dir in sorted(self._channels_dir.iterdir()):
                if not guild_dir.is_dir():
                    continue
                guild_id = guild_dir.name
                for ch_dir in sorted(guild_dir.iterdir()):
                    if not ch_dir.is_dir():
                        continue
                    channel_index = ch_dir / "index.html"
                    if not channel_index.exists():
                        continue
                    channel_id = ch_dir.name
                    thread_count = sum(1 for p in ch_dir.iterdir() if p.is_dir())
                    channels.append({
                        "name": self._read_channel_name(ch_dir),
                        "folder": f"channels/{guild_id}/{channel_id}",
                        "thread_count": thread_count,
                    })

        index_path = self._output / "index.html"
        tmpl = self._env.get_template("home.html.j2")
        html = tmpl.render(root=self._root(index_path, self._output), tree=self._tree_or_build(tree), channels=channels)
        index_path.write_text(html, encoding="utf-8")

        if self._git:
            self._git.mark_changed()

    # ------------------------------------------------------------------
    # Static pages (legal, privacy, etc.)
    # ------------------------------------------------------------------

    # Registry: list of {slug, title, template}
    STATIC_PAGES: list[dict] = [
        {"slug": "legal", "title": "Legal", "template": "legal.html.j2"},
    ]

    def write_static_pages(self) -> None:
        """Generate all registered static pages to the output directory."""
        self._output.mkdir(parents=True, exist_ok=True)
        for page in self.STATIC_PAGES:
            slug = page["slug"]
            out_path = self._output / f"{slug}.html"
            tmpl = self._env.get_template(page["template"])
            html = tmpl.render(
                root=self._root(out_path, self._output),
                tree=self._build_tree(),
            )
            out_path.write_text(html, encoding="utf-8")
            logger.debug("Wrote static page: %s", out_path)

    # ------------------------------------------------------------------
    # Internal: helpers
    # ------------------------------------------------------------------


    async def archive_all_from_ids(self, channel_ids: list[int]) -> None:
        """Enumerate all channels first, build full tree, then archive."""
        tree = self._build_tree_from_ids(channel_ids)
        async with self._session_context() as session:
            for cid in channel_ids:
                ch = self._client.get_channel(cid) or await self._client.fetch_channel(cid)
                if not isinstance(ch, discord.ForumChannel):
                    continue
                all_threads = await self._collect_threads(ch)
                for thread in all_threads:
                    await self.archive_thread(thread, session, tree)
                self._write_channel_index(ch, tree, all_threads)
        self._write_home_index(tree)

    @staticmethod
    async def _collect_threads(channel: discord.ForumChannel) -> list[discord.Thread]:
        """Active + archived threads, deduped, preserving order."""
        seen: set[int] = set()
        out: list[discord.Thread] = []
        for thread in channel.threads:
            if thread.id not in seen:
                seen.add(thread.id)
                out.append(thread)
        async for thread in channel.archived_threads(limit=None):
            if thread.id not in seen:
                seen.add(thread.id)
                out.append(thread)
        return out

    @staticmethod
    def _merge_channel_into_tree(
        tree: list[dict], channel, threads: list[discord.Thread]
    ) -> list[dict]:
        """Return `tree` with `channel`'s thread list replaced by `threads` (in-memory).
        Adds the channel node if absent."""
        guild_id = str(channel.guild.id) if channel.guild else "0"
        node = {
            "id": str(channel.id),
            "name": channel.name,
            "folder": f"{guild_id}/{channel.id}",
            "threads": [
                {"id": str(t.id), "name": t.name, "folder": f"{guild_id}/{channel.id}/{t.id}"}
                for t in threads
            ],
        }
        out = []
        replaced = False
        for existing in tree:
            if existing.get("id") == node["id"]:
                out.append(node)
                replaced = True
            else:
                out.append(existing)
        if not replaced:
            out.append(node)
        return out

    def _build_tree_from_ids(self, channel_ids: list[int]) -> list[dict]:
        """Build complete tree from Discord objects (before writing to disk)."""
        tree = []
        for cid in channel_ids:
            ch = self._client.get_channel(cid)
            if ch is None or not hasattr(ch, "threads"):
                continue
            guild_id = str(ch.guild.id) if ch.guild else "0"
            threads = [{"id": str(t.id), "name": t.name, "folder": f"{guild_id}/{cid}/{t.id}"}
                       for t in ch.threads]
            tree.append({"id": str(cid), "name": ch.name, "folder": f"{guild_id}/{cid}", "threads": threads})
        return tree

    @staticmethod
    def _embeds_from_frontmatter(embeds: list[dict]) -> list[dict]:
        """Convert embed data from frontmatter to template-ready format."""
        result = []
        for e in embeds:
            color = e.get("color")
            if isinstance(color, int):
                color = f"#{color:06x}"
            result.append({**e, "color": color})
        return result

    def _build_tree(self) -> list[dict]:
        """Build full channel/thread tree for the unified sidebar."""
        channels = []
        if not self._channels_dir.exists():
            return channels
        for guild_dir in sorted(self._channels_dir.iterdir()):
            if not guild_dir.is_dir():
                continue
            guild_id = guild_dir.name
            for ch_dir in sorted(guild_dir.iterdir()):
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
                    threads.append({"id": th_id, "name": th_name, "folder": f"{guild_id}/{ch_id}/{th_id}"})
                channels.append({"id": ch_id, "name": ch_name, "folder": f"{guild_id}/{ch_id}", "threads": threads})
        return channels

    @staticmethod
    def _read_channel_name(ch_dir: Path) -> str:
        """Read channel name from any thread's .md frontmatter, then fallback to HTML."""
        for th_dir in sorted(ch_dir.iterdir()):
            if th_dir.is_dir():
                for md in sorted(th_dir.glob("*.md")):
                    name = _read_frontmatter(md).get("channel_name")
                    if name:
                        return str(name)
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
        for md in sorted(th_dir.glob("*.md")):
            name = _read_frontmatter(md).get("thread_name")
            if name:
                return str(name)
        return th_dir.name

    @staticmethod
    def _read_first_message_meta(th_dir: Path) -> dict:
        """Read author, timestamp, and first image attachment info from the earliest .md frontmatter."""
        md_files = sorted(th_dir.glob("*.md"))
        if not md_files:
            return {}
        fm = _read_frontmatter(md_files[0])
        first_image = None
        attachments = fm.get("attachments") or []
        for att in attachments:
            if att.get("is_image"):
                first_image = {
                    "id": str(att["id"]),
                    "filename": att["filename"],
                }
                break
        return {
            "author": fm.get("author", ""),
            "timestamp": fm.get("timestamp", ""),
            "first_image": first_image,
        }
