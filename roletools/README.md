# RoleTools Cog

> [!NOTE]  
> This cog is based on the original `roletools` cog from [Trusty-cogs](https://github.com/TrustyJAID/Trusty-cogs) by TrustyJAID.

RoleTools is a feature-rich, highly configurable role management utility cog for Red Discord Bots. It supports self-assignable roles, automatic roles, temporary roles, reaction roles, role costs, role exclusivity, requirements, interactive buttons, select menus, and sticky roles.

---

## 📋 Table of Contents
1. [Base Commands](#-base-commands)
2. [Role Settings](#-role-settings)
3. [Reaction Roles](#-reaction-roles)
4. [Role Requirements](#-role-requirements)
5. [Inclusive & Exclusive Roles](#-inclusive--exclusive-roles)
6. [Buttons & Select Menus](#-buttons--select-menus)
7. [Temporary Roles](#-temporary-roles)
8. [Role Messages](#-role-messages)

---

## 🛠️ Command Documentation

### ⚙️ Base Commands
These are the general utility commands for managing and viewing roles.

* **`[p]roletools selfrole <role>`**  
  Add or remove a defined self-role. If you already have the role, it will be removed.
  * **`[p]roletools selfrole add <role>`**: Gives yourself the designated role.
  * **`[p]roletools selfrole remove <role>`**: Removes the designated role from yourself.
* **`[p]roletools giverole <role> [who...]`**  
  Gives a role to designated members. Targets can include members, roles, text/voice channels, or terms like `everyone`, `here`, `bots`, or `humans`.
* **`[p]roletools removerole <role> [who...]`**  
  Removes a role from designated members. Targets can include members, roles, text/voice channels, or terms like `everyone`, `here`, `bots`, or `humans`.
* **`[p]roletools forcerole <users> <role>`**  
  Force a sticky role on one or more users (works by ID or mention).
* **`[p]roletools forceroleremove <users> <role>`**  
  Force remove a sticky role on one or more users (works by ID or mention).
* **`[p]roletools viewroles [role]`** (alias: `viewrole`)  
  View current RoleTools setup for roles in the server in an interactive menu.

---

### ⚙️ Role Settings
Configure global options, toggles, and behaviors for roles.

* **`[p]roletools sticky [true_or_false]`**  
  Toggle or display the guild-wide sticky role status (reassign roles when a user leaves and rejoins).
* **`[p]roletools sticky blacklist`**  
  Manage the roles excluded from the sticky role reassignments.
  * **`[p]roletools sticky blacklist add <role>`**: Add a role to the sticky role blacklist.
  * **`[p]roletools sticky blacklist remove <role>`** (alias: `delete`): Remove a role from the blacklist.
  * **`[p]roletools sticky blacklist list`**: List all blacklisted roles.
* **`[p]roletools autorole <true_or_false> <role>`** (alias: `auto`)  
  Toggle whether a role is automatically given to new users upon joining.
* **`[p]roletools selfassignable <true_or_false> <role>`** (aliases: `selfadd`, `selfassign`)  
  Toggle if a role can be self-assigned by users.
* **`[p]roletools selfremovable <true_or_false> <role>`** (alias: `selfrem`)  
  Toggle if a role can be removed from oneself.
* **`[p]roletools cost <cost> <role>`**  
  Set the cost in bot currency credits to acquire a role. Set to `0` or less to disable.
* **`[p]roletools atomic [true_or_false|clear]`**  
  Set role assignment atomicity for the server (when `True`, roles are assigned individually; when `False`, they are grouped to prevent rate-limiting). Use `clear` to fallback to global rules.
* **`[p]roletools globalatomic [true_or_false]`**  
  Set the global default atomicity of role assignment (Bot Owner only).

---

### 🎭 Reaction Roles
Create and manage emoji reaction roles.

* **`[p]roletools reaction`** (aliases: `react`, `reactions`)  
  Base group for reaction role commands.
  * **`[p]roletools reaction create <message> <emoji> <role>`** (aliases: `make`, `setup`): Add a reaction role to a message.
  * **`[p]roletools reaction remove <message> <role_or_emoji>`** (alias: `rem`): Remove a reaction role from a message.
  * **`[p]roletools reaction bulk <message> [role_emoji...]`** (aliases: `bulkcreate`, `bulkmake`): Add multiple reaction roles to a single message at once.
  * **`[p]roletools reaction list`** (aliases: `reactionroles`, `reactrole`): List all registered reaction roles.
  * **`[p]roletools reaction clearreact <message> [emojis...]`** (alias: `clearreacts`): Remove all or specific reaction roles from a message.
  * **`[p]roletools reaction cleanup`**: Cleanup stale reaction roles (for deleted roles/channels/messages).
  * **`[p]roletools reaction ownercleanup`**: Perform a bot-wide cleanup of reaction roles (Bot Owner only).

---

### 🛑 Role Requirements
Restrict role acquisition based on the user's current roles.

* **`[p]roletools required`** (aliases: `requires`, `require`, `req`)  
  Base group for required role commands.
  * **`[p]roletools required add <role> <required_roles...>`**: Add one or more roles that a user must have to acquire the target `<role>`.
  * **`[p]roletools required remove <role> <required_roles...>`**: Remove requirement roles.
  * **`[p]roletools required any <role> [true_or_false]`**: If set to `True`, the user only needs *any one* of the required roles, rather than *all* of them.

---

### 🔄 Inclusive & Exclusive Roles
Manage automatic chains or exclusions when assigning roles.

* **`[p]roletools include`** (alias: `inclusive`)  
  Base group for inclusive roles.
  * **`[p]roletools include add <role> <inclusive_roles...>`**: Automatically add inclusive roles when a user gains `<role>`.
  * **`[p]roletools include mutual <roles...>`**: Make a set of roles mutually inclusive to each other.
  * **`[p]roletools include remove <role> <inclusive_roles...>`**: Remove inclusive role rules.
* **`[p]roletools exclude`** (alias: `exclusive`)  
  Base group for exclusive roles.
  * **`[p]roletools exclude add <role> <exclusive_roles...>`**: Automatically remove exclusive roles when a user gains `<role>`.
  * **`[p]roletools exclude mutual <roles...>`**: Make a set of roles mutually exclusive to each other.
  * **`[p]roletools exclude remove <role> <exclusive_roles...>`**: Remove exclusive role rules.

---

### 🔘 Buttons & Select Menus
Setup interactive components (buttons and dropdown menus) for assigning roles.

* **`[p]roletools buttons`** (alias: `button`)  
  Base group for interactive button management.
  * **`[p]roletools buttons create <name> <role> [extras]`**: Create a role button config. Customizations like labels, emojis, styles, and custom success messages are supported in `extras`.
  * **`[p]roletools buttons delete <name>`** (aliases: `del`, `remove`): Delete a button config.
  * **`[p]roletools buttons view`**: View all buttons registered in the server.
  * **`[p]roletools buttons cleanup`**: Clean up buttons for deleted roles.
* **`[p]roletools select`** (alias: `selects`)  
  Base group for select menus.
  * **`[p]roletools select create <name> <options...> [extras]`**: Create a select dropdown menu.
  * **`[p]roletools select delete <name>`** (aliases: `del`, `remove`): Delete a select menu.
  * **`[p]roletools select createoption <name> <role> [extras]`** (alias: `addoption`): Create a select option that can be added to menus.
  * **`[p]roletools select deleteoption <name>`** (aliases: `deloption`, `removeoption`, `remoption`): Delete a select option.
  * **`[p]roletools select view`** (alias: `list`): View all dropdown menus in the server.
  * **`[p]roletools select viewoptions`** (alias: `listoptions`): View all individual options.
  * **`[p]roletools select cleanup`**: Clean up select menus and options for deleted roles.

---

### ⏳ Temporary Roles
Assign roles that automatically expire after a specified duration.

* **`[p]roletools temporary`** (alias: `temp`)  
  Base group for temporary role commands.
  * **`[p]roletools temporary set <role> <duration>`**: Set a role to expire and be removed after a duration (e.g. `2d`, `12h`, `30m`).
  * **`[p]roletools temporary list`**: List all users who currently have temporary roles and their time remaining.

---

### ✉️ Role Messages
Send interactive messages containing buttons or select menus.

* **`[p]roletools message`**  
  Base group for sending messages with interactive components.
  * **`[p]roletools message send <channel> <buttons...> <menus...> [text]`**: Send a message with the specified buttons and dropdown menus.
  * **`[p]roletools message edit <message> <buttons...> <menus...>`**: Edit an existing message to have the specified buttons and menus.
  * **`[p]roletools message sendselect <channel> <menus...> [text]`**: Send a message with only select menus.
  * **`[p]roletools message editselect <message> <menus...>`**: Edit an existing message to have only select menus.
  * **`[p]roletools message sendbutton <channel> <buttons...> [text]`**: Send a message with only buttons.
  * **`[p]roletools message editbutton <message> <buttons...>`**: Edit an existing message to have only buttons.
