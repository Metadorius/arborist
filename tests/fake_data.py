"""Shared fake data + helper for generating a fake archive site."""
import asyncio
import shutil
import urllib.request
from pathlib import Path
from unittest.mock import patch

from bot.archiver import Archiver


# ---------------------------------------------------------------------------
# Fake discord.py objects
# ---------------------------------------------------------------------------

class FakeUser:
    def __init__(self, id: int, name: str):
        self.id = id
        self.name = name
    def __str__(self) -> str: return self.name
    @property
    def display_avatar(self) -> None: return None


class FakeAttachment:
    def __init__(self, id: int, filename: str, size: int = 5000, content_type: str = "image/png"):
        self.id = id
        self.filename = filename
        self.size = size
        self.url = f"https://cdn.discordapp.com/attachments/1/{id}/{filename}"
        self.content_type = content_type


class FakeField:
    def __init__(self, name: str, value: str, inline: bool = False):
        self.name = name
        self.value = value
        self.inline = inline


class FakeEmbed:
    def __init__(self, title=None, description=None, url=None, color=None,
                 fields=None, image=None, thumbnail=None):
        self.title = title
        self.description = description
        self.url = url
        self.color = type("Color", (), {"value": 0x4ade80})() if color else type("Color", (), {"value": None})()
        self.fields = fields or []
        class Img: url = "https://cdn.discordapp.com/embed/example.png"
        self.image = Img() if image else None
        self.thumbnail = Img() if thumbnail else None


class FakeReaction:
    def __init__(self, emoji: str, count: int = 1):
        self.emoji = type("E", (), {"__str__": lambda s: emoji})()
        self.count = count


import datetime as _dt
def _utc(*a):
    return _dt.datetime(*a, tzinfo=_dt.timezone.utc)


class FakeMessage:
    def __init__(self, id: int, content: str, channel, author: FakeUser,
                 attachments=None, embeds=None, reactions=None,
                 created_at=None, edited_at=None):
        self.id = id
        self.content = content
        self.channel = channel
        self.author = author
        self.attachments = attachments or []
        self.embeds = embeds or []
        self.reactions = reactions or []
        self.created_at = created_at or _utc(2026, 5, 24, 12, 0)
        self.edited_at = edited_at
        self.pinned = False
        self.jump_url = f"https://discord.com/channels/1/{channel.id}/{id}"


class FakeThread:
    def __init__(self, id: int, name: str, parent_id: int, parent, messages: list):
        self.id = id
        self.name = name
        self.parent_id = parent_id
        self.parent = parent
        self._messages = messages
    def history(self, limit=None, oldest_first=True):
        async def _gen():
            for m in self._messages:
                yield m
        return _gen()


class FakeChannel:
    def __init__(self, id: int, name: str, threads=None):
        self.id = id
        self.name = name
        self._threads = threads or []
        self._archived = []
    @property
    def threads(self): return self._threads
    def archived_threads(self, limit=None):
        async def _gen():
            for t in self._archived:
                yield t
        return _gen()


class FakeClient:
    def __init__(self, channels: dict):
        self._channels = channels
    def get_channel(self, cid): return self._channels.get(cid)
    async def fetch_channel(self, cid): return self._channels.get(cid)


# ---------------------------------------------------------------------------
# Data builder
# ---------------------------------------------------------------------------

