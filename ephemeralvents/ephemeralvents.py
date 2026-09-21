"""EphemeralVents Cog for Red-DiscordBot.

On-demand peer-support venting system generating ephemeral text channels
with upfront interaction boundaries and automated lifecycle management.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Any, Dict, List, Literal, Optional, Set, Tuple, Union

import discord
from discord.ext import tasks
from red_commons.logging import getLogger
from redbot.core import Config, commands
from redbot.core.bot import Red

from .constants import (
    CONFIG_IDENTIFIER,
    DEFAULT_CRISIS_HEADER,
    DEFAULT_EMBED_COLOR,
    DEFAULT_GUILD,
    DEFAULT_INTENTS,
    INTENT_COLORS,
    MAX_SLUG_LENGTH,
)
from .views import (
    ArchivedVentView,
    CloseVentView,
    LegacyArchivedVentView,
    VentLauncherView,
)

log = getLogger("red.antigravity.ephemeralvents")


def sanitize_channel_name(emoji: str, topic: Optional[str], fallback: str) -> str:
    """Sanitize channel name to lowercase alphanumeric characters and hyphens.

    Format: vent-<emoji>-<topic> or fallback to vent-<emoji>-<fallback>.
    Total length is safely capped below Discord's 100-character limit.
    """
    clean_topic = ""
    if topic:
        clean = topic.strip().lower()
        clean = re.sub(r"[\s_]+", "-", clean)
        clean = re.sub(r"[^a-z0-9\-]", "", clean)
        clean_topic = re.sub(r"-+", "-", clean).strip("-")

    if not clean_topic:
        clean = fallback.strip().lower()
        clean = re.sub(r"[\s_]+", "-", clean)
        clean = re.sub(r"[^a-z0-9\-]", "", clean)
        clean_topic = re.sub(r"-+", "-", clean).strip("-")

    if not clean_topic:
        clean_topic = "vent"

    # Emoji prefix handling
    prefix = "vent-"
    if emoji:
        custom_match = re.match(r"<a?:([a-zA-Z0-9_]+):\d+>", emoji)
        if custom_match:
            emo_str = custom_match.group(1).lower()
            prefix = f"vent-{emo_str}-"
        else:
            prefix = f"vent-{emoji}-"

    max_len = 100
    avail = max_len - len(prefix)
    if avail < 1:
        return prefix[:100].rstrip("-")

    return f"{prefix}{clean_topic[:avail]}".rstrip("-")


class EphemeralVents(commands.Cog):
    """Ephemeral peer-support venting channels with structured boundaries."""

    def __init__(self, bot: Red) -> None:
        super().__init__()
        self.bot: Red = bot
        self.config: Config = Config.get_conf(
            self,
            identifier=CONFIG_IDENTIFIER,
            force_registration=True,
        )
        self.config.register_guild(**DEFAULT_GUILD)

        # In-memory fast cache of tracked vent channel IDs
        self._active_channel_ids: Set[int] = set()

        # Concurrency locks per guild to avoid race conditions during creation
        self._guild_locks: Dict[int, asyncio.Lock] = {}

    async def cog_load(self) -> None:
        """Register persistent views, load active channels cache, and start background loop."""
        # Persistent UI views for Discord.py 2.x
        self.bot.add_view(VentLauncherView(self))
        self.bot.add_view(CloseVentView(self))
        self.bot.add_view(ArchivedVentView(self))
        self.bot.add_view(LegacyArchivedVentView(self))

        # Populate active channel cache from Config and migrate legacy crisis header
        try:
            all_guilds = await self.config.all_guilds()
            for guild_id, guild_data in all_guilds.items():
                active_vents = guild_data.get("active_vents", {})
                for channel_id_str in active_vents.keys():
                    try:
                        self._active_channel_ids.add(int(channel_id_str))
                    except (ValueError, TypeError):
                        pass

                crisis = guild_data.get("crisis_header", "")
                if crisis and crisis.startswith("### 🆘 Crisis Support & Resources"):
                    new_crisis = (
                        crisis.split("\n", 1)[1].lstrip()
                        if "\n" in crisis
                        else DEFAULT_CRISIS_HEADER
                    )
                    await self.config.guild_from_id(guild_id).crisis_header.set(new_crisis)
        except Exception as e:
            log.error(f"Failed to load active vents cache: {e}")

        # Start periodic cleanup loop
        self.cleanup_loop.start()

    def cog_unload(self) -> None:
        """Cancel background tasks when the cog unloads."""
        self.cleanup_loop.cancel()

    def _get_guild_lock(self, guild_id: int) -> asyncio.Lock:
        """Retrieve or create an asyncio lock for a guild."""
        if guild_id not in self._guild_locks:
            self._guild_locks[guild_id] = asyncio.Lock()
        return self._guild_locks[guild_id]

    # -------------------------------------------------------------------------
    # Helper & Validation Methods
    # -------------------------------------------------------------------------

    async def check_user_vent_rate_limit(
        self, guild: discord.Guild, user: discord.abc.User
    ) -> Tuple[bool, Optional[discord.TextChannel]]:
        """Verify if the user already has an active vent channel.

        Returns a tuple of (has_active, existing_channel).
        Automatically prunes stale channels that no longer exist in Discord.
        """
        stale_channels: List[str] = []
        existing_channel: Optional[discord.TextChannel] = None
        has_active: bool = False

        async with self.config.guild(guild).active_vents() as vents:
            for channel_id_str, data in vents.items():
                if data.get("author_id") == user.id:
                    channel_id = int(channel_id_str)
                    ch = guild.get_channel(channel_id)
                    if not ch:
                        try:
                            fetched = await self.bot.fetch_channel(channel_id)
                            ch = fetched if isinstance(fetched, discord.TextChannel) else None
                        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                            ch = None

                    if ch and isinstance(ch, discord.TextChannel):
                        has_active = True
                        existing_channel = ch
                        break
                    else:
                        stale_channels.append(channel_id_str)

            for cid_str in stale_channels:
                vents.pop(cid_str, None)
                self._active_channel_ids.discard(int(cid_str))

        return has_active, existing_channel

    async def can_moderate_vent(
        self,
        guild: discord.Guild,
        member: discord.Member,
        channel: Optional[discord.TextChannel] = None,
    ) -> bool:
        """Check if a member has moderator authority over vent channels."""
        # Bot owners and Red bot admins
        if await self.bot.is_owner(member) or await self.bot.is_admin(member):
            return True

        # Server administrators
        if member.guild_permissions.administrator:
            return True

        # Channel or guild manage_channels permission
        if channel:
            if channel.permissions_for(member).manage_channels:
                return True
        elif member.guild_permissions.manage_channels:
            return True

        # Configured moderator role check
        mod_role_id = await self.config.guild(guild).mod_role_id()
        if mod_role_id and member.get_role(mod_role_id) is not None:
            return True

        # Red bot mod check
        if await self.bot.is_mod(member):
            return True

        return False

    async def can_close_vent(
        self,
        guild: discord.Guild,
        member: discord.Member,
        channel: discord.TextChannel,
    ) -> bool:
        """Check if a member is allowed to manually close the given vent channel."""
        active_vents = await self.config.guild(guild).active_vents()
        vent_data = active_vents.get(str(channel.id))
        if vent_data and vent_data.get("author_id") == member.id:
            return True

        return await self.can_moderate_vent(guild, member, channel)

    # -------------------------------------------------------------------------
    # Vent Lifecycle Actions: Create, Lock, Archive, Delete
    # -------------------------------------------------------------------------

    async def create_vent_channel(
        self,
        guild: discord.Guild,
        author: discord.Member,
        intent_key: str,
        topic: Optional[str] = None,
    ) -> discord.TextChannel:
        """Create and initialize a new ephemeral vent channel."""
        lock = self._get_guild_lock(guild.id)
        async with lock:
            # Re-verify rate limit under the lock
            has_active, existing = await self.check_user_vent_rate_limit(guild, author)
            if has_active and existing:
                return existing

            guild_config = self.config.guild(guild)
            hub_channel_id = await guild_config.hub_channel_id()
            hub_channel = guild.get_channel(hub_channel_id) if hub_channel_id else None
            parent_category = hub_channel.category if hub_channel else None

            # Retrieve intent profile
            intents = await guild_config.intents()
            intent_data = intents.get(intent_key, DEFAULT_INTENTS.get("open", {}))
            intent_emoji = intent_data.get("emoji", "💬")
            intent_label = intent_data.get("label", intent_key.capitalize())
            intent_note = intent_data.get("header_note", "Please respect the author's space.")

            # Sanitize channel name
            fallback_name = author.display_name or author.name
            channel_name = sanitize_channel_name(intent_emoji, topic, fallback_name)

            # Sync base permissions from the category
            overwrites: Dict[
                Union[discord.Role, discord.Member], discord.PermissionOverwrite
            ] = {}
            if parent_category:
                overwrites = parent_category.overwrites.copy()

            # Ensure @everyone has view_channel=True and send_messages=True
            everyone_role = guild.default_role
            everyone_ow = overwrites.get(everyone_role, discord.PermissionOverwrite())
            everyone_ow.view_channel = True
            everyone_ow.send_messages = True
            overwrites[everyone_role] = everyone_ow

            # Ensure the bot itself has all necessary permissions
            bot_ow = overwrites.get(guild.me, discord.PermissionOverwrite())
            bot_ow.view_channel = True
            bot_ow.send_messages = True
            bot_ow.manage_channels = True
            bot_ow.manage_messages = True
            bot_ow.embed_links = True
            bot_ow.read_message_history = True
            overwrites[guild.me] = bot_ow

            # Ensure configured mod role has visibility and messaging
            mod_role_id = await guild_config.mod_role_id()
            if mod_role_id:
                mod_role = guild.get_role(mod_role_id)
                if mod_role:
                    mod_ow = overwrites.get(mod_role, discord.PermissionOverwrite())
                    mod_ow.view_channel = True
                    mod_ow.send_messages = True
                    mod_ow.read_message_history = True
                    overwrites[mod_role] = mod_ow

            # Create text channel
            channel = await guild.create_text_channel(
                name=channel_name,
                category=parent_category,
                overwrites=overwrites,
                topic=f"Ephemeral Vent | Boundary: {intent_label} | Author: {author.display_name}",
                reason=f"Ephemeral vent channel requested by {author} ({author.id})",
            )

            # Construct opening embed
            crisis_header = await guild_config.crisis_header()
            if crisis_header and crisis_header.startswith("### 🆘 Crisis Support & Resources"):
                crisis_header = (
                    crisis_header.split("\n", 1)[1].lstrip()
                    if "\n" in crisis_header
                    else DEFAULT_CRISIS_HEADER
                )
            embed_color = INTENT_COLORS.get(intent_key, DEFAULT_EMBED_COLOR)

            title_text = f"{intent_emoji} Vent: {topic}" if topic else f"{intent_emoji} Vent Space"
            embed = discord.Embed(
                title=title_text,
                color=embed_color,
                timestamp=discord.utils.utcnow(),
            )
            if topic:
                embed.add_field(name="Topic", value=topic, inline=False)

            embed.add_field(
                name=f"Interaction Boundary — {intent_label}",
                value=intent_note,
                inline=False,
            )
            embed.add_field(
                name="Vent Author",
                value=f"{author.mention} ({author.display_name})",
                inline=True,
            )

            crisis_enabled = await guild_config.crisis_enabled()
            if crisis_enabled and crisis_header:
                embed.add_field(
                    name="Crisis & Peer Support Resources",
                    value=crisis_header,
                    inline=False,
                )

            embed.set_footer(
                text="Click 'Close Vent' below when you are ready to conclude this session."
            )

            # Send and pin opening message
            view = CloseVentView(self)
            opening_msg = await channel.send(
                content=f"Welcome {author.mention}, your ephemeral vent channel is ready.",
                embed=embed,
                view=view,
            )

            try:
                await opening_msg.pin(reason="Pin ephemeral vent boundary notice and controls")
                # Attempt to delete the system pins_add message to keep channel tidy
                async for m in channel.history(limit=5):
                    if m.type == discord.MessageType.pins_add:
                        await m.delete()
                        break
            except (discord.Forbidden, discord.HTTPException):
                pass

            # Record active vent metadata
            now = time.time()
            async with guild_config.active_vents() as vents:
                vents[str(channel.id)] = {
                    "author_id": author.id,
                    "intent_key": intent_key,
                    "created_at": now,
                    "last_active_at": now,
                    "is_locked": False,
                    "locked_at": None,
                }
            self._active_channel_ids.add(channel.id)

            return channel

    async def lock_vent_channel(
        self,
        channel: discord.TextChannel,
        inactivity_hours: float,
        current_time: Optional[float] = None,
    ) -> None:
        """Lock channel send_messages permission due to inactivity."""
        guild = channel.guild
        everyone_role = guild.default_role

        try:
            everyone_ow = channel.overwrites_for(everyone_role)
            everyone_ow.send_messages = False
            await channel.set_permissions(
                everyone_role,
                overwrite=everyone_ow,
                reason="Ephemeral vent inactivity lock triggered",
            )
        except discord.Forbidden:
            log.warning(f"Forbidden while setting lock overwrite on channel {channel.id}")
            return

        display_hours = (
            int(inactivity_hours) if inactivity_hours.is_integer() else f"{inactivity_hours:g}"
        )
        try:
            await channel.send(
                f"🔒 This vent has been inactive for {display_hours} hours and is now locked."
            )
        except (discord.Forbidden, discord.HTTPException):
            pass

        now = current_time if current_time is not None else time.time()
        async with self.config.guild(guild).active_vents() as vents:
            channel_id_str = str(channel.id)
            if channel_id_str in vents:
                vents[channel_id_str]["is_locked"] = True
                vents[channel_id_str]["locked_at"] = now

    async def archive_vent_channel(
        self, channel: discord.TextChannel, reason: str = "Ephemeral vent archived"
    ) -> None:
        """Archive a vent channel: restrict @everyone, grant mod access, move category."""
        guild = channel.guild
        guild_config = self.config.guild(guild)
        everyone_role = guild.default_role

        # 1. Restrict read access: set @everyone view_channel=False and send_messages=False
        try:
            everyone_ow = channel.overwrites_for(everyone_role)
            everyone_ow.view_channel = False
            everyone_ow.send_messages = False
            await channel.set_permissions(everyone_role, overwrite=everyone_ow, reason=reason)
        except discord.Forbidden:
            log.warning(f"Forbidden while setting @everyone overwrite in {channel.id}")

        # 2. Grant view_channel=True, read_message_history=True, send_messages=False to mod_role_id
        mod_role_id = await guild_config.mod_role_id()
        if mod_role_id:
            mod_role = guild.get_role(mod_role_id)
            if mod_role:
                try:
                    mod_ow = channel.overwrites_for(mod_role)
                    mod_ow.view_channel = True
                    mod_ow.read_message_history = True
                    mod_ow.send_messages = False
                    await channel.set_permissions(mod_role, overwrite=mod_ow, reason=reason)
                except discord.Forbidden:
                    log.warning(f"Forbidden while setting mod role overwrite in {channel.id}")

        # Grant bot full permissions to manage archived channel
        try:
            bot_ow = channel.overwrites_for(guild.me)
            bot_ow.view_channel = True
            bot_ow.read_message_history = True
            bot_ow.send_messages = True
            bot_ow.manage_channels = True
            await channel.set_permissions(guild.me, overwrite=bot_ow, reason=reason)
        except discord.Forbidden:
            pass

        # 3. Optional move to archive_category_id if configured
        archive_category_id = await guild_config.archive_category_id()
        if archive_category_id:
            archive_cat = guild.get_channel(archive_category_id)
            if isinstance(archive_cat, discord.CategoryChannel):
                try:
                    await channel.edit(category=archive_cat, reason=reason)
                except (discord.Forbidden, discord.HTTPException) as e:
                    log.warning(
                        f"Could not move archived channel {channel.id} to category {archive_category_id}: {e}"
                    )

        # 4. Post moderator utility message with persistent Delete Vent Channel button
        embed = discord.Embed(
            title="Vent Archived",
            description=(
                "This vent channel has completed its session and has been archived.\n"
                "Members with the moderator role or `Manage Channels` permission may review "
                "the transcript or permanently delete this channel using the button below."
            ),
            color=discord.Color.dark_grey(),
            timestamp=discord.utils.utcnow(),
        )
        view = ArchivedVentView(self)
        try:
            await channel.send(embed=embed, view=view)
        except (discord.Forbidden, discord.HTTPException) as e:
            log.warning(f"Could not send archived notice in channel {channel.id}: {e}")

        # 5. Remove channel from active loop tracking
        channel_id_str = str(channel.id)
        async with guild_config.active_vents() as vents:
            vents.pop(channel_id_str, None)
        self._active_channel_ids.discard(channel.id)

    async def delete_vent_channel(
        self, channel: discord.TextChannel, reason: str = "Ephemeral vent deleted"
    ) -> None:
        """Permanently delete a vent channel and clean up its config metadata."""
        guild = channel.guild
        channel_id_str = str(channel.id)

        # Clean config entry first
        async with self.config.guild(guild).active_vents() as vents:
            vents.pop(channel_id_str, None)
        self._active_channel_ids.discard(channel.id)

        try:
            await channel.delete(reason=reason)
        except discord.NotFound:
            pass
        except discord.Forbidden:
            log.warning(f"Missing permissions to delete channel {channel.id} in guild {guild.id}")
        except discord.HTTPException as e:
            log.warning(f"Failed to delete channel {channel.id}: {e}")

    async def close_vent_channel(
        self, channel: discord.TextChannel, closed_by: discord.Member
    ) -> None:
        """Handle manual vent closure: immediately lock and execute post_action."""
        guild = channel.guild
        everyone_role = guild.default_role

        # Immediately lock channel
        try:
            everyone_ow = channel.overwrites_for(everyone_role)
            everyone_ow.send_messages = False
            await channel.set_permissions(
                everyone_role,
                overwrite=everyone_ow,
                reason=f"Vent closed by {closed_by} ({closed_by.id})",
            )
        except (discord.Forbidden, discord.HTTPException):
            pass

        post_action = await self.config.guild(guild).post_action()

        if post_action == "delete":
            try:
                await channel.send(
                    f"🔒 Vent closed by {closed_by.mention}. This channel will now be permanently deleted..."
                )
            except (discord.Forbidden, discord.HTTPException):
                pass
            await asyncio.sleep(2.0)
            await self.delete_vent_channel(
                channel,
                reason=f"Vent closed by {closed_by} ({closed_by.id})",
            )
        else:
            try:
                await channel.send(
                    f"🔒 Vent closed by {closed_by.mention}. Archiving channel..."
                )
            except (discord.Forbidden, discord.HTTPException):
                pass
            await self.archive_vent_channel(
                channel,
                reason=f"Vent closed by {closed_by} ({closed_by.id})",
            )

    # -------------------------------------------------------------------------
    # Event Listeners
    # -------------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Update last_active_at timestamp on human activity in active vent channels."""
        if not message.guild or message.author.bot:
            return

        channel_id = message.channel.id
        if channel_id not in self._active_channel_ids:
            return

        channel_id_str = str(channel_id)
        now = message.created_at.timestamp()

        # Update last_active_at if not locked
        async with self.config.guild(message.guild).active_vents() as vents:
            if channel_id_str in vents and not vents[channel_id_str].get("is_locked", False):
                vents[channel_id_str]["last_active_at"] = now

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel) -> None:
        """Clean up config when a tracked vent channel is manually deleted."""
        if channel.id in self._active_channel_ids:
            self._active_channel_ids.discard(channel.id)
            async with self.config.guild(channel.guild).active_vents() as vents:
                vents.pop(str(channel.id), None)

    # -------------------------------------------------------------------------
    # Background Lifecycle Loop
    # -------------------------------------------------------------------------

    @tasks.loop(minutes=5.0)
    async def cleanup_loop(self) -> None:
        """Periodic background evaluation of inactivity and lifespan timeouts."""
        current_time = time.time()
        for guild in self.bot.guilds:
            try:
                await self._process_guild_lifecycle(guild, current_time)
            except Exception as e:
                log.exception(f"Unexpected error in vent cleanup loop for guild {guild.id}: {e}")

    @cleanup_loop.before_loop
    async def before_cleanup_loop(self) -> None:
        """Wait until bot is ready before starting loop."""
        await self.bot.wait_until_ready()

    async def _process_guild_lifecycle(self, guild: discord.Guild, current_time: float) -> None:
        """Process inactivity locks and hard cap expirations for a single guild."""
        guild_config = self.config.guild(guild)
        active_vents = await guild_config.active_vents()
        if not active_vents:
            return

        inactivity_hours = float(await guild_config.inactivity_timeout())
        hard_cap_hours = float(await guild_config.hard_cap_timeout())
        post_action = await guild_config.post_action()

        inactivity_seconds = inactivity_hours * 3600.0
        hard_cap_seconds = hard_cap_hours * 3600.0

        stale_channels: List[str] = []

        for channel_id_str, vent_data in list(active_vents.items()):
            channel_id = int(channel_id_str)
            channel = guild.get_channel(channel_id)
            if not channel:
                try:
                    fetched = await self.bot.fetch_channel(channel_id)
                    channel = fetched if isinstance(fetched, discord.TextChannel) else None
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    channel = None

            if not channel or not isinstance(channel, discord.TextChannel):
                stale_channels.append(channel_id_str)
                continue

            is_locked = vent_data.get("is_locked", False)
            last_active = vent_data.get("last_active_at", vent_data.get("created_at", current_time))

            # Phase 1: Inactivity Lock Check
            if not is_locked:
                if (current_time - last_active) >= inactivity_seconds:
                    try:
                        await self.lock_vent_channel(channel, inactivity_hours, current_time=current_time)
                    except Exception as e:
                        log.error(f"Error locking vent channel {channel_id}: {e}")
                continue

            # Phase 2: Lifespan Hard Cap Check (when is_locked=True)
            locked_at = vent_data.get("locked_at") or last_active
            if (current_time - locked_at) >= hard_cap_seconds:
                try:
                    if post_action == "delete":
                        await self.delete_vent_channel(
                            channel,
                            reason=f"Ephemeral vent hard cap timeout reached ({hard_cap_hours:g}h)",
                        )
                    else:
                        await self.archive_vent_channel(
                            channel,
                            reason=f"Ephemeral vent hard cap timeout reached ({hard_cap_hours:g}h)",
                        )
                except Exception as e:
                    log.error(f"Error executing hard cap action on channel {channel_id}: {e}")

        if stale_channels:
            async with guild_config.active_vents() as vents:
                for cid_str in stale_channels:
                    vents.pop(cid_str, None)
                    self._active_channel_ids.discard(int(cid_str))

    # -------------------------------------------------------------------------
    # Administration Commands ([p]ventset)
    # -------------------------------------------------------------------------

    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    @commands.group(name="ventset", invoke_without_command=True)
    async def ventset(self, ctx: commands.Context) -> None:
        """Configure EphemeralVents.

        Configure settings, timeouts, intents, and channels for ephemeral vents.
        """
        if ctx.invoked_subcommand is None:
            await self.show_settings(ctx)

    @ventset.command(name="show")
    async def ventset_show(self, ctx: commands.Context) -> None:
        """Show current settings.

        Display current EphemeralVents configuration settings.
        """
        await self.show_settings(ctx)

    async def show_settings(self, ctx: commands.Context) -> None:
        """Helper to render guild settings embed."""
        guild = ctx.guild
        cfg = self.config.guild(guild)

        hub_channel_id = await cfg.hub_channel_id()
        mod_role_id = await cfg.mod_role_id()
        archive_category_id = await cfg.archive_category_id()
        inactivity_timeout = await cfg.inactivity_timeout()
        hard_cap_timeout = await cfg.hard_cap_timeout()
        post_action = await cfg.post_action()
        active_vents = await cfg.active_vents()
        intents = await cfg.intents()
        crisis_enabled = await cfg.crisis_enabled()
        crisis_header = await cfg.crisis_header()
        if crisis_header and crisis_header.startswith("### 🆘 Crisis Support & Resources"):
            crisis_header = (
                crisis_header.split("\n", 1)[1].lstrip()
                if "\n" in crisis_header
                else DEFAULT_CRISIS_HEADER
            )

        hub_ch = guild.get_channel(hub_channel_id) if hub_channel_id else None
        mod_role = guild.get_role(mod_role_id) if mod_role_id else None
        archive_cat = guild.get_channel(archive_category_id) if archive_category_id else None

        embed = discord.Embed(
            title="EphemeralVents Configuration",
            color=discord.Color.teal(),
            timestamp=discord.utils.utcnow(),
        )

        hub_desc = hub_ch.mention if hub_ch else "*Not set*"
        mod_desc = mod_role.mention if mod_role else "*Not set*"
        arch_desc = archive_cat.name if archive_cat else "*None (keep in original category)*"

        embed.add_field(name="Hub Channel", value=hub_desc, inline=True)
        embed.add_field(name="Mod Role", value=mod_desc, inline=True)
        embed.add_field(name="Archive Category", value=arch_desc, inline=True)
        embed.add_field(name="Inactivity Timeout", value=f"{inactivity_timeout:g} hours", inline=True)
        embed.add_field(name="Hard Cap Lifespan", value=f"{hard_cap_timeout:g} hours", inline=True)
        embed.add_field(name="Post-Expiration Action", value=f"`{post_action}`", inline=True)
        embed.add_field(name="Active Vents", value=f"{len(active_vents)} channel(s)", inline=True)

        intent_summary = ", ".join(f"{data.get('emoji', '')} `{slug}`" for slug, data in intents.items())
        embed.add_field(
            name=f"Configured Intents ({len(intents)})",
            value=intent_summary if intent_summary else "*None*",
            inline=False,
        )

        if not crisis_enabled or not crisis_header:
            crisis_preview = "🔴 *Disabled / Cleared*"
        else:
            crisis_preview = (
                f"🟢 Enabled\n{crisis_header[:250]}..."
                if len(crisis_header) > 250
                else f"🟢 Enabled\n{crisis_header}"
            )
        embed.add_field(name="Crisis Header", value=crisis_preview, inline=False)
        embed.set_footer(text=f"Use {ctx.clean_prefix}ventset help to view all available commands.")

        can_embed = ctx.channel.permissions_for(ctx.guild.me).embed_links
        if can_embed:
            try:
                await ctx.send(embed=embed)
                return
            except discord.Forbidden:
                pass

        # Plaintext fallback when bot lacks Embed Links permission in this channel
        text_lines = [
            "**⚙️ EphemeralVents Configuration**",
            f"• **Hub Channel:** {hub_desc}",
            f"• **Mod Role:** {mod_desc}",
            f"• **Archive Category:** {arch_desc}",
            f"• **Inactivity Timeout:** {inactivity_timeout:g} hours",
            f"• **Hard Cap Lifespan:** {hard_cap_timeout:g} hours",
            f"• **Post-Expiration Action:** `{post_action}`",
            f"• **Active Vents:** {len(active_vents)} channel(s)",
            f"• **Configured Intents ({len(intents)}):** {intent_summary if intent_summary else '*None*'}",
            f"• **Crisis Header Preview:** {crisis_preview}",
            "",
            f"*(Tip: Grant me 'Embed Links' permission in this channel for rich embeds. Use `{ctx.clean_prefix}ventset help` to view subcommands.)*",
        ]
        try:
            await ctx.send("\n".join(text_lines))
        except discord.Forbidden:
            log.warning(
                f"Forbidden while sending settings message in guild {guild.id} channel {ctx.channel.id}"
            )

    @ventset.command(name="help", aliases=["subcommands", "commands"])
    async def ventset_help(self, ctx: commands.Context) -> None:
        """List ventset subcommands.

        Display all available ventset subcommands and their usage.
        """
        await ctx.send_help(self.ventset)

    @ventset.command(name="channel")
    async def ventset_channel(
        self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None
    ) -> None:
        """Set or clear vent hub channel.

        Set the vent hub launcher channel and post the launcher embed,
        or pass no channel to clear and disable it.
        """
        if channel is None:
            await self.config.guild(ctx.guild).hub_channel_id.set(None)
            await ctx.send("✅ Vent hub channel has been cleared and disabled.")
            return

        # Check permissions in the chosen channel
        bot_perms = channel.permissions_for(ctx.guild.me)
        if not (bot_perms.view_channel and bot_perms.send_messages and bot_perms.embed_links):
            await ctx.send(
                f"❌ I need permissions to View Channel, Send Messages, and Embed Links in {channel.mention}."
            )
            return

        # Check category permissions for channel creation
        if channel.category:
            cat_perms = channel.category.permissions_for(ctx.guild.me)
            if not cat_perms.manage_channels:
                await ctx.send(
                    f"⚠️ Warning: I do not have 'Manage Channels' permission in category **{channel.category.name}**. "
                    "I will be unable to generate vent channels there until permissions are granted."
                )

        await self.config.guild(ctx.guild).hub_channel_id.set(channel.id)

        # Post / refresh launcher embed
        launcher_embed = discord.Embed(
            title="🌱 Peer Support & Vent Hub",
            description=(
                "Need a safe space to share what's on your mind? Click the button below to open a private peer-support channel.\n\n"
                "• **Choose Your Intent:** Upfront interaction style (advice, comfort only, gentle, etc.).\n"
                "• **Ephemeral:** Inactive channels lock automatically and are archived or deleted.\n"
                "• **In Control:** Close your vent at any time with the Close Vent button."
            ),
            color=discord.Color.teal(),
        )
        launcher_embed.set_footer(text="Please respect community boundaries and interaction rules.")
        view = VentLauncherView(self)

        try:
            await channel.send(embed=launcher_embed, view=view)
            await ctx.send(f"✅ Vent hub channel set to {channel.mention} and launcher embed posted.")
        except discord.Forbidden:
            await ctx.send(
                f"✅ Vent hub channel set to {channel.mention}, but I was unable to send the launcher embed (Forbidden)."
            )

    @ventset.command(name="modrole")
    async def ventset_modrole(
        self, ctx: commands.Context, role: Optional[discord.Role] = None
    ) -> None:
        """Set or clear moderator role.

        Configure the role allowed to moderate vents and access archives.
        """
        if role is None:
            await self.config.guild(ctx.guild).mod_role_id.set(None)
            await ctx.send("✅ Moderator role cleared. Only users with 'Manage Channels' can moderate vents.")
            return

        await self.config.guild(ctx.guild).mod_role_id.set(role.id)
        await ctx.send(f"✅ Moderator role set to {role.mention}.")

    @ventset.command(name="archivecategory")
    async def ventset_archivecategory(
        self, ctx: commands.Context, category: Optional[discord.CategoryChannel] = None
    ) -> None:
        """Set or clear archive category.

        Configure an optional category to move archived vent channels into.
        """
        if category is None:
            await self.config.guild(ctx.guild).archive_category_id.set(None)
            await ctx.send("✅ Archive category reset to None. Archived vents will remain in their original category.")
            return

        # Check bot permissions in target category
        perms = category.permissions_for(ctx.guild.me)
        if not perms.manage_channels:
            await ctx.send(
                f"⚠️ Warning: I do not have 'Manage Channels' permission in category **{category.name}**."
            )

        await self.config.guild(ctx.guild).archive_category_id.set(category.id)
        await ctx.send(f"✅ Archive category set to **{category.name}**.")

    @ventset.command(name="timeouts")
    async def ventset_timeouts(
        self, ctx: commands.Context, inactivity_hours: float, lifespan_hours: float
    ) -> None:
        """Set vent timeouts.

        Set inactivity lock and lifespan hard cap durations in hours.
        """
        if inactivity_hours <= 0.0 or lifespan_hours <= 0.0:
            await ctx.send("❌ Timeout durations must be greater than 0 hours.")
            return

        await self.config.guild(ctx.guild).inactivity_timeout.set(float(inactivity_hours))
        await self.config.guild(ctx.guild).hard_cap_timeout.set(float(lifespan_hours))
        await ctx.send(
            f"✅ Timeouts updated:\n"
            f"• **Inactivity Lock:** {inactivity_hours:g} hours\n"
            f"• **Hard Cap Lifespan:** {lifespan_hours:g} hours"
        )

    @ventset.command(name="action")
    async def ventset_action(
        self, ctx: commands.Context, action: Literal["archive", "delete"]
    ) -> None:
        """Set expiration action.

        Set the post-expiration action to either 'archive' or 'delete'.
        """
        act = action.lower()
        if act not in ("archive", "delete"):
            await ctx.send("❌ Action must be either `archive` or `delete`.")
            return

        await self.config.guild(ctx.guild).post_action.set(act)
        await ctx.send(f"✅ Post-expiration action set to `{act}`.")

    @ventset.command(name="crisis")
    async def ventset_crisis(
        self, ctx: commands.Context, *, text: Optional[str] = None
    ) -> None:
        """View or configure crisis support header.

        Run without arguments to view current crisis resources text.
        Pass text to update, 'reset' for default, or 'off'/'clear' to disable.
        """
        guild = ctx.guild
        cfg = self.config.guild(guild)

        # Case 1: Bare command -> show current crisis text and status
        if text is None:
            crisis_enabled = await cfg.crisis_enabled()
            crisis_header = await cfg.crisis_header()
            if crisis_header and crisis_header.startswith("### 🆘 Crisis Support & Resources"):
                crisis_header = (
                    crisis_header.split("\n", 1)[1].lstrip()
                    if "\n" in crisis_header
                    else DEFAULT_CRISIS_HEADER
                )

            can_embed = ctx.channel.permissions_for(guild.me).embed_links

            if not crisis_enabled or not crisis_header:
                desc = (
                    "🔴 **Status:** Disabled / Cleared\n\n"
                    "No crisis support resources will be displayed in vent channels."
                )
                tip = f"Use `{ctx.clean_prefix}ventset crisis reset` to restore default or `{ctx.clean_prefix}ventset crisis on` to re-enable."
            else:
                desc = f"🟢 **Status:** Enabled\n\n{crisis_header}"
                tip = (
                    f"• **Update text:** `{ctx.clean_prefix}ventset crisis <text>`\n"
                    f"• **Reset to default:** `{ctx.clean_prefix}ventset crisis reset`\n"
                    f"• **Disable / clear:** `{ctx.clean_prefix}ventset crisis off` (or `clear`)"
                )

            if can_embed:
                embed = discord.Embed(
                    title="Crisis Support & Peer Resources",
                    description=desc,
                    color=discord.Color.teal() if (crisis_enabled and crisis_header) else discord.Color.red(),
                    timestamp=discord.utils.utcnow(),
                )
                embed.set_footer(text=f"Use {ctx.clean_prefix}ventset crisis <option> to modify.")
                try:
                    await ctx.send(embed=embed)
                    return
                except discord.Forbidden:
                    pass

            # Plaintext fallback
            msg = f"**Crisis Support & Peer Resources**\n\n{desc}\n\n{tip}"
            try:
                await ctx.send(msg)
            except discord.Forbidden:
                pass
            return

        clean_text = text.strip().strip("'\"")

        # Case 2: Blank entry, clear, disable, off, none
        if not clean_text or clean_text.lower() in ("clear", "none", "disable", "off"):
            await cfg.crisis_enabled.set(False)
            await ctx.send(
                f"✅ Crisis support header has been disabled and removed from vent channels.\n"
                f"*(Restore anytime with `{ctx.clean_prefix}ventset crisis reset` or `{ctx.clean_prefix}ventset crisis on`)*"
            )
            return

        # Case 3: Enable / on
        if clean_text.lower() in ("enable", "on"):
            await cfg.crisis_enabled.set(True)
            crisis_header = await cfg.crisis_header()
            if not crisis_header:
                await cfg.crisis_header.set(DEFAULT_CRISIS_HEADER)
            await ctx.send("✅ Crisis support header has been enabled.")
            return

        # Case 4: Reset to default
        if clean_text.lower() == "reset":
            await cfg.crisis_header.set(DEFAULT_CRISIS_HEADER)
            await cfg.crisis_enabled.set(True)
            await ctx.send("✅ Crisis support header text has been restored to default and enabled.")
            return

        # Case 5: Update custom text
        await cfg.crisis_header.set(clean_text)
        await cfg.crisis_enabled.set(True)
        await ctx.send("✅ Crisis support header text has been updated and enabled.")

    # -------------------------------------------------------------------------
    # Intent Management Subcommands ([p]ventset intents)
    # -------------------------------------------------------------------------

    @ventset.group(name="intents", invoke_without_command=True)
    async def ventset_intents(self, ctx: commands.Context) -> None:
        """Manage vent intent tags.

        Manage interaction intent tags available to users.
        """
        if ctx.invoked_subcommand is None:
            await self.intents_list(ctx)

    @ventset_intents.command(name="list")
    async def intents_list(self, ctx: commands.Context) -> None:
        """List configured intents.

        List all configured interaction intent profiles and boundaries.
        """
        intents = await self.config.guild(ctx.guild).intents()
        if not intents:
            await ctx.send("No intents are currently configured.")
            return

        embed = discord.Embed(
            title="Configured Vent Intents",
            color=discord.Color.teal(),
            description="Users choose one of these intents when launching an ephemeral vent channel.",
        )

        for slug, data in intents.items():
            emoji = data.get("emoji", "")
            label = data.get("label", slug)
            desc = data.get("description", "N/A")
            note = data.get("header_note", "N/A")

            embed.add_field(
                name=f"{emoji} {label} (`{slug}`)",
                value=f"• **Select Description:** {desc}\n• **Boundary Notice:** {note}",
                inline=False,
            )

        can_embed = ctx.channel.permissions_for(ctx.guild.me).embed_links
        if can_embed:
            try:
                await ctx.send(embed=embed)
                return
            except discord.Forbidden:
                pass

        # Plaintext fallback when bot lacks Embed Links permission in this channel
        lines = [
            "**📋 Configured Vent Intents**",
            "Users choose one of these intents when launching an ephemeral vent channel:",
            "",
        ]
        for slug, data in intents.items():
            emoji = data.get("emoji", "")
            label = data.get("label", slug)
            desc = data.get("description", "N/A")
            note = data.get("header_note", "N/A")
            lines.append(f"• **{emoji} {label}** (`{slug}`):")
            lines.append(f"  - *Select Description:* {desc}")
            lines.append(f"  - *Boundary Notice:* {note}")

        lines.append("")
        lines.append(f"*(Tip: Grant me 'Embed Links' permission in this channel for rich embeds.)*")

        try:
            await ctx.send("\n".join(lines))
        except discord.Forbidden:
            log.warning(
                f"Forbidden while sending intents list in guild {ctx.guild.id} channel {ctx.channel.id}"
            )

    @ventset_intents.command(name="help", aliases=["subcommands", "commands"])
    async def intents_help(self, ctx: commands.Context) -> None:
        """List intents subcommands.

        Display all available intents subcommands and their usage.
        """
        await ctx.send_help(self.ventset_intents)

    @ventset_intents.command(name="add", usage="<slug> <emoji> <label> | <header_note>")
    async def intents_add(
        self, ctx: commands.Context, slug: str, emoji: str, *, rest: str
    ) -> None:
        """Add or update an intent.

        Add or update a custom intent tag.
        Use a pipe `|` to separate the label and header note.
        Example: `[p]ventset intents add rant 🔴 Just Ranting | The author wants to vent without advice.`
        """
        clean_slug = slug.strip().lower()
        if not re.match(r"^[a-z0-9_\-]+$", clean_slug):
            await ctx.send("❌ Slug must contain only alphanumeric characters, dashes, or underscores.")
            return

        if len(clean_slug) > MAX_SLUG_LENGTH:
            await ctx.send(f"❌ Slug cannot exceed {MAX_SLUG_LENGTH} characters.")
            return

        if "|" not in rest:
            await ctx.send(
                "❌ Please separate the label and header boundary note with a pipe (`|`).\n"
                f"**Usage:** `{ctx.clean_prefix}ventset intents add <slug> <emoji> <label> | <header_note>`\n"
                f"**Example:** `{ctx.clean_prefix}ventset intents add rant 🔴 Rant Only | The author is venting only.`"
            )
            return

        label_part, note_part = rest.split("|", 1)
        clean_label = label_part.strip().strip("'\"")
        clean_note = note_part.strip().strip("'\"")

        if not clean_label:
            await ctx.send("❌ Label cannot be empty.")
            return
        if not clean_note:
            await ctx.send("❌ Header boundary note cannot be empty.")
            return

        if len(clean_label) > 100:
            await ctx.send("❌ Label cannot exceed 100 characters.")
            return
        if len(clean_note) > 1000:
            await ctx.send("❌ Header note cannot exceed 1000 characters.")
            return

        async with self.config.guild(ctx.guild).intents() as intents:
            intents[clean_slug] = {
                "emoji": emoji.strip(),
                "label": clean_label,
                "description": clean_label[:100],
                "header_note": clean_note,
            }

        await ctx.send(
            f"✅ Intent `{clean_slug}` successfully configured:\n"
            f"• **Emoji:** {emoji.strip()}\n"
            f"• **Label:** {clean_label}\n"
            f"• **Boundary Note:** {clean_note}"
        )

    @ventset_intents.command(name="remove")
    async def intents_remove(self, ctx: commands.Context, slug: str) -> None:
        """Delete an intent tag.

        Delete an intent tag by slug (minimum 1 intent required).
        """
        clean_slug = slug.strip().lower()
        intents = await self.config.guild(ctx.guild).intents()

        if clean_slug not in intents:
            await ctx.send(f"❌ Intent `{clean_slug}` does not exist.")
            return

        if len(intents) <= 1:
            await ctx.send("❌ Cannot remove this intent. At least 1 intent must remain configured.")
            return

        async with self.config.guild(ctx.guild).intents() as conf_intents:
            conf_intents.pop(clean_slug, None)

        await ctx.send(f"✅ Intent `{clean_slug}` has been removed.")

    @ventset_intents.command(name="reset")
    async def intents_reset(self, ctx: commands.Context) -> None:
        """Reset intents to presets.

        Restore configured intents to the 5 default emoji presets.
        """
        await self.config.guild(ctx.guild).intents.set(DEFAULT_INTENTS)
        await ctx.send("✅ Configured intents have been reset to the 5 default presets (🟠, 🟡, 🟢, 🔵, 🟣).")

    # -------------------------------------------------------------------------
    # Redbot End-User Data Methods (GDPR Compliance)
    # -------------------------------------------------------------------------

    async def red_get_data_for_user(self, *, user_id: int) -> Dict[str, Any]:
        """Return end user data stored for user_id."""
        user_vents = []
        all_guilds = await self.config.all_guilds()
        for guild_id, data in all_guilds.items():
            vents = data.get("active_vents", {})
            for cid_str, vent in vents.items():
                if vent.get("author_id") == user_id:
                    user_vents.append({
                        "guild_id": guild_id,
                        "channel_id": cid_str,
                        "created_at": vent.get("created_at"),
                        "intent_key": vent.get("intent_key"),
                    })
        return {"active_vents": user_vents}

    async def red_delete_data_for_user(
        self,
        *,
        requester: Literal["discord_deleted_user", "owner", "user", "user_strict"],
        user_id: int,
    ) -> None:
        """Delete end user data stored for user_id."""
        all_guilds = await self.config.all_guilds()
        for guild_id in all_guilds.keys():
            async with self.config.guild_from_id(guild_id).active_vents() as vents:
                to_remove = [
                    cid_str
                    for cid_str, vent in vents.items()
                    if vent.get("author_id") == user_id
                ]
                for cid_str in to_remove:
                    vents.pop(cid_str, None)
                    self._active_channel_ids.discard(int(cid_str))
