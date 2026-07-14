# Pinhead Cog

A Discord Red Bot cog that allows users to request message pins via emoji reactions. Requests are routed to a moderator approval channel where moderators can approve, deny, warn, or block requests using buttons on a custom embed panel.

## Features

- **Emoji-Triggered Pin Requests**: Users can react to any message in channels or forum threads with a specific emoji (defaults to `📌`) to request a pin.
- **Reaction Prompt Configuration**: Admins configure the trigger and approval emojis by reacting directly to the bot's prompt messages.
- **Mod Approval Panel**: Requests send a rich embed panel to a designated moderator channel.
  - Includes jump links, channel/thread details, original author, message content, and images.
  - Features Discord UI Buttons (`Approve`, `Deny`, `Warn`, and `Block`) for instant moderator actions.
- **Auto-Reaction & Pinning**: Upon approval, the bot adds the configured approval emoji (defaults to `✅`) to the original message and pins it.
- **Denial Cleanup**: If a request is denied (via `Deny`, `Warn`, or `Block` buttons), the bot removes the original user's trigger reaction and adds the message to a list of denied messages to prevent future requests on it.
- **Abuse Prevention (Warning & Blocking)**: 
  - **Warn**: Denies the request and sends a customizable warning DM to the requestor.
  - **Block**: Denies the request, sends a customizable block notification DM to the requestor, and blocks them from making future pin requests.
- **Rate Limiting**: Configurable rate limit (cooldown) per user per guild to prevent reaction spam.
- **Persistent Interactions**: Button views are persistent and will continue working even after bot restarts.
- **Robust Verification**: Checks channel/message presence, permissions, block status, and duplicate request states to prevent errors.

## Commands

All settings are configured using the `[p]pinheadset` command group. This group is restricted to users with Red Administrator roles or server management permissions.

- `[p]pinheadset settings` (aliases: `show`, `view`): Display the current settings for the server.
- `[p]pinheadset modchannel [channel]`: Set the text channel where pin requests will be sent for moderator approval. Pass no channel to disable pin requests.
- `[p]pinheadset trigger`: Prompt to react and change the trigger emoji.
- `[p]pinheadset approveemoji`: Prompt to react and change the approval emoji.
- `[p]pinheadset cooldown <seconds>`: Set the cooldown duration (in seconds) per user to request pins (default is `60`).
- `[p]pinheadset warnmsg [message]`: Set the DM warning message. Reset to default if left empty.
- `[p]pinheadset blockmsg [message]`: Set the DM block message. Reset to default if left empty.
- `[p]pinheadset block add <user>`: Block a user from requesting pins.
- `[p]pinheadset block remove <user>` (aliases: `delete`, `del`): Unblock a user.
- `[p]pinheadset block list`: List all currently blocked users in the server.

## Permissions

- **Configuration**: Only admins can run the `[p]pinheadset` commands.
- **Approving/Denying/Moderating**: Only users recognized by Red as moderators or administrators (or the bot owner) can click the approval panel buttons.
- **Bot Permissions**: The bot needs the following permissions:
  - `Manage Messages` in the target channel to pin messages and manage reactions.
  - `Add Reactions` in the target channel to add the approval reaction.
  - `Send Messages` and `Embed Links` in the moderator channel.
