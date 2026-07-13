# Pinhead Cog

A Discord Red Bot cog that allows users to request message pins via emoji reactions. Requests are routed to a moderator approval channel where moderators can approve or deny requests using buttons on a custom embed panel.

## Features

- **Emoji-Triggered Pin Requests**: Users can react to any message in channels or forum threads with a specific emoji (defaults to `📌`) to request a pin.
- **Reaction Prompt Configuration**: Admins configure the trigger and approval emojis by reacting directly to the bot's prompt messages.
- **Mod Approval Panel**: Requests send a rich embed panel to a designated moderator channel.
  - Includes jump links, channel/thread details, original author, message content, and images.
  - Features Discord UI Buttons (`Approve` / `Deny`) for instant actions.
- **Auto-Reaction & Pinning**: Upon approval, the bot adds the configured approval emoji (defaults to `✅`) to the original message and pins it.
- **Rate Limiting**: Configurable rate limit (cooldown) per user per guild to prevent reaction spam.
- **Persistent Interactions**: Button views are persistent and will continue working even after bot restarts.
- **Robust Verification**: Checks channel/message presence, permissions, and duplicate request states to prevent errors.

## Commands

All settings are configured using the `[p]pinheadset` command group. This group is restricted to users with Red Administrator roles or server management permissions.

- `[p]pinheadset settings` (aliases: `show`, `view`): Display the current settings for the server.
- `[p]pinheadset modchannel [channel]`: Set the text channel where pin requests will be sent for moderator approval. Pass no channel to disable pin requests.
- `[p]pinheadset trigger`: Prompt to react and change the trigger emoji.
- `[p]pinheadset approveemoji`: Prompt to react and change the approval emoji.
- `[p]pinheadset cooldown <seconds>`: Set the cooldown duration (in seconds) per user to request pins (default is `60`).

## Permissions

- **Configuration**: Only admins can run the `[p]pinheadset` commands.
- **Approving/Denying**: Only users recognized by Red as moderators or administrators (or the bot owner) can click the `Approve` or `Deny` buttons.
- **Bot Permissions**: The bot needs the following permissions:
  - `Manage Messages` in the target channel to pin messages.
  - `Add Reactions` in the target channel to add the approval reaction.
  - `Send Messages` and `Embed Links` in the moderator channel.
