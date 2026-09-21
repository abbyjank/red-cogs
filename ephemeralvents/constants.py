"""Constants and default configuration for EphemeralVents cog."""

from typing import Any, Dict
import discord

DEFAULT_INTENTS: Dict[str, Dict[str, str]] = {
    "advice": {
        "emoji": "🟠",
        "label": "Advice / Honest Opinion",
        "description": "Looking for constructive advice and honest thoughts.",
        "header_note": "The author is actively seeking advice and solutions. Constructive feedback is welcome.",
    },
    "comfort": {
        "emoji": "🟡",
        "label": "Comfort & Validation",
        "description": "Just looking for comfort and validation.",
        "header_note": "The author is looking for comfort and validation only. Please refrain from giving advice or problem-solving.",
    },
    "relate": {
        "emoji": "🟢",
        "label": "Relate / Shared Experience",
        "description": "Looking to hear from others who have gone through this.",
        "header_note": "The author is looking for shared experiences and solidarity. Feel free to share similar situations.",
    },
    "gentle": {
        "emoji": "🔵",
        "label": "Be Gentle",
        "description": "Feeling fragile or unstable; please handle with care.",
        "header_note": "The author is feeling vulnerable. Please be mindful, gentle, and considerate in your replies.",
    },
    "open": {
        "emoji": "🟣",
        "label": "Open / Any",
        "description": "No preference on interaction style.",
        "header_note": "The author is open to any constructive interaction, whether advice, comfort, or discussion.",
    },
}

DEFAULT_CRISIS_HEADER: str = (
    "If you or someone you know is going through a crisis or in immediate danger, please reach out to professional resources:\n"
    "• **US & Canada:** Call or text **988** (Suicide & Crisis Lifeline)\n"
    "• **Crisis Text Line:** Text **HOME** to **741741**\n"
    "• **UK:** Call **111** (NHS) or **0800 689 5652** (National Suicide Prevention)\n"
    "• **International:** Find resources at [Find A Helpline](https://findahelpline.com/) and [Befrienders Worldwide](https://www.befrienders.org/)\n\n"
    "⚠️ *This space is for peer support only and is not a substitute for professional help. Please respect the author's interaction boundaries.*"
)

DEFAULT_GUILD: Dict[str, Any] = {
    "hub_channel_id": None,
    "mod_role_id": None,
    "archive_category_id": None,
    "inactivity_timeout": 12.0,
    "hard_cap_timeout": 24.0,
    "post_action": "archive",
    "crisis_header": DEFAULT_CRISIS_HEADER,
    "active_vents": {},
    "intents": DEFAULT_INTENTS,
}

# Persistent custom_ids for discord.ui components
LAUNCHER_BUTTON_ID: str = "ephemeralvents:start_vent"
CLOSE_BUTTON_ID: str = "ephemeralvents:close_vent"
DELETE_BUTTON_ID: str = "ephemeralvents:delete_channel"
LEGACY_DELETE_BUTTON_ID: str = "ephemeralvents:delete_thread"

# Limitations and configuration constants
MAX_TOPIC_LENGTH: int = 30
MAX_SLUG_LENGTH: int = 25
CONFIG_IDENTIFIER: int = 748291048291

# Visual color mapping for intent embeds
INTENT_COLORS: Dict[str, discord.Color] = {
    "advice": discord.Color.orange(),
    "comfort": discord.Color.gold(),
    "relate": discord.Color.green(),
    "gentle": discord.Color.blue(),
    "open": discord.Color.purple(),
}
DEFAULT_EMBED_COLOR: discord.Color = discord.Color.teal()
