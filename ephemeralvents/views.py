"""Discord UI Views and Modals for EphemeralVents cog."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Dict, Optional

import discord

from .constants import (
    CLOSE_BUTTON_ID,
    DELETE_BUTTON_ID,
    LEGACY_DELETE_BUTTON_ID,
    LAUNCHER_BUTTON_ID,
    MAX_TOPIC_LENGTH,
)

if TYPE_CHECKING:
    from .ephemeralvents import EphemeralVents

log = logging.getLogger("red.antigravity.ephemeralvents.views")


class VentLauncherView(discord.ui.View):
    """Persistent view placed on the vent hub launcher message."""

    def __init__(self, cog: EphemeralVents) -> None:
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="Start a Vent",
        style=discord.ButtonStyle.primary,
        emoji="🌱",
        custom_id=LAUNCHER_BUTTON_ID,
    )
    async def start_vent_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Handle user clicking 'Start a Vent'."""
        guild = interaction.guild
        if not guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "This action can only be used inside a server.",
                ephemeral=True,
            )
            return

        # Check bot permissions in guild
        if not guild.me.guild_permissions.manage_channels:
            await interaction.response.send_message(
                "I do not have the 'Manage Channels' permission to create a vent channel.",
                ephemeral=True,
            )
            return

        # Rate limit: 1 active vent per user
        has_active, existing_channel = await self.cog.check_user_vent_rate_limit(
            guild, interaction.user
        )
        if has_active:
            mention_text = (
                f": {existing_channel.mention}" if existing_channel else "."
            )
            await interaction.response.send_message(
                f"You already have an active vent channel{mention_text} "
                "Please close your current vent before opening a new one.",
                ephemeral=True,
            )
            return

        modal = VentTopicModal(self.cog)
        await interaction.response.send_modal(modal)


