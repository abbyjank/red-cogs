"""Unit and integration tests for EphemeralVents cog."""

import asyncio
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import discord
from redbot.core import Config, data_manager

from ephemeralvents.constants import (
    CLOSE_BUTTON_ID,
    CONFIG_IDENTIFIER,
    DEFAULT_ARCHIVE_EMOJI,
    DEFAULT_CRISIS_HEADER,
    DEFAULT_GUILD,
    DEFAULT_INTENTS,
    DELETE_BUTTON_ID,
    LAUNCHER_BUTTON_ID,
    MAX_TOPIC_LENGTH,
)
from ephemeralvents.ephemeralvents import (
    EphemeralVents,
    format_archived_channel_name,
    sanitize_channel_name,
)
from ephemeralvents.views import (
    ArchivedVentView,
    CloseVentView,
    IntentSelect,
    IntentSelectView,
    VentLauncherView,
    VentTopicModal,
)


def setUpModule():
    """Setup temporary Red data manager for unit testing."""
    data_manager.create_temp_config()
    data_manager.load_basic_configuration("temporary_red")



class TestConstantsAndNaming(unittest.TestCase):
    """Test constants, default schema, and channel name sanitization."""

    def test_default_schema(self):
        """Verify DEFAULT_GUILD schema contains all required fields."""
        required_fields = [
            "hub_channel_id",
            "mod_role_id",
            "archive_category_id",
            "archive_emoji",
            "inactivity_timeout",
            "hard_cap_timeout",
            "post_action",
            "crisis_header",
            "active_vents",
            "intents",
        ]
        for field in required_fields:
            self.assertIn(field, DEFAULT_GUILD, f"Missing {field} in DEFAULT_GUILD")

        self.assertEqual(DEFAULT_GUILD["inactivity_timeout"], 12.0)
        self.assertEqual(DEFAULT_GUILD["hard_cap_timeout"], 24.0)
        self.assertEqual(DEFAULT_GUILD["post_action"], "archive")
        self.assertEqual(DEFAULT_GUILD["archive_emoji"], DEFAULT_ARCHIVE_EMOJI)
        self.assertIsNone(DEFAULT_GUILD["archive_category_id"])

    def test_default_intents(self):
        """Verify the 5 default emoji intents and their fields."""
        expected_slugs = ["advice", "comfort", "relate", "gentle", "open"]
        for slug in expected_slugs:
            self.assertIn(slug, DEFAULT_INTENTS)
            intent = DEFAULT_INTENTS[slug]
            self.assertIn("emoji", intent)
            self.assertIn("label", intent)
            self.assertIn("description", intent)
            self.assertIn("header_note", intent)

        self.assertEqual(DEFAULT_INTENTS["advice"]["emoji"], "🟠")
        self.assertEqual(DEFAULT_INTENTS["comfort"]["emoji"], "🟡")
        self.assertEqual(DEFAULT_INTENTS["relate"]["emoji"], "🟢")
        self.assertEqual(DEFAULT_INTENTS["gentle"]["emoji"], "🔵")
        self.assertEqual(DEFAULT_INTENTS["open"]["emoji"], "🟣")

    def test_button_custom_ids(self):
        """Verify persistent button custom IDs are defined and unique."""
        ids = [LAUNCHER_BUTTON_ID, CLOSE_BUTTON_ID, DELETE_BUTTON_ID]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(MAX_TOPIC_LENGTH, 30)

    def test_sanitize_channel_name_topic(self):
        """Verify sanitization when a topic is provided."""
        self.assertEqual(
            sanitize_channel_name("🟡", "rough day", "abby"),
            "vent-🟡-rough-day",
        )
        self.assertEqual(
            sanitize_channel_name("🟡", "Rough Day!", "abby"),
            "vent-🟡-rough-day",
        )
        self.assertEqual(
            sanitize_channel_name("🟡", "Need--to__talk!!", "abby"),
            "vent-🟡-need-to-talk",
        )

    def test_sanitize_channel_name_fallback(self):
        """Verify fallback to author name when topic is omitted or stripped."""
        self.assertEqual(
            sanitize_channel_name("🟡", None, "Abby"),
            "vent-🟡-abby",
        )
        self.assertEqual(
            sanitize_channel_name("🟡", "", "Abby_Jank"),
            "vent-🟡-abby-jank",
        )
        self.assertEqual(
            sanitize_channel_name("🟡", "   ", "Abby"),
            "vent-🟡-abby",
        )
        # Fallback when topic and author are both special chars
        self.assertEqual(
            sanitize_channel_name("🟡", "!@#$", "%^&*"),
            "vent-🟡-vent",
        )

    def test_sanitize_channel_name_length_limit(self):
        """Verify channel name does not exceed 100 characters and ends cleanly."""
        long_topic = "a" * 120
        name = sanitize_channel_name("🟠", long_topic, "user")
        self.assertLessEqual(len(name), 100)
        self.assertFalse(name.endswith("-"))
        self.assertTrue(name.startswith("vent-🟠-"))

    def test_sanitize_custom_emoji(self):
        """Verify custom emoji name extraction."""
        name = sanitize_channel_name("<:heart:123456789>", "sadness", "user")
        self.assertEqual(name, "vent-heart-sadness")

    def test_format_archived_channel_name(self):
        """Verify channel renaming when archived."""
        # Standard colour emoji prefix
        self.assertEqual(
            format_archived_channel_name("vent-🟡-abby"),
            "📦-abby",
        )
        self.assertEqual(
            format_archived_channel_name("vent-🟠-rough-day"),
            "📦-rough-day",
        )
        # Custom emoji prefix
        self.assertEqual(
            format_archived_channel_name("vent-heart-sadness"),
            "📦-sadness",
        )
        # Simple vent-prefix with single hyphen
        self.assertEqual(
            format_archived_channel_name("vent-abby"),
            "📦-abby",
        )
        # Channel not matching vent-prefix
        self.assertEqual(
            format_archived_channel_name("general-chat"),
            "📦-general-chat",
        )
        # Custom archive emoji
        self.assertEqual(
            format_archived_channel_name("vent-🟡-abby", archive_emoji="📁"),
            "📁-abby",
        )
        # Custom emoji as archive emoji
        self.assertEqual(
            format_archived_channel_name("vent-🟡-abby", archive_emoji="<:box:1234567>"),
            "box-abby",
        )
        # Already archived channel should not re-prefix
        self.assertEqual(
            format_archived_channel_name("📦-abby"),
            "📦-abby",
        )
        # Channel name length capped at 100
        long_name = "vent-🟡-" + ("a" * 150)
        archived_long = format_archived_channel_name(long_name)
        self.assertLessEqual(len(archived_long), 100)
        self.assertTrue(archived_long.startswith("📦-"))
        self.assertFalse(archived_long.endswith("-"))