def build_fake_data():
    """Build and return (FakeClient, channels_dict)."""
    alice = FakeUser(100, "Alice")
    bob = FakeUser(101, "BobBot")
    charlie = FakeUser(102, "Charlie")

    ch_assets = FakeChannel(111, "assets")
    ch_tuts = FakeChannel(222, "tutorials")
    ch_show = FakeChannel(333, "show-and-tell")

    thread_assets = FakeThread(10001, "Cool Asset Pack v2", 111, ch_assets, [])
    thread_assets_pbr = FakeThread(10002, "Free PBR Materials Pack", 111, ch_assets, [])
    thread_assets_naming = FakeThread(10003, "Question: best asset naming convention?", 111, ch_assets, [])
    thread_assets_village = FakeThread(10004, "WIP: medieval village kit", 111, ch_assets, [])

    thread_tuts = FakeThread(20001, "Blender Basics -- Intermediate", 222, ch_tuts, [])
    thread_tuts_rig = FakeThread(20002, "Rigging tutorial: skeleton setup", 222, ch_tuts, [])
    thread_tuts_sp = FakeThread(20003, "Substance Painter for beginners", 222, ch_tuts, [])

    thread_show = FakeThread(30001, "Procedural Texture Experiment", 333, ch_show, [])
    thread_show_dragon = FakeThread(30002, "Sculpting practice: dragon head", 333, ch_show, [])
    thread_show_anim = FakeThread(30003, "Animated character demo", 333, ch_show, [])
    thread_show_scene = FakeThread(30004, "First completed scene!", 333, ch_show, [])
    thread_show_light = FakeThread(30005, "Lighting study collection", 333, ch_show, [])

    # --- assets ---
    assets_msg1 = FakeMessage(1001,
        "Hey everyone! I just released **Cool Asset Pack v2**!\n\n"
        "This pack includes:\n- 50 high-res textures\n- 10 3D models\n- 5 sound effects\n\n"
        "Check the attachment below!",
        thread_assets, alice,
        attachments=[FakeAttachment(9001, "preview.png"),
                     FakeAttachment(9002, "asset-pack-v2.zip", size=50000000, content_type="application/zip")],
        reactions=[FakeReaction("🔥", 12), FakeReaction("👍", 8), FakeReaction("🎉", 3)],
        created_at=_utc(2026, 5, 20, 8, 0))
    assets_msg2 = FakeMessage(1002,
        "Updated the download link. Here's the new one:\n\n<@101> can you pin this?",
        thread_assets, alice,
        edited_at=_utc(2026, 5, 20, 9, 15),
        created_at=_utc(2026, 5, 20, 9, 0))
    assets_msg3 = FakeMessage(1003,
        "Here's a code snippet for using the textures:\n\n```python\nfrom assets import TextureLoader\n\n"
        "loader = TextureLoader(\"pack_v2\")\ntexture = loader.load(\"brick_wall\")\n"
        "print(f\"Loaded {texture.name} ({texture.width}x{texture.height})\")\n"
        "```\n\nLet me know if you have ||any questions||!",
        thread_assets, bob,
        reactions=[FakeReaction("❤️", 5)],
        created_at=_utc(2026, 5, 20, 10, 30))
    assets_msg4 = FakeMessage(1004,
        "This looks great! <@100> Amazing work on the **normal maps** \U0001f44f",
        thread_assets, charlie,
        created_at=_utc(2026, 5, 21, 14, 0))
    assets_msg5 = FakeMessage(1005,
        "Here's a quick preview:\n\n-# Small disclaimer: these are still WIP\n\n"
        "> The final pack will include PBR materials\n\nhttps://example.com/docs",
        thread_assets, alice,
        embeds=[FakeEmbed(title="Cool Asset Pack v2 -- Preview",
                          description="Check out the new textures and models in this preview render.",
                          color=True, image=True)],
        attachments=[FakeAttachment(9003, "render.webp", content_type="image/webp")],
        reactions=[FakeReaction("⭐", 2)],
        created_at=_utc(2026, 5, 21, 15, 0))
    thread_assets._messages = [assets_msg1, assets_msg2, assets_msg3, assets_msg4, assets_msg5]

    # --- tutorials ---
    tut_msg1 = FakeMessage(2001,
        "# Blender Basics: Intermediate Guide\n\n## What you'll learn\n\n"
        "- **Retopology** techniques\n- UV *unwrapping* best practices\n"
        "- ~~Outdated~~ methods to avoid\n\n---\n\n### Retopology\n\n```\n"
        "1. Start with a high-poly mesh\n2. Create a low-poly cage\n"
        "3. Use Shrinkwrap modifier\n4. Relax the result\n```\n\n"
        "||spoiler: the answer is always edge loops||",
        thread_tuts, bob,
        embeds=[FakeEmbed(title="Video Tutorial",
                          description="Watch the full guide on YouTube",
                          url="https://youtube.com/watch?v=example", color=True)],
        reactions=[FakeReaction("📚", 7), FakeReaction("💡", 4)],
        created_at=_utc(2026, 5, 18, 10, 0))
    tut_msg2 = FakeMessage(2002,
        "Great tutorial! The retopology section helped a lot <@101>\n\nHere's my result:\n<:blender_logo:555>",
        thread_tuts, alice,
        attachments=[FakeAttachment(9004, "my_result.png")],
        created_at=_utc(2026, 5, 18, 16, 30))
    thread_tuts._messages = [tut_msg1, tut_msg2]

    # --- show-and-tell ---
    show_msg1 = FakeMessage(3001,
        "Check out this **procedural texture** I made!\n\n<@100> <@102> what do you think?",
        thread_show, charlie,
        attachments=[FakeAttachment(9005, "procedural_demo.mp4", content_type="video/mp4")],
        reactions=[FakeReaction("😍", 15), FakeReaction("👍", 6)],
        created_at=_utc(2026, 5, 23, 20, 0))
    show_msg2 = FakeMessage(3002,
        "Here's a **gallery** of the latest renders from the project 🎨",
        thread_show, charlie,
        attachments=[
            FakeAttachment(9301, "render_01.jpg", content_type="image/jpeg"),
            FakeAttachment(9302, "render_02.jpg", content_type="image/jpeg"),
            FakeAttachment(9303, "render_03.jpg", content_type="image/jpeg"),
            FakeAttachment(9304, "render_04.jpg", content_type="image/jpeg"),
        ],
        reactions=[FakeReaction("🖼️", 8), FakeReaction("🔥", 5)],
        created_at=_utc(2026, 5, 24, 9, 0))
    thread_show._messages = [show_msg1, show_msg2]

    # --- extra threads (short, to showcase the sidebar tree) ---
    thread_assets_pbr._messages = [FakeMessage(1101,
        "Dropping a free **PBR materials pack** -- 20 surfaces, 2K textures, CC0.",
        thread_assets_pbr, bob,
        attachments=[FakeAttachment(9101, "pbr_pack.zip", size=80000000, content_type="application/zip")],
        reactions=[FakeReaction("🙏", 9)],
        created_at=_utc(2026, 5, 19, 11, 0))]
    thread_assets_naming._messages = [FakeMessage(1201,
        "What naming convention do you use? `snake_case`, `PascalCase`, prefix-by-type?",
        thread_assets_naming, charlie,
        reactions=[FakeReaction("🤔", 4)],
        created_at=_utc(2026, 5, 22, 9, 30))]
    thread_assets_village._messages = [FakeMessage(1301,
        "Early WIP of a **medieval village kit** -- modular walls, roofs, props.",
        thread_assets_village, alice,
        attachments=[FakeAttachment(9102, "village_wip.png")],
        created_at=_utc(2026, 5, 23, 17, 0))]

    thread_tuts_rig._messages = [FakeMessage(2101,
        "Step-by-step **skeleton setup** for humanoid rigs. Covers IK, constraints, weight painting.",
        thread_tuts_rig, bob,
        reactions=[FakeReaction("📚", 6)],
        created_at=_utc(2026, 5, 17, 14, 0))]
    thread_tuts_sp._messages = [FakeMessage(2201,
        "**Substance Painter** quickstart: smart materials, layer masks, exporting to glTF.",
        thread_tuts_sp, bob,
        created_at=_utc(2026, 5, 19, 13, 0))]

    thread_show_dragon._messages = [FakeMessage(3101,
        "Some sculpting practice -- **dragon head** in ZBrush.",
        thread_show_dragon, alice,
        attachments=[FakeAttachment(9201, "dragon_head.png")],
        reactions=[FakeReaction("🐉", 11), FakeReaction("🔥", 4)],
        created_at=_utc(2026, 5, 22, 19, 0))]
    thread_show_anim._messages = [FakeMessage(3201,
        "Short **animated demo** of a character I've been working on.",
        thread_show_anim, charlie,
        attachments=[FakeAttachment(9202, "anim_demo.mp4", content_type="video/mp4")],
        reactions=[FakeReaction("🎬", 8)],
        created_at=_utc(2026, 5, 23, 12, 0))]
    thread_show_scene._messages = [FakeMessage(3301,
        "My **first completed scene**! Took two months but I'm happy with the result.",
        thread_show_scene, alice,
        attachments=[FakeAttachment(9203, "first_scene.png")],
        reactions=[FakeReaction("🎉", 14), FakeReaction("❤️", 7)],
        created_at=_utc(2026, 5, 24, 10, 0))]
    thread_show_light._messages = [FakeMessage(3401,
        "Collection of **lighting studies** -- HDRI, three-point, dramatic side-light.",
        thread_show_light, bob,
        attachments=[FakeAttachment(9204, "lighting_studies.png")],
        created_at=_utc(2026, 5, 24, 16, 0))]

    ch_assets._threads = [thread_assets, thread_assets_pbr, thread_assets_naming, thread_assets_village]
    ch_tuts._threads = [thread_tuts, thread_tuts_rig, thread_tuts_sp]
    ch_show._threads = [thread_show, thread_show_dragon, thread_show_anim, thread_show_scene, thread_show_light]

    channels = {111: ch_assets, 222: ch_tuts, 333: ch_show}
    return FakeClient(channels), channels


