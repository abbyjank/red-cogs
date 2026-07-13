import asyncio
import time
from typing import Dict, Tuple

import discord
from red_commons.logging import getLogger
from redbot.core import Config, commands

log = getLogger("red.antigravity.pinhead")


class PinError(Exception):
    """Base exception class for pinning errors."""
    pass


class ChannelNotFound(PinError):
    """Raised when the target channel cannot be found."""
    pass


class MessageNotFound(PinError):
    """Raised when the target message cannot be found."""
    pass


class MissingPermissions(PinError):
    """Raised when the bot lacks permissions to pin or react."""
    pass


class AlreadyPinned(PinError):
    """Raised when the message is already pinned."""
    pass


class UnknownPinError(PinError):
    """Raised for other unexpected discord API errors."""
    pass


class PinRequestView(discord.ui.View):
    """Persistent view for pin request mod actions."""

    def __init__(self, cog: "Pinhead"):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="Approve",
        style=discord.ButtonStyle.success,
        custom_id="pinhead:approve"
    )
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Verify the user is a moderator or administrator
        if not (await self.cog.bot.is_mod(interaction.user) or 
                await self.cog.bot.is_admin(interaction.user) or 
                await self.cog.bot.is_owner(interaction.user)):
            await interaction.response.send_message(
                "You do not have permission to approve this request.",
                ephemeral=True
            )
            return

        await interaction.response.defer()

        mod_msg_id = str(interaction.message.id)
        active_requests = await self.cog.config.active_requests()
        if mod_msg_id not in active_requests:
            # Disable buttons if the request is already resolved
            for item in self.children:
                item.disabled = True
            await interaction.message.edit(view=self)
            await interaction.followup.send(
                "This request has already been handled or is no longer active.",
                ephemeral=True
            )
            return

        data = active_requests[mod_msg_id]
        channel_id = data["channel_id"]
        message_id = data["message_id"]

        try:
            await self.cog.approve_pin(channel_id, message_id, interaction.user)
            
            # Remove from active requests
            async with self.cog.config.active_requests() as reqs:
                reqs.pop(mod_msg_id, None)

            # Disable buttons and update status on the mod message
            for item in self.children:
                item.disabled = True

            embed = interaction.message.embeds[0]
            embed.color = discord.Color.green()
            embed.title = "Pin Request - Approved"
            embed.add_field(
                name="Status",
                value=f"✅ Approved by {interaction.user.mention}",
                inline=False
            )

            await interaction.message.edit(embed=embed, view=self)

        except ChannelNotFound as e:
            await interaction.followup.send(f"Failed to pin: {str(e)}", ephemeral=True)
            async with self.cog.config.active_requests() as reqs:
                reqs.pop(mod_msg_id, None)
            for item in self.children:
                item.disabled = True
            await interaction.message.edit(view=self)

        except MessageNotFound as e:
            await interaction.followup.send(f"Failed to pin: {str(e)}", ephemeral=True)
            async with self.cog.config.active_requests() as reqs:
                reqs.pop(mod_msg_id, None)
            for item in self.children:
                item.disabled = True
            await interaction.message.edit(view=self)

        except AlreadyPinned as e:
            await interaction.followup.send(f"Failed to pin: {str(e)}", ephemeral=True)
            async with self.cog.config.active_requests() as reqs:
                reqs.pop(mod_msg_id, None)
            for item in self.children:
                item.disabled = True
            await interaction.message.edit(view=self)

        except (MissingPermissions, UnknownPinError) as e:
            await interaction.followup.send(f"Failed to pin: {str(e)}", ephemeral=True)

    @discord.ui.button(
        label="Deny",
        style=discord.ButtonStyle.danger,
        custom_id="pinhead:deny"
    )
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Verify the user is a moderator or administrator
        if not (await self.cog.bot.is_mod(interaction.user) or 
                await self.cog.bot.is_admin(interaction.user) or 
                await self.cog.bot.is_owner(interaction.user)):
            await interaction.response.send_message(
                "You do not have permission to deny this request.",
                ephemeral=True
            )
            return

        await interaction.response.defer()

        mod_msg_id = str(interaction.message.id)
        active_requests = await self.cog.config.active_requests()
        if mod_msg_id not in active_requests:
            # Disable buttons if the request is already resolved
            for item in self.children:
                item.disabled = True
            await interaction.message.edit(view=self)
            await interaction.followup.send(
                "This request has already been handled or is no longer active.",
                ephemeral=True
            )
            return

        # Remove from active requests config
        async with self.cog.config.active_requests() as reqs:
            reqs.pop(mod_msg_id, None)

        # Disable buttons and update status on the mod message
        for item in self.children:
            item.disabled = True

        embed = interaction.message.embeds[0]
        embed.color = discord.Color.red()
        embed.title = "Pin Request - Denied"
        embed.add_field(
            name="Status",
            value=f"❌ Denied by {interaction.user.mention}",
            inline=False
        )

        await interaction.message.edit(embed=embed, view=self)


