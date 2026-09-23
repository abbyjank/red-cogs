# EphemeralVents Cog

A production-ready Discord Red Bot cog providing an on-demand, peer-support venting system. Instead of static venting channels that accumulate clutter or trigger boundary crossed interactions, EphemeralVents generates structured, temporary text channels where authors select an interaction intent upfront (e.g., advice, comfort only, relate, be gentle, open).

Channels are automatically monitored and locked upon inactivity, and subsequently archived or deleted once their hard cap lifespan is reached.

---

## Features

- **Dynamic On-Demand Channels**: Ephemeral text channels created within the category of a designated `#hub_channel`.
- **Upfront Intent Boundaries**: Users pick from customizable intent profiles so responders know the exact boundaries:
  - 🟠 **Advice / Honest Opinion**: Constructive feedback and problem-solving welcome.
  - 🟡 **Comfort & Validation**: Comfort and validation only; no unsolicited advice.
  - 🟢 **Relate / Shared Experience**: Seeking solidarity and shared stories.
  - 🔵 **Be Gentle**: Author is vulnerable; extra kindness requested.
  - 🟣 **Open / Any**: Open to any constructive interaction style.
- **Active Vents Live Index**:
  - Auto-updating embed posted in `#hub_channel` directly below the launcher embed.
  - Lists all active vent channels with clickable channel mentions (`#channel-name`), topics, intent tags, status badges (`🟢 Open` vs `🔒 Locked`), and relative start times (`Started 5 minutes ago`).
  - Solves Discord's community channel-hiding behavior so members can effortlessly browse and jump into active peer-support conversations.
  - Auto-updates in real time upon channel creation, lock, manual closure, archive, deletion, or intent changes.
- **Persistent Discord UI**:
  - **Launcher**: Persistent `Start a Vent` button in `#hub_channel`.
  - **Modal**: Optional brief topic/title input (max 30 characters).
  - **Dynamic Select Menu**: Intent selection dropdown dynamically populated from guild configuration.
  - **In-Channel Controls**: Persistent `Close Vent` button pinned in channel for the author and moderators.
  - **Archived Channel Controls**: Persistent `Delete Vent Channel` button for moderators.
- **Channel Naming & Sanitization**:
  - Automatically formats channel names to lowercase, alphanumeric characters, and hyphens (e.g. `vent-🟡-rough-day`).
  - Fallbacks to author display name or `vent` if omitted (e.g. `vent-🟡-abby` or `vent-🟡-vent`).
  - Safely caps total length below Discord's 100-character limit.
- **Permission Syncing & Security**:
  - Inherits parent category overwrites while guaranteeing `@everyone` has `View Channel` and `Send Messages`.
  - Configured moderator role and the bot are granted full moderation and visibility permissions.
- **Lifecycle & Background Automation (`tasks.loop`)**:
  - **Activity Tracking**: Tracks human activity in active channels via `on_message`.
  - **Inactivity Lock**: Locks `@everyone` (`send_messages=False`) and posts a notice when a channel reaches the inactivity duration (default: 12 hours).
  - **Lifespan Hard Cap**: Once locked, transitions channel according to `post_action` after the hard cap duration (default: 24 hours).
  - **Archival or Deletion**:
    - `archive`: Renames channel to an archived prefix (e.g. `vent-🟡-abby` becomes `📦-abby`), hides channel from `@everyone` (`view_channel=False`), grants read-only access to moderators, optionally moves to an archive category, and posts a moderator deletion button.
    - `delete`: Permanently deletes the channel and prunes configuration metadata.
- **Manual Closure**:
  - Clicking `Close Vent` immediately locks the channel and triggers the configured post-action (archive or delete).
- **GDPR Compliant**: Implements Red's end-user data handling protocols (`red_get_data_for_user`, `red_delete_data_for_user`).

---

## Commands

All administrative settings are managed under the `[p]ventset` command group, restricted to users with `Manage Server` permissions or bot administrators.

| Command | Description |
| :--- | :--- |
| `[p]ventset` / `[p]ventset show` | Display current EphemeralVents configuration, live index status, and active vent count. |
| `[p]ventset help` (aliases: `commands`, `subcommands`) | Display help and list all available `ventset` subcommands and their usage. |
| `[p]ventset channel [#channel]` | Set the vent hub launcher channel, post the launcher and index embeds (or clear if no channel given). |
| `[p]ventset index [repost=False]` (alias: `refresh`) | Refresh or repost the active vents live index embed in the configured hub channel. |
| `[p]ventset modrole [@role]` | Set or clear the moderator role for vent oversight and archive access. |
| `[p]ventset archivecategory [category]` | Set or clear an optional category to move archived vent channels into. |
| `[p]ventset archiveemoji [emoji]` | Set or reset the prefix emoji used when renaming archived channels (default: `📦`). |
| `[p]ventset timeouts <inactivity_hours> <lifespan_hours>` | Set the inactivity lock and hard cap lifespan durations (default: `12` and `24`). |
| `[p]ventset action <archive\|delete>` | Toggle post-expiration action between `archive` and `delete`. |
| `[p]ventset crisis [text]` | View current crisis text (bare command), update text, restore default (`reset`), or disable/remove (`off`/`clear`). |
| `[p]ventset intents list` | List all configured intent presets, emojis, and boundary notes. |
| `[p]ventset intents add <slug> <emoji> <label> \| <header_note>` | Add or update a custom intent (e.g. `rant 🔴 Rant Only \| No advice wanted.`). |
| `[p]ventset intents remove <slug>` | Remove an intent profile (minimum 1 intent required). |
| `[p]ventset intents reset` | Reset intents back to the 5 default emoji presets (🟠, 🟡, 🟢, 🔵, 🟣). |

---

## Permissions Required

The bot requires the following permissions in the server / category:
- **Manage Channels**: To create, lock, move, and delete vent channels.
- **Manage Roles / Permissions**: To set channel overwrites for `@everyone` and moderator roles.
- **Manage Messages**: To pin opening boundary embeds and clean up pin notification messages.
- **View Channel & Send Messages**: To operate inside the hub and vent channels.
- **Embed Links & Read Message History**: To render control panels and track channel activity.