# ---------------------------------------------------------------------------
# Generate a fake archive site
# ---------------------------------------------------------------------------

def _download_placeholder_images(output_dir: Path):
    """Download random picsum images into the expected attachment directories.

    Images are cached to ``tests/.cache/test-images/`` so they are only
    downloaded once per picsum ID, then copied into place.

    All placeholder images courtesy of `Lorem Picsum <https://picsum.photos>`_.
    """
    _cache = Path(__file__).resolve().parent / ".cache" / "test-images"
    _cache.mkdir(parents=True, exist_ok=True)

    # write attribution notice
    _attribution = _cache / "ATTRIBUTION.txt"
    if not _attribution.exists():
        _attribution.write_text(
            "These placeholder images come from Lorem Picsum (https://picsum.photos).\n"
            "They are cached here to avoid re-downloading during test runs.\n",
            encoding="utf-8",
        )

    # (channel_id, attachment_id, filename, picsum_id)
    mappings = [
        (111, 9001, "preview.png",        237),
        (111, 9003, "render.webp",        42),
        (111, 9102, "village_wip.png",    1015),
        (222, 9004, "my_result.png",      180),
        (333, 9005, "procedural_demo.mp4", None),  # skip video
        (333, 9201, "dragon_head.png",    220),
        (333, 9203, "first_scene.png",    250),
        (333, 9204, "lighting_studies.png", 20),
        (333, 9301, "render_01.jpg",      10),
        (333, 9302, "render_02.jpg",      11),
        (333, 9303, "render_03.jpg",      12),
        (333, 9304, "render_04.jpg",      13),
    ]
    for ch_id, att_id, filename, pic_id in mappings:
        if pic_id is None:
            continue
        dest_dir = output_dir / "attachments" / str(ch_id) / str(att_id)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / filename
        if dest.exists():
            continue

        cached = _cache / f"{pic_id}.jpg"
        if not cached.exists():
            url = f"https://picsum.photos/id/{pic_id}/800/600"
            try:
                urllib.request.urlretrieve(url, str(cached))
            except Exception:
                continue  # offline — skip, dest won't exist

        if cached.exists():
            shutil.copy2(cached, str(dest))

def generate_fake_site(output_dir: Path, copy_css: bool = True):
    """Run the archiver with fake data into output_dir."""
    import builtins
    import bot.archiver as archiver_mod

    orig = builtins.isinstance

    def _wrap(obj, cls):
        if cls is archiver_mod.discord.ForumChannel and hasattr(obj, "threads"):
            return True
        return orig(obj, cls)

    builtins.isinstance = _wrap

    try:
        client = build_fake_data()[0]
        with patch("bot.archiver.download_all_attachments", return_value=[]):
            archiver = Archiver(client, output_dir)
            asyncio.run(archiver.archive_all_from_ids(list(client._channels.keys())))
    finally:
        builtins.isinstance = orig

    _download_placeholder_images(output_dir)

    if copy_css:
        css = Path(__file__).resolve().parent.parent / "site" / "styles.css"
        if css.exists():
            shutil.copy2(css, output_dir / "styles.css")
