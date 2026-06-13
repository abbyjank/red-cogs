# Welcome Cog

A Red Discord Bot cog that welcomes new members and says goodbye to those who leave. It supports channel messages, direct message (DM/whisper) greetings (with separate custom messages), embed messages, role assignment for bots, verification pending gates, and more.

## Features
* **Channel Welcomes & Goodbyes:** Custom messages sent to defined channels.
* **DM Welcomes (Whispers):** Welcome users directly in their DMs, either instead of or in addition to the channel welcome.
* **DM-Specific Messages:** Configure separate welcome messages for DM sends and channel sends.
* **Embed Customization:** Create rich embeds for both greeting and goodbye messages (custom colors, titles, footers, thumbnails, icons, and main images).
* **Bot Customizations:** Assign roles automatically to newly joined bots and define custom bot-only messages.
* **Onboarding Guard:** Delay greetings until a user completes verification/onboarding.
* **Group Greetings:** Minimize spam by grouping greetings if many users join at once.

---

## Message Formatting Variables
You can use the following variables in your greeting, goodbye, and embed text:
* `{0}` or `{0.name}`: The member's username.
* `{0.mention}`: Mention the member.
* `{0.id}`: The member's Discord ID.
* `{1}` or `{1.name}`: The guild/server name.
* `{count}`: The number of users who have joined the guild today.

---

## Commands

Use `[p]welcomeset` to manage the cog settings. All commands require administrator permissions or the `manage_channels` permission.

### Base Command & Settings
* `[p]welcomeset settings`  
  Shows the server's current welcome, goodbye, DM, and bot configuration settings.

### Whisper / DM Greetings
* `[p]welcomeset whisper [choice]`  
  Sets whether or not a DM is sent to the new user.  
  * **Choices:** `off` (turn off DMs), `only` (only DM, no channel message), `both` (send both DM and channel message).  
  * If no option is specified, toggles between `off` and `only`.
* `[p]welcomeset whisper add <format_msg>`  
  Adds a DM-specific welcome message format to be chosen at random.
* `[p]welcomeset whisper list` (Aliases: `edit`, `delete`, `del`)  
  Lists all DM-specific greetings. Shows an interactive menu to edit or delete existing messages.

### Channel Greetings
* `[p]welcomeset greeting toggle`  
  Turns on/off welcoming new users to the guild.
* `[p]welcomeset greeting channel <channel>`  
  Sets the channel to send greeting messages to.
* `[p]welcomeset greeting add <format_msg>`  
  Adds a channel welcome message format to be chosen at random.
* `[p]welcomeset greeting list` (Aliases: `edit`, `delete`, `del`)  
  Lists all channel greetings. Shows an interactive menu to edit or delete existing messages.
* `[p]welcomeset greeting allowedmentions <set_to> <allowed...>`  
  Configures the bot's allowed mentions for greetings. Set `set_to` to `True` or `False` for `users`, `roles`, or `everyone`.
* `[p]welcomeset greeting grouped <grouped>`  
  Set to `True` to group greetings when multiple users join in a short period (resets daily).
* `[p]welcomeset greeting pending <wait_for_pending>`  
  If set to `True`, waits for the user to pass the server verification screen or onboarding process before sending the welcome message.
* `[p]welcomeset greeting deleteprevious`  
  Toggles whether the bot deletes the previous welcome message when a new member joins to reduce channel clutter.
* `[p]welcomeset greeting deleteafter [delete_after]`  
  Automatically deletes welcome messages after the specified number of seconds. Provide no input to disable deletion.
* `[p]welcomeset greeting minimumage <days>`  
  Sets the minimum age of the account (in days) required to trigger the welcome greeting. Set to `0` to disable.
* `[p]welcomeset greeting filter [replacement]`  
  Defines what to do if a username matches the core filter. If a replacement is provided, replaces matches with it. If left blank, does not post greetings for matching usernames.
* `[p]welcomeset greeting test`  
  Sends a temporary test greeting message (deleted after 60 seconds).

### Channel Goodbyes
* `[p]welcomeset goodbye toggle`  
  Turns on/off saying goodbye to members leaving the guild.
* `[p]welcomeset goodbye channel <channel>`  
  Sets the channel to send goodbye messages to.
* `[p]welcomeset goodbye add <format_msg>`  
  Adds a goodbye message format to be chosen at random.
* `[p]welcomeset goodbye list` (Aliases: `edit`, `delete`, `del`)  
  Lists all goodbye messages. Shows an interactive menu to edit or delete existing messages.
* `[p]welcomeset goodbye allowedmentions <set_to> <allowed...>`  
  Configures the bot's allowed mentions for goodbye messages.
* `[p]welcomeset goodbye deleteprevious`  
  Toggles whether the bot deletes the previous goodbye message when a member leaves.
* `[p]welcomeset goodbye deleteafter [delete_after]`  
  Automatically deletes goodbye messages after the specified number of seconds.
* `[p]welcomeset goodbye test`  
  Sends a temporary test goodbye message (deleted after 60 seconds).

### Bot Welcome Settings
* `[p]welcomeset bot msg [format_msg]`  
  Sets the greeting message for bots. Leave blank to treat bots as regular users.
* `[p]welcomeset bot goodbyemsg [format_msg]`  
  Sets the goodbye message for bots. Leave blank to treat bots as regular users.
* `[p]welcomeset bot role [role]`  
  Assigns a specific role to bots when they join. Leave blank to disable.
* `[p]welcomeset bot test`  
  Tests the bot join message flow.

### Embed Configuration
* `[p]welcomeset embed toggle`  
  Toggles whether greeting/goodbye messages are sent as rich embeds.
* `[p]welcomeset embed colour <colour>` (Alias: `color`)  
  Sets the greeting embed color. Accepts hex codes or integer values.
* `[p]welcomeset embed goodbyecolour <colour>` (Aliases: `gcolor`, `goodbyecolor`, `gcolour`)  
  Sets the goodbye embed color.
* `[p]welcomeset embed title [title]`  
  Sets the embed title. Supports formatting variables.
* `[p]welcomeset embed footer [footer]`  
  Sets the embed footer. Supports formatting variables.
* `[p]welcomeset embed thumbnail [link]`  
  Sets the embed thumbnail image. Options include an image URL, or `avatar`, `server` (guild icon), or `splash`.
* `[p]welcomeset embed icon [link]`  
  Sets the embed author icon. Options include an image URL, or `avatar`, `server`, or `splash`.
* `[p]welcomeset embed image greeting [link]`  
  Sets the large image for greeting embeds.
* `[p]welcomeset embed image goodbye [link]`  
  Sets the large image for goodbye embeds.
* `[p]welcomeset embed timestamp`  
  Toggles whether a timestamp is displayed in embeds.
* `[p]welcomeset embed author`  
  Toggles whether the user's name and avatar are placed in the author field of the embed.
* `[p]welcomeset embed mention`  
  Toggles whether to mention the user outside of the embed to trigger a notification badge.