class Pinhead(commands.Cog):
    """
    Request message pins via emoji reactions, approved by mods.
    """

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=897451239841, force_registration=True)

        default_guild = {
            "trigger_emoji": "📌",
            "approve_emoji": "✅",
            "mod_channel": None,
            "cooldown": 60,
        }
        default_global = {
            "active_requests": {},  # mod_msg_id -> {"channel_id": int, "message_id": int}
        }
        self.config.register_guild(**default_guild)
        self.config.register_global(**default_global)

        # In-memory cooldown tracker: (guild_id, user_id) -> timestamp
        self.cooldowns: Dict[Tuple[int, int], float] = {}

    async def cog_load(self):
        # Register the persistent view so it handles button clicks after restarts
        self.bot.add_view(PinRequestView(self))

    async def approve_pin(self, channel_id: int, message_id: int, mod_user: discord.Member):
        """Add approval emoji and pin the original message."""
        channel = self.bot.get_channel(channel_id)
        if not channel:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except discord.NotFound:
                raise ChannelNotFound("The channel no longer exists.")
            except discord.HTTPException:
                raise ChannelNotFound("Failed to access the channel.")

        try:
            message = await channel.fetch_message(message_id)
        except discord.NotFound:
            raise MessageNotFound("The original message was deleted.")
        except discord.HTTPException:
            raise MessageNotFound("Failed to access the original message.")

        if message.pinned:
            raise AlreadyPinned("The message is already pinned.")

        # Check bot permissions in target channel
        me = channel.guild.me
        permissions = channel.permissions_for(me)
        if not permissions.manage_messages:
            raise MissingPermissions("I need the 'Manage Messages' permission in that channel to pin it.")
        if not permissions.add_reactions:
            raise MissingPermissions("I need the 'Add Reactions' permission in that channel to add the approval reaction.")

        # Add the approval reaction
        guild_config = self.config.guild(channel.guild)
        approve_emoji = await guild_config.approve_emoji()
        try:
            await message.add_reaction(approve_emoji)
        except discord.HTTPException as e:
            log.warning(f"Failed to add approval reaction to message {message_id}: {e}")

        # Pin the message
        try:
            await message.pin(reason=f"Pin request approved by mod: {mod_user}")
        except discord.HTTPException as e:
            raise UnknownPinError(f"Failed to pin the message: {e}")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        # Ignore non-guild reactions
        if not payload.guild_id:
            return

        # Ignore bots
        if payload.member and payload.member.bot:
            return

        guild_id = payload.guild_id
        guild_config = self.config.guild_from_id(guild_id)
        trigger_emoji = await guild_config.trigger_emoji()

        # Check if the emoji matches the configured trigger emoji
        if str(payload.emoji) != trigger_emoji:
            return

        # Check if mod channel is configured
        mod_channel_id = await guild_config.mod_channel()
        if not mod_channel_id:
            return

        # Check channel and message validity
        channel = self.bot.get_channel(payload.channel_id)
        if not channel:
            try:
                channel = await self.bot.fetch_channel(payload.channel_id)
            except discord.HTTPException:
                return

        # Ignore reactions in the mod channel itself to prevent loops/mod clutter
        if channel.id == mod_channel_id:
            return

        try:
            message = await channel.fetch_message(payload.message_id)
        except discord.HTTPException:
            return

        # If already pinned, do nothing
        if message.pinned:
            return

        # Enforce rate limit/cooldown
        cooldown = await guild_config.cooldown()
        user_id = payload.user_id
        current_time = time.time()
        last_triggered = self.cooldowns.get((guild_id, user_id), 0.0)

        if current_time - last_triggered < cooldown:
            # On cooldown, remove the trigger reaction to signal rate limit
            try:
                if payload.member:
                    await message.remove_reaction(payload.emoji, payload.member)
            except discord.HTTPException:
                pass
            return

        # Check if there is already an active request for this message
        active_requests = await self.config.active_requests()
        for mod_msg_id, data in active_requests.items():
            if data["message_id"] == message.id:
                # Already has a pending request, remove reaction
                try:
                    if payload.member:
                        await message.remove_reaction(payload.emoji, payload.member)
                except discord.HTTPException:
                    pass
                return

        # Fetch the mod channel object
        mod_channel = self.bot.get_channel(mod_channel_id)
        if not mod_channel:
            try:
                mod_channel = await self.bot.fetch_channel(mod_channel_id)
            except discord.HTTPException:
                return

        # Format message content for embed description
        content = message.content or ""
        if not content:
            if message.embeds:
                content = "*(Message contains embeds)*"
            else:
                content = "*(No text content)*"

        if len(content) > 2000:
            content = content[:1997] + "..."

        embed = discord.Embed(
            title="Pin Request",
            description=content,
            color=discord.Color.blue(),
            timestamp=message.created_at
        )
        embed.add_field(name="Author", value=message.author.mention, inline=True)

        if isinstance(channel, discord.Thread):
            channel_info = f"{channel.mention} (Thread in {channel.parent.mention})"
        else:
            channel_info = channel.mention
        embed.add_field(name="Channel", value=channel_info, inline=True)

        embed.add_field(
            name="Jump Link",
            value=f"[Go to message]({message.jump_url})",
            inline=False
        )
        
        requestor_name = payload.member.display_name if payload.member else f"User ID {user_id}"
        embed.set_footer(text=f"Requested by {requestor_name} ({user_id})")

        # Attach message image preview if available
        if message.attachments:
            for attachment in message.attachments:
                if attachment.content_type and attachment.content_type.startswith("image/"):
                    embed.set_image(url=attachment.url)
                    break

        # Send approval panel message
        view = PinRequestView(self)
        try:
            mod_msg = await mod_channel.send(embed=embed, view=view)
        except discord.HTTPException as e:
            log.error(f"Failed to send mod notification in guild {guild_id}: {e}")
            return

        # Save to active requests and update user's cooldown
        async with self.config.active_requests() as reqs:
            reqs[str(mod_msg.id)] = {"channel_id": channel.id, "message_id": message.id}
        
        self.cooldowns[(guild_id, user_id)] = current_time

    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    @commands.group(name="pinheadset")
    async def pinheadset(self, ctx: commands.Context):
        """Configure Pinhead settings."""
        pass

    @pinheadset.command(name="modchannel")
    async def set_mod_channel(self, ctx: commands.Context, channel: discord.TextChannel = None):
        """Set or clear the mod approval channel.

        Pin requests will be sent here for moderator approval.
        """
        if channel is None:
            await self.config.guild(ctx.guild).mod_channel.set(None)
            await ctx.send("Pin requests have been disabled (mod channel cleared).")
            return

        # Check bot permissions in the mod channel
        permissions = channel.permissions_for(ctx.guild.me)
        if not (permissions.send_messages and permissions.embed_links):
            await ctx.send(
                f"I need permissions to send messages and embed links in {channel.mention} first."
            )
            return

        await self.config.guild(ctx.guild).mod_channel.set(channel.id)
        await ctx.send(f"Success! Pin requests will now be sent to {channel.mention}")

    @pinheadset.command(name="trigger")
    async def set_trigger(self, ctx: commands.Context):
        """Set the trigger emoji.

        The bot will prompt you to react to a message to configure the emoji.
        """
        msg = await ctx.send(
            "Please react to **this message** within 60 seconds with the emoji you want to "
            "use as the pin request trigger."
        )

        def check(reaction, user):
            return user.id == ctx.author.id and reaction.message.id == msg.id

        try:
            reaction, user = await self.bot.wait_for("reaction_add", timeout=60.0, check=check)
        except asyncio.TimeoutError:
            await ctx.send("Timed out waiting for a reaction. Try again.")
            return

        # Verify bot can use the reaction emoji
        try:
            await msg.add_reaction(reaction.emoji)
        except discord.HTTPException:
            await ctx.send(
                "I cannot use that emoji. Please react with a standard unicode emoji or "
                "an emoji from a server I have access to."
            )
            return

        emoji_str = str(reaction.emoji)
        await self.config.guild(ctx.guild).trigger_emoji.set(emoji_str)
        await ctx.send(f"Success! The pin request trigger emoji has been set to: {emoji_str}")

    @pinheadset.command(name="approveemoji")
    async def set_approve_emoji(self, ctx: commands.Context):
        """Set the approval emoji.

        The bot will prompt you to react to a message to configure the emoji.
        """
        msg = await ctx.send(
            "Please react to **this message** within 60 seconds with the emoji you want to "
            "use as the approval reaction."
        )

        def check(reaction, user):
            return user.id == ctx.author.id and reaction.message.id == msg.id

        try:
            reaction, user = await self.bot.wait_for("reaction_add", timeout=60.0, check=check)
        except asyncio.TimeoutError:
            await ctx.send("Timed out waiting for a reaction. Try again.")
            return

        # Verify bot can use the reaction emoji
        try:
            await msg.add_reaction(reaction.emoji)
        except discord.HTTPException:
            await ctx.send(
                "I cannot use that emoji. Please react with a standard unicode emoji or "
                "an emoji from a server I have access to."
            )
            return

        emoji_str = str(reaction.emoji)
        await self.config.guild(ctx.guild).approve_emoji.set(emoji_str)
        await ctx.send(f"Success! The approved pin reaction emoji has been set to: {emoji_str}")

    @pinheadset.command(name="cooldown")
    async def set_cooldown(self, ctx: commands.Context, seconds: int):
        """Set the pin request cooldown.

        Configures the rate limit cooldown (in seconds) per user.
        """
        if seconds < 0 or seconds > 86400:
            await ctx.send("Please provide a cooldown value between 0 and 86400 seconds (24 hours).")
            return

        await self.config.guild(ctx.guild).cooldown.set(seconds)
        await ctx.send(f"Success! Cooldown has been set to {seconds} seconds.")

    @pinheadset.command(name="settings", aliases=["show", "view"])
    async def show_settings(self, ctx: commands.Context):
        """Show current Pinhead settings."""
        guild_config = self.config.guild(ctx.guild)
        trigger = await guild_config.trigger_emoji()
        approve = await guild_config.approve_emoji()
        mod_chan_id = await guild_config.mod_channel()
        cooldown = await guild_config.cooldown()

        mod_channel_mention = "Not Configured"
        if mod_chan_id:
            channel = ctx.guild.get_channel(mod_chan_id)
            if channel:
                mod_channel_mention = channel.mention
            else:
                mod_channel_mention = f"Configured channel ID {mod_chan_id} (Channel not found)"

        embed = discord.Embed(
            title="Pinhead Settings",
            color=discord.Color.blurple()
        )
        embed.add_field(name="Trigger Emoji", value=trigger, inline=True)
        embed.add_field(name="Approval Emoji", value=approve, inline=True)
        embed.add_field(name="Moderator Channel", value=mod_channel_mention, inline=True)
        embed.add_field(name="Cooldown", value=f"{cooldown} seconds", inline=True)

        await ctx.send(embed=embed)