class VentTopicModal(discord.ui.Modal, title="Start a Vent"):
    """Modal prompting the user for an optional topic/title."""

    def __init__(self, cog: EphemeralVents) -> None:
        super().__init__(timeout=300.0)
        self.cog = cog

    topic_input = discord.ui.TextInput(
        label="Topic / Title",
        placeholder="Brief topic (optional, but encouraged to help others understand)",
        required=False,
        max_length=MAX_TOPIC_LENGTH,
        style=discord.TextStyle.short,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Handle modal submission by prompting intent selection."""
        guild = interaction.guild
        if not guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "This interaction can only be completed inside a server.",
                ephemeral=True,
            )
            return

        # Re-check rate limit in case of rapid submissions
        has_active, existing_channel = await self.cog.check_user_vent_rate_limit(
            guild, interaction.user
        )
        if has_active:
            mention_text = (
                f": {existing_channel.mention}" if existing_channel else "."
            )
            await interaction.response.send_message(
                f"You already have an active vent channel{mention_text} "
                "Please close your current vent before opening a new one.",
                ephemeral=True,
            )
            return

        raw_topic = self.topic_input.value or ""
        clean_topic = raw_topic.strip()

        # Fetch guild's configured intents
        intents: Dict[str, Dict[str, str]] = await self.cog.config.guild(guild).intents()
        if not intents:
            from .constants import DEFAULT_INTENTS
            intents = DEFAULT_INTENTS

        view = IntentSelectView(self.cog, topic=clean_topic, intents=intents)
        await interaction.response.send_message(
            "Please select your interaction intent below to create your vent channel:",
            view=view,
            ephemeral=True,
        )


class IntentSelect(discord.ui.Select):
    """Dynamic select menu populated from the guild's configured intents."""

    def __init__(
        self,
        cog: EphemeralVents,
        topic: str,
        intents: Dict[str, Dict[str, str]],
    ) -> None:
        self.cog = cog
        self.topic = topic
        self.intents = intents

        options = []
        for slug, data in intents.items():
            label = data.get("label", slug)[:100]
            description = data.get("description", "")[:100]
            emoji_str = data.get("emoji")

            opt = discord.SelectOption(
                label=label,
                value=slug,
                description=description if description else None,
                emoji=emoji_str if emoji_str else None,
            )
            options.append(opt)

        super().__init__(
            placeholder="Choose an interaction intent style...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle intent selection and trigger channel creation."""
        guild = interaction.guild
        if not guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "This action can only be completed inside a server.",
                ephemeral=True,
            )
            return

        # Disable select menu to prevent duplicate clicks
        self.disabled = True
        if self.view:
            for item in self.view.children:
                if isinstance(item, discord.ui.Select):
                    item.disabled = True
            await interaction.response.edit_message(
                content="⏳ Creating your vent channel...",
                view=self.view,
            )
        else:
            await interaction.response.defer(ephemeral=True)

        selected_slug = self.values[0]

        try:
            channel = await self.cog.create_vent_channel(
                guild=guild,
                author=interaction.user,
                intent_key=selected_slug,
                topic=self.topic,
            )
            await interaction.edit_original_response(
                content=f"✅ Your vent channel has been created: {channel.mention}",
                view=None,
            )
        except discord.Forbidden as e:
            log.warning(f"Forbidden while creating vent channel in guild {guild.id}: {e}")
            await interaction.edit_original_response(
                content="❌ Failed to create vent channel: Missing permissions (Manage Channels or Manage Roles).",
                view=None,
            )
        except Exception as e:
            log.exception(f"Unexpected error while creating vent channel in guild {guild.id}")
            await interaction.edit_original_response(
                content=f"❌ An error occurred while creating your vent channel: {e}",
                view=None,
            )


class IntentSelectView(discord.ui.View):
    """Temporary ephemeral view containing the intent select menu."""

    def __init__(
        self,
        cog: EphemeralVents,
        topic: str,
        intents: Dict[str, Dict[str, str]],
    ) -> None:
        super().__init__(timeout=300.0)
        self.cog = cog
        self.topic = topic
        self.intents = intents
        self.select_menu = IntentSelect(cog=cog, topic=topic, intents=intents)
        self.add_item(self.select_menu)

    async def on_timeout(self) -> None:
        """Disable select menu when timed out."""
        self.select_menu.disabled = True


class CloseVentView(discord.ui.View):
    """Persistent view pinned in vent channel to allow author or mods to close it."""

    def __init__(self, cog: EphemeralVents) -> None:
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="Close Vent",
        style=discord.ButtonStyle.danger,
        emoji="🔒",
        custom_id=CLOSE_BUTTON_ID,
    )
    async def close_vent_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Handle user clicking 'Close Vent'."""
        guild = interaction.guild
        channel = interaction.channel
        if (
            not guild
            or not isinstance(interaction.user, discord.Member)
            or not isinstance(channel, discord.TextChannel)
        ):
            await interaction.response.send_message(
                "This action can only be executed in a guild text channel.",
                ephemeral=True,
            )
            return

        can_close = await self.cog.can_close_vent(guild, interaction.user, channel)
        if not can_close:
            await interaction.response.send_message(
                "Only the vent author or moderators can close this vent.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()
        await self.cog.close_vent_channel(channel, closed_by=interaction.user)


class ArchivedVentView(discord.ui.View):
    """Persistent view posted in archived vent channels for moderator deletion."""

    def __init__(self, cog: EphemeralVents) -> None:
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="Delete Vent Channel",
        style=discord.ButtonStyle.danger,
        emoji="🗑️",
        custom_id=DELETE_BUTTON_ID,
    )
    async def delete_channel_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Handle moderator clicking 'Delete Vent Channel'."""
        guild = interaction.guild
        channel = interaction.channel
        if (
            not guild
            or not isinstance(interaction.user, discord.Member)
            or not isinstance(channel, discord.TextChannel)
        ):
            await interaction.response.send_message(
                "This action can only be executed in a guild text channel.",
                ephemeral=True,
            )
            return

        can_moderate = await self.cog.can_moderate_vent(guild, interaction.user, channel)
        if not can_moderate:
            await interaction.response.send_message(
                "Only moderators can delete this archived vent channel.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            "Deleting vent channel...",
            ephemeral=True,
        )
        await self.cog.delete_vent_channel(
            channel,
            reason=f"Archived vent deleted by moderator {interaction.user} ({interaction.user.id})",
        )


class LegacyArchivedVentView(discord.ui.View):
    """Persistent view supporting the legacy DELETE_BUTTON_ID for backward compatibility."""

    def __init__(self, cog: EphemeralVents) -> None:
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="Delete Vent Channel",
        style=discord.ButtonStyle.danger,
        emoji="🗑️",
        custom_id=LEGACY_DELETE_BUTTON_ID,
    )
    async def legacy_delete_channel_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Handle legacy delete button interaction."""
        guild = interaction.guild
        channel = interaction.channel
        if (
            not guild
            or not isinstance(interaction.user, discord.Member)
            or not isinstance(channel, discord.TextChannel)
        ):
            await interaction.response.send_message(
                "This action can only be executed in a guild text channel.",
                ephemeral=True,
            )
            return

        can_moderate = await self.cog.can_moderate_vent(guild, interaction.user, channel)
        if not can_moderate:
            await interaction.response.send_message(
                "Only moderators can delete this archived vent channel.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            "Deleting vent channel...",
            ephemeral=True,
        )
        await self.cog.delete_vent_channel(
            channel,
            reason=f"Archived vent deleted by moderator {interaction.user} ({interaction.user.id})",
        )