class TestViewsAndModals(unittest.TestCase):
    """Test persistent UI views and dynamic components."""

    def setUp(self):
        self.bot = MagicMock()
        self.cog = EphemeralVents(self.bot)

    def test_views_are_persistent(self):
        """Verify persistent views have timeout=None and persistent custom_ids."""
        launcher_view = VentLauncherView(self.cog)
        self.assertIsNone(launcher_view.timeout)
        launcher_buttons = [c for c in launcher_view.children if isinstance(c, discord.ui.Button)]
        self.assertTrue(any(b.custom_id == LAUNCHER_BUTTON_ID for b in launcher_buttons))

        close_view = CloseVentView(self.cog)
        self.assertIsNone(close_view.timeout)
        close_buttons = [c for c in close_view.children if isinstance(c, discord.ui.Button)]
        self.assertTrue(any(b.custom_id == CLOSE_BUTTON_ID for b in close_buttons))

        archived_view = ArchivedVentView(self.cog)
        self.assertIsNone(archived_view.timeout)
        archived_buttons = [c for c in archived_view.children if isinstance(c, discord.ui.Button)]
        self.assertTrue(any(b.custom_id == DELETE_BUTTON_ID for b in archived_buttons))

    def test_modal_fields(self):
        """Verify VentTopicModal text input field properties."""
        modal = VentTopicModal(self.cog)
        self.assertEqual(modal.topic_input.max_length, 30)
        self.assertFalse(modal.topic_input.required)

    def test_intent_select_options(self):
        """Verify dynamic select menu options are created from guild intents."""
        select = IntentSelect(self.cog, topic="Test Topic", intents=DEFAULT_INTENTS)
        self.assertEqual(len(select.options), 5)
        values = [opt.value for opt in select.options]
        self.assertEqual(values, ["advice", "comfort", "relate", "gentle", "open"])


