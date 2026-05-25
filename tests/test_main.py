"""Tests for the ArboristClient slash command wiring."""

from unittest.mock import Mock

import discord
from discord import app_commands

from bot.main import _make_archive_command


def test_archive_command_requires_manage_guild():
    """`/archive` is gated behind manage_guild — a regular member can't trigger a full re-archive."""
    cmd = _make_archive_command(archiver=Mock(), channel_ids=["1", "2"])
    assert isinstance(cmd, app_commands.Command)
    # default_member_permissions is set via @app_commands.default_permissions(manage_guild=True)
    perms = cmd.default_permissions
    assert perms is not None
    assert perms.manage_guild is True
    assert cmd.guild_only is True
