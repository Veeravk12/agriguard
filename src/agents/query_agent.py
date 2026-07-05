"""Turns a farm owner's Telegram reply into an action, or answers a plain
status check without touching whatever decision is still pending.
"""

import requests

from src import config

ACTION_LABELS = {
    "irrigate": "Irrigate",
    "spray_pesticide": "Spray pesticide",
    "no_action": "No action",
}

_ACTION_KEYWORDS = {
    "irrigate": ["irrigate", "water", "irrigation"],
    "spray_pesticide": ["spray", "pesticide"],
    "no_action": ["no action", "none", "cancel", "skip", "no"],
}

_STATUS_KEYWORDS = [
    "status", "update", "how's it going", "hows it going",
    "what's happening", "whats happening", "what's going on",
]


def build_options(*actions: str) -> list[str]:
    """Turns the local/cloud actions into a short numbered menu. "uncertain"
    isn't a real choice so it's dropped; "no action" is always offered even
    if neither model proposed it, since it's always a valid call."""
    options = [a for a in dict.fromkeys(actions) if a != "uncertain"]
    if "no_action" not in options:
        options.append("no_action")
    return options


def parse_reply(text: str, options: list[str] | None = None) -> str | None:
    """Maps a reply to a recognized action, or None if unrecognized. If
    `options` is given (the numbered menu that was sent), a bare number like
    "1" or "1." picks from it. Otherwise falls back to keyword matching so
    free-text replies like "spray it" still work."""
    stripped = text.strip()
    digits = stripped.rstrip(".)")
    if options and digits.isdigit():
        index = int(digits) - 1
        if 0 <= index < len(options):
            return options[index]

    lowered = stripped.lower()
    for action, keywords in _ACTION_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return action
    return None


def is_status_query(text: str) -> bool:
    """True if the reply is just asking how things are going, not choosing
    an action."""
    lowered = text.strip().lower()
    return any(keyword in lowered for keyword in _STATUS_KEYWORDS)


def get_latest_update_id() -> int:
    """Highest update_id right now, so a fresh polling session ignores
    anything sent before it started."""
    if not (config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID):
        return 0
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/getUpdates"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
    except requests.RequestException:
        return 0
    if not data.get("ok") or not data["result"]:
        return 0
    return max(u["update_id"] for u in data["result"])


def fetch_new_replies(last_update_id: int) -> tuple[list[str], int]:
    """Polls Telegram for messages after last_update_id. Returns the new
    message texts from the configured chat, plus the new last_update_id."""
    if not (config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID):
        return [], last_update_id

    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/getUpdates"
    try:
        resp = requests.get(url, params={"offset": last_update_id + 1, "timeout": 0}, timeout=10)
        data = resp.json()
    except requests.RequestException:
        return [], last_update_id

    if not data.get("ok"):
        return [], last_update_id

    replies = []
    new_last_id = last_update_id
    for update in data["result"]:
        new_last_id = max(new_last_id, update["update_id"])
        message = update.get("message", {})
        chat_id = str(message.get("chat", {}).get("id", ""))
        text = message.get("text")
        if text and chat_id == str(config.TELEGRAM_CHAT_ID):
            replies.append(text)
    return replies, new_last_id
