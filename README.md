# Abby's Red Cogs

A collection of custom and modified cogs for [Red-DiscordBot](https://github.com/Cog-Creators/Red-DiscordBot).

> [!NOTE]  
> - The `roletools` and `welcome` cogs in this repository are based on the original versions from [Trusty-cogs](https://github.com/TrustyJAID/Trusty-cogs) by TrustyJAID.
> - The `emojitracker` cog is based on the original version from [vrt-cogs](https://github.com/vertyco/vrt-cogs/tree/main/emojitracker) by vertyco.

## 📦 Included Cogs

| Cog Name | Description |
| :--- | :--- |
| **[EmojiTracker](file:///home/abusch/cogs/red-cogs/emojitracker/README.md)** | Track custom emojis in text channels and threads, with features for self-reaction counts, leaderboards, and unused/least used emojis. |
| **[RoleTools](file:///home/abusch/cogs/red-cogs/roletools/README.md)** | Advanced role utility commands. Features reaction roles, automatic roles, temporary roles, role credit costs, inclusive/exclusive role settings, required role checks, interactive buttons/dropdown select menus, and refactored sticky roles (with a guild-wide toggle and role blacklist support). |
| **[Pinhead](file:///home/abusch/cogs/red-cogs/pinhead/README.md)** | Request message pins via reactions (defaults to 📌). Requests are sent to a designated mod channel with Approve/Deny buttons. Once approved, the bot pins the message and adds a configurable approval reaction (defaults to ✅). Features per-user rate limits and persistent interactions across bot restarts. |
| **[Welcome](file:///home/abusch/cogs/red-cogs/welcome/README.md)** | Welcomes new users to the server or says goodbye when they leave. Supports custom channels, DMs, verification gating, and bot greeting roles. |
| **[EphemeralVents](file:///home/abusch/cogs/red-cogs/ephemeralvents/README.md)** | On-demand peer-support venting system generating ephemeral text channels with upfront interaction boundaries, inactivity auto-locking, and lifespan archival/deletion. |

---

## 🚀 Installation

To add this repository to your instance of Red Discord Bot:

1. Add the repository:
   ```bash
   [p]cog repo add abby-red-cogs https://github.com/abbyjank/red-cogs
   ```
2. Install the cogs you want:
   ```bash
   [p]cog install abby-red-cogs emojitracker
   ```
   ```bash
   [p]cog install abby-red-cogs roletools
   ```
   ```bash
   [p]cog install abby-red-cogs welcome
   ```
   ```bash
   [p]cog install abby-red-cogs pinhead
   ```
   ```bash
   [p]cog install abby-red-cogs ephemeralvents
   ```
3. Load the cogs:
   ```bash
   [p]cog load emojitracker
   ```
   ```bash
   [p]cog load roletools
   ```
   ```bash
   [p]cog load welcome
   ```
   ```bash
   [p]cog load pinhead
   ```
   ```bash
   [p]cog load ephemeralvents
   ```
   *(Replace `[p]` with your bot's prefix.)*