class TestCogLogic(unittest.IsolatedAsyncioTestCase):
    """Async tests for rate limiting, permissions, and lifecycle processing."""

    async def asyncSetUp(self):
        self.bot = MagicMock()
        self.bot.is_owner = AsyncMock(return_value=False)
        self.bot.is_admin = AsyncMock(return_value=False)
        self.bot.is_mod = AsyncMock(return_value=False)

        # Mock Red Config
        self.cog = EphemeralVents(self.bot)
        self.guild = MagicMock(spec=discord.Guild)
        self.guild.id = 123456789
        self.guild.default_role = MagicMock(spec=discord.Role)
        self.guild.me = MagicMock(spec=discord.Member)
        await self.cog.config.clear_all_guilds()

    async def test_rate_limit_no_active(self):
        """User with no active vents should not be rate-limited."""
        user = MagicMock(spec=discord.Member)
        user.id = 999

        has_active, ch = await self.cog.check_user_vent_rate_limit(self.guild, user)
        self.assertFalse(has_active)
        self.assertIsNone(ch)

    async def test_rate_limit_with_active(self):
        """User with an active existing vent should be rate-limited."""
        user = MagicMock(spec=discord.Member)
        user.id = 999

        channel = MagicMock(spec=discord.TextChannel)
        channel.id = 555
        self.guild.get_channel.return_value = channel

        # Inject into config
        async with self.cog.config.guild(self.guild).active_vents() as vents:
            vents["555"] = {
                "author_id": 999,
                "intent_key": "advice",
                "created_at": time.time(),
                "last_active_at": time.time(),
                "is_locked": False,
                "locked_at": None,
            }

        has_active, existing_ch = await self.cog.check_user_vent_rate_limit(self.guild, user)
        self.assertTrue(has_active)
        self.assertEqual(existing_ch, channel)

    async def test_rate_limit_prunes_stale_deleted_channel(self):
        """If tracked channel is deleted in Discord, check_user_vent_rate_limit cleans it up."""
        user = MagicMock(spec=discord.Member)
        user.id = 999

        # Channel not found in Discord
        self.guild.get_channel.return_value = None
        self.bot.fetch_channel = AsyncMock(side_effect=discord.NotFound(MagicMock(), "Not found"))

        async with self.cog.config.guild(self.guild).active_vents() as vents:
            vents["555"] = {
                "author_id": 999,
                "intent_key": "advice",
                "created_at": time.time(),
                "last_active_at": time.time(),
                "is_locked": False,
                "locked_at": None,
            }

        has_active, existing_ch = await self.cog.check_user_vent_rate_limit(self.guild, user)
        self.assertFalse(has_active)
        self.assertIsNone(existing_ch)

        # Config should be pruned
        vents_after = await self.cog.config.guild(self.guild).active_vents()
        self.assertNotIn("555", vents_after)

    async def test_can_close_vent_author(self):
        """Author can close their own vent channel."""
        channel = MagicMock(spec=discord.TextChannel)
        channel.id = 777
        member = MagicMock(spec=discord.Member)
        member.id = 888
        member.guild_permissions.administrator = False
        member.guild_permissions.manage_channels = False
        member.get_role.return_value = None

        async with self.cog.config.guild(self.guild).active_vents() as vents:
            vents["777"] = {"author_id": 888}

        can_close = await self.cog.can_close_vent(self.guild, member, channel)
        self.assertTrue(can_close)

    async def test_can_close_vent_unauthorized_member(self):
        """Random member cannot close someone else's vent."""
        channel = MagicMock(spec=discord.TextChannel)
        channel.id = 777
        channel.permissions_for.return_value.manage_channels = False
        member = MagicMock(spec=discord.Member)
        member.id = 111  # Not author
        member.guild_permissions.administrator = False
        member.guild_permissions.manage_channels = False
        member.get_role.return_value = None

        async with self.cog.config.guild(self.guild).active_vents() as vents:
            vents["777"] = {"author_id": 888}

        can_close = await self.cog.can_close_vent(self.guild, member, channel)
        self.assertFalse(can_close)

    async def test_can_moderate_with_mod_role(self):
        """Member with configured mod_role_id can moderate vents."""
        member = MagicMock(spec=discord.Member)
        member.id = 222
        member.guild_permissions.administrator = False
        member.guild_permissions.manage_channels = False

        mod_role = MagicMock(spec=discord.Role)
        mod_role.id = 333
        member.get_role.side_effect = lambda rid: mod_role if rid == 333 else None

        await self.cog.config.guild(self.guild).mod_role_id.set(333)

        can_mod = await self.cog.can_moderate_vent(self.guild, member)
        self.assertTrue(can_mod)

    async def test_lifecycle_inactivity_lock(self):
        """Periodic loop triggers inactivity lock when inactivity_timeout is exceeded."""
        channel = MagicMock(spec=discord.TextChannel)
        channel.id = 500
        channel.guild = self.guild
        channel.set_permissions = AsyncMock()
        channel.send = AsyncMock()
        channel.overwrites_for.return_value = discord.PermissionOverwrite()
        self.guild.get_channel.return_value = channel

        now = 1000000.0
        # Inactivity timeout is 12 hours = 43200 seconds. Last active was 13 hours ago.
        async with self.cog.config.guild(self.guild).active_vents() as vents:
            vents["500"] = {
                "author_id": 123,
                "intent_key": "advice",
                "created_at": now - 50000,
                "last_active_at": now - 47000,
                "is_locked": False,
                "locked_at": None,
            }

        await self.cog._process_guild_lifecycle(self.guild, now)

        channel.set_permissions.assert_awaited()
        channel.send.assert_awaited()

        # Config should be updated with is_locked=True and locked_at
        vents_after = await self.cog.config.guild(self.guild).active_vents()
        self.assertTrue(vents_after["500"]["is_locked"])
        self.assertEqual(vents_after["500"]["locked_at"], now)

    async def test_lifecycle_hard_cap_archive(self):
        """Periodic loop archives channel when hard_cap_timeout is reached and post_action is archive."""
        channel = MagicMock(spec=discord.TextChannel)
        channel.id = 600
        channel.name = "vent-🟠-sadness"
        channel.guild = self.guild
        channel.set_permissions = AsyncMock()
        channel.send = AsyncMock()
        channel.edit = AsyncMock()
        channel.overwrites_for.return_value = discord.PermissionOverwrite()
        self.guild.get_channel.return_value = channel

        now = 1000000.0
        # Hard cap is 24 hours = 86400 seconds. Locked 25 hours ago.
        async with self.cog.config.guild(self.guild).active_vents() as vents:
            vents["600"] = {
                "author_id": 123,
                "intent_key": "advice",
                "created_at": now - 150000,
                "last_active_at": now - 100000,
                "is_locked": True,
                "locked_at": now - 90000,
            }

        await self.cog.config.guild(self.guild).post_action.set("archive")
        await self.cog._process_guild_lifecycle(self.guild, now)

        # Overwrites should restrict @everyone
        channel.set_permissions.assert_awaited()
        # Channel should be renamed with archive prefix
        channel.edit.assert_awaited()
        self.assertEqual(channel.edit.await_args.kwargs["name"], "📦-sadness")
        # Notice with ArchivedVentView should be sent
        channel.send.assert_awaited()

        # Channel should be removed from active_vents
        vents_after = await self.cog.config.guild(self.guild).active_vents()
        self.assertNotIn("600", vents_after)

    async def test_lifecycle_hard_cap_delete(self):
        """Periodic loop deletes channel when hard_cap_timeout is reached and post_action is delete."""
        channel = MagicMock(spec=discord.TextChannel)
        channel.id = 700
        channel.guild = self.guild
        channel.delete = AsyncMock()
        self.guild.get_channel.return_value = channel

        now = 1000000.0
        async with self.cog.config.guild(self.guild).active_vents() as vents:
            vents["700"] = {
                "author_id": 123,
                "intent_key": "advice",
                "created_at": now - 150000,
                "last_active_at": now - 100000,
                "is_locked": True,
                "locked_at": now - 90000,
            }

        await self.cog.config.guild(self.guild).post_action.set("delete")
        await self.cog._process_guild_lifecycle(self.guild, now)

        channel.delete.assert_awaited()
        vents_after = await self.cog.config.guild(self.guild).active_vents()
        self.assertNotIn("700", vents_after)

    async def test_create_vent_channel(self):
        """Test full create_vent_channel flow."""
        author = MagicMock(spec=discord.Member)
        author.id = 444
        author.display_name = "Alex"
        author.mention = "<@444>"

        category = MagicMock(spec=discord.CategoryChannel)
        category.overwrites = {}

        hub_channel = MagicMock(spec=discord.TextChannel)
        hub_channel.category = category
        self.guild.get_channel.return_value = hub_channel

        created_channel = MagicMock(spec=discord.TextChannel)
        created_channel.id = 8888
        created_channel.send = AsyncMock()
        created_channel.history = MagicMock()

        # Mock pin message
        pin_msg = MagicMock()
        pin_msg.pin = AsyncMock()
        created_channel.send.return_value = pin_msg

        async def empty_history(*args, **kwargs):
            if False:
                yield None

        created_channel.history.return_value = empty_history()

        self.guild.create_text_channel = AsyncMock(return_value=created_channel)

        await self.cog.config.guild(self.guild).hub_channel_id.set(1234)

        result = await self.cog.create_vent_channel(
            guild=self.guild,
            author=author,
            intent_key="comfort",
            topic="Rough Day",
        )

        self.assertEqual(result, created_channel)
        self.guild.create_text_channel.assert_awaited()
        call_kwargs = self.guild.create_text_channel.await_args.kwargs
        self.assertEqual(call_kwargs["name"], "vent-🟡-rough-day")
        self.assertEqual(call_kwargs["category"], category)

        # Ensure @everyone view and send are True
        overwrites = call_kwargs["overwrites"]
        self.assertTrue(overwrites[self.guild.default_role].view_channel)
        self.assertTrue(overwrites[self.guild.default_role].send_messages)

        # Check config
        active_vents = await self.cog.config.guild(self.guild).active_vents()
        self.assertIn("8888", active_vents)
        self.assertEqual(active_vents["8888"]["author_id"], 444)
        self.assertEqual(active_vents["8888"]["intent_key"], "comfort")
        self.assertIn(8888, self.cog._active_channel_ids)

        # Check embed has crisis header when enabled
        send_kwargs = created_channel.send.await_args.kwargs
        sent_embed = send_kwargs["embed"]
        field_names = [f.name for f in sent_embed.fields]
        self.assertIn("Crisis & Peer Support Resources", field_names)

    async def test_create_vent_channel_crisis_disabled(self):
        """When crisis_enabled is False, crisis header field is omitted from embed."""
        author = MagicMock(spec=discord.Member)
        author.id = 555
        author.display_name = "Taylor"
        author.mention = "<@555>"

        category = MagicMock(spec=discord.CategoryChannel)
        category.overwrites = {}

        hub_channel = MagicMock(spec=discord.TextChannel)
        hub_channel.category = category
        self.guild.get_channel.return_value = hub_channel

        created_channel = MagicMock(spec=discord.TextChannel)
        created_channel.id = 7777
        created_channel.send = AsyncMock()
        created_channel.history = MagicMock()
        pin_msg = MagicMock()
        pin_msg.pin = AsyncMock()
        created_channel.send.return_value = pin_msg

        async def empty_history(*args, **kwargs):
            if False:
                yield None

        created_channel.history.return_value = empty_history()
        self.guild.create_text_channel = AsyncMock(return_value=created_channel)

        await self.cog.config.guild(self.guild).hub_channel_id.set(1234)
        await self.cog.config.guild(self.guild).crisis_enabled.set(False)

        await self.cog.create_vent_channel(
            guild=self.guild,
            author=author,
            intent_key="comfort",
            topic="Test",
        )

        sent_embed = created_channel.send.await_args.kwargs["embed"]
        field_names = [f.name for f in sent_embed.fields]
        self.assertNotIn("Crisis & Peer Support Resources", field_names)

    async def test_close_vent_channel_manual(self):
        """Test manual close transitions to archive or delete."""
        channel = MagicMock(spec=discord.TextChannel)
        channel.id = 9999
        channel.name = "vent-🟡-abby"
        channel.guild = self.guild
        channel.set_permissions = AsyncMock()
        channel.send = AsyncMock()
        channel.edit = AsyncMock()
        channel.delete = AsyncMock()
        channel.overwrites_for.return_value = discord.PermissionOverwrite()

        closer = MagicMock(spec=discord.Member)
        closer.mention = "<@555>"
        closer.id = 555

        # Test archive path
        await self.cog.config.guild(self.guild).post_action.set("archive")
        async with self.cog.config.guild(self.guild).active_vents() as vents:
            vents["9999"] = {"author_id": 555}
        self.cog._active_channel_ids.add(9999)

        await self.cog.close_vent_channel(channel, closed_by=closer)
        channel.set_permissions.assert_awaited()
        channel.edit.assert_awaited()
        self.assertEqual(channel.edit.await_args.kwargs["name"], "📦-abby")
        self.assertNotIn(9999, self.cog._active_channel_ids)

    async def test_on_message_listener(self):
        """Human message in active channel updates last_active_at."""
        channel = MagicMock(spec=discord.TextChannel)
        channel.id = 1111

        message = MagicMock(spec=discord.Message)
        message.guild = self.guild
        message.channel = channel
        message.author.bot = False
        message.created_at.timestamp.return_value = 1234567.0

        self.cog._active_channel_ids.add(1111)
        async with self.cog.config.guild(self.guild).active_vents() as vents:
            vents["1111"] = {
                "author_id": 100,
                "is_locked": False,
                "last_active_at": 1000.0,
            }

        await self.cog.on_message(message)

        vents_after = await self.cog.config.guild(self.guild).active_vents()
        self.assertEqual(vents_after["1111"]["last_active_at"], 1234567.0)

        # Bot message should be ignored
        message.author.bot = True
        message.created_at.timestamp.return_value = 9999999.0
        await self.cog.on_message(message)
        vents_after2 = await self.cog.config.guild(self.guild).active_vents()
        self.assertEqual(vents_after2["1111"]["last_active_at"], 1234567.0)

    async def test_on_guild_channel_delete_listener(self):
        """Channel deletion removes channel from config and active cache."""
        channel = MagicMock(spec=discord.TextChannel)
        channel.id = 2222
        channel.guild = self.guild

        self.cog._active_channel_ids.add(2222)
        async with self.cog.config.guild(self.guild).active_vents() as vents:
            vents["2222"] = {"author_id": 200}

        await self.cog.on_guild_channel_delete(channel)

        self.assertNotIn(2222, self.cog._active_channel_ids)
        vents_after = await self.cog.config.guild(self.guild).active_vents()
        self.assertNotIn("2222", vents_after)

    async def test_admin_commands(self):
        """Test administration commands."""
        ctx = MagicMock()
        ctx.guild = self.guild
        ctx.send = AsyncMock()
        ctx.clean_prefix = "!"

        # 1. Timeouts command
        await self.cog.ventset_timeouts.callback(self.cog, ctx, 6.0, 18.0)
        self.assertEqual(await self.cog.config.guild(self.guild).inactivity_timeout(), 6.0)
        self.assertEqual(await self.cog.config.guild(self.guild).hard_cap_timeout(), 18.0)

        # Invalid timeouts
        await self.cog.ventset_timeouts.callback(self.cog, ctx, 0.0, -1.0)
        ctx.send.assert_awaited()

        # 2. Action command
        await self.cog.ventset_action.callback(self.cog, ctx, "delete")
        self.assertEqual(await self.cog.config.guild(self.guild).post_action(), "delete")
        await self.cog.ventset_action.callback(self.cog, ctx, "invalid")

        # 3. Crisis command
        # 3a. Update text
        await self.cog.ventset_crisis.callback(self.cog, ctx, text="Custom Help 123")
        self.assertEqual(await self.cog.config.guild(self.guild).crisis_header(), "Custom Help 123")
        self.assertTrue(await self.cog.config.guild(self.guild).crisis_enabled())

        # 3b. Bare command (view current text)
        channel = MagicMock(spec=discord.TextChannel)
        ctx.channel = channel
        channel.permissions_for.return_value.embed_links = True
        await self.cog.ventset_crisis.callback(self.cog, ctx, text=None)
        ctx.send.assert_awaited()

        # 3c. Clear / off / disable
        await self.cog.ventset_crisis.callback(self.cog, ctx, text="off")
        self.assertFalse(await self.cog.config.guild(self.guild).crisis_enabled())

        # 3d. Bare command when disabled
        await self.cog.ventset_crisis.callback(self.cog, ctx, text=None)
        ctx.send.assert_awaited()

        # 3e. On / enable
        await self.cog.ventset_crisis.callback(self.cog, ctx, text="on")
        self.assertTrue(await self.cog.config.guild(self.guild).crisis_enabled())

        # 3f. Reset
        await self.cog.ventset_crisis.callback(self.cog, ctx, text="reset")
        self.assertEqual(await self.cog.config.guild(self.guild).crisis_header(), DEFAULT_CRISIS_HEADER)
        self.assertTrue(await self.cog.config.guild(self.guild).crisis_enabled())

        # 3g. Blank entry clears / disables
        await self.cog.ventset_crisis.callback(self.cog, ctx, text='""')
        self.assertFalse(await self.cog.config.guild(self.guild).crisis_enabled())

        # 4. Modrole command
        role = MagicMock(spec=discord.Role)
        role.id = 99999
        role.mention = "<@&99999>"
        await self.cog.ventset_modrole.callback(self.cog, ctx, role)
        self.assertEqual(await self.cog.config.guild(self.guild).mod_role_id(), 99999)
        await self.cog.ventset_modrole.callback(self.cog, ctx, None)
        self.assertIsNone(await self.cog.config.guild(self.guild).mod_role_id())

        # 4b. Archive emoji command
        await self.cog.ventset_archiveemoji.callback(self.cog, ctx, "📁")
        self.assertEqual(await self.cog.config.guild(self.guild).archive_emoji(), "📁")
        await self.cog.ventset_archiveemoji.callback(self.cog, ctx, None)
        self.assertEqual(await self.cog.config.guild(self.guild).archive_emoji(), DEFAULT_ARCHIVE_EMOJI)

        # 5. Intents add / remove / reset
        await self.cog.intents_add.callback(self.cog, ctx, "rant", "🔴", rest="Rant / No Advice | Just venting.")
        intents = await self.cog.config.guild(self.guild).intents()
        self.assertIn("rant", intents)
        self.assertEqual(intents["rant"]["emoji"], "🔴")
        self.assertEqual(intents["rant"]["header_note"], "Just venting.")

        # Try to remove non-existent
        await self.cog.intents_remove.callback(self.cog, ctx, "nonexistent")

        # Remove rant
        await self.cog.intents_remove.callback(self.cog, ctx, "rant")
        intents_after = await self.cog.config.guild(self.guild).intents()
        self.assertNotIn("rant", intents_after)

        # Reset intents
        await self.cog.intents_reset.callback(self.cog, ctx)
        reset_intents = await self.cog.config.guild(self.guild).intents()
        self.assertEqual(set(reset_intents.keys()), set(DEFAULT_INTENTS.keys()))

        # 6. Help subcommands
        ctx.send_help = AsyncMock()
        await self.cog.ventset_help.callback(self.cog, ctx)
        ctx.send_help.assert_awaited_with(self.cog.ventset)

        await self.cog.intents_help.callback(self.cog, ctx)
        ctx.send_help.assert_awaited_with(self.cog.ventset_intents)

        # 7. show_settings embed vs plaintext fallback
        channel = MagicMock(spec=discord.TextChannel)
        ctx.channel = channel

        # Test embed mode
        channel.permissions_for.return_value.embed_links = True
        await self.cog.show_settings(ctx)
        call_kwargs = ctx.send.await_args.kwargs
        self.assertIn("embed", call_kwargs)

        # Test plaintext fallback (when embed_links = False)
        channel.permissions_for.return_value.embed_links = False
        await self.cog.show_settings(ctx)
        call_args = ctx.send.await_args
        self.assertIn("EphemeralVents Configuration", call_args.args[0])

        # 8. intents_list embed vs plaintext fallback
        channel.permissions_for.return_value.embed_links = True
        await self.cog.intents_list.callback(self.cog, ctx)
        self.assertIn("embed", ctx.send.await_args.kwargs)

        channel.permissions_for.return_value.embed_links = False
        await self.cog.intents_list.callback(self.cog, ctx)
        self.assertIn("Configured Vent Intents", ctx.send.await_args.args[0])

    async def test_gdpr_methods(self):
        """Test red_get_data_for_user and red_delete_data_for_user."""
        async with self.cog.config.guild(self.guild).active_vents() as vents:
            vents["3333"] = {
                "author_id": 5050,
                "intent_key": "comfort",
                "created_at": 1000.0,
            }
        self.cog._active_channel_ids.add(3333)

        data = await self.cog.red_get_data_for_user(user_id=5050)
        self.assertEqual(len(data["active_vents"]), 1)
        self.assertEqual(data["active_vents"][0]["channel_id"], "3333")

        await self.cog.red_delete_data_for_user(requester="user", user_id=5050)
        vents_after = await self.cog.config.guild(self.guild).active_vents()
        self.assertNotIn("3333", vents_after)
        self.assertNotIn(3333, self.cog._active_channel_ids)


if __name__ == "__main__":
    unittest.main()

