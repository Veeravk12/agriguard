"""Live health checks for the three external systems AgriGuard's agents
depend on — read by dashboard.dashboard for the "agent/bot status" panel.
Each check is cheap and side-effect-free (no Gemini generate_content calls,
so it never burns the escalation quota; Telegram's getMe is free and doesn't
send a message)."""

import requests

from src import config, trace_logger


def ollama_status() -> dict:
    try:
        resp = requests.get(f"{config.OLLAMA_HOST}/api/version", timeout=3)
        resp.raise_for_status()
        return {
            "name": "Local Decision Agent (Ollama)",
            "status": "ok",
            "detail": f"reachable at {config.OLLAMA_HOST}, model={config.OLLAMA_MODEL} "
                      f"(server v{resp.json().get('version', '?')})",
        }
    except requests.RequestException as exc:
        return {
            "name": "Local Decision Agent (Ollama)",
            "status": "critical",
            "detail": f"unreachable at {config.OLLAMA_HOST} ({exc.__class__.__name__})",
        }


def gemini_status() -> dict:
    name = "Cloud Reasoning Agent (Gemini)"
    if not config.GEMINI_API_KEY:
        return {"name": name, "status": "not_configured", "detail": "GEMINI_API_KEY not set — falls back to human escalation"}

    last_cloud_call = None
    for entry in reversed(trace_logger.read_all()):
        if entry.get("cloud_decision"):
            last_cloud_call = entry["cloud_decision"]
            break

    if last_cloud_call is None:
        return {"name": name, "status": "warning", "detail": "configured, not called yet this session"}

    reasoning = last_cloud_call.get("reasoning", "")
    if "call failed" in reasoning:
        return {"name": name, "status": "critical", "detail": f"last call failed: {reasoning}"}
    return {"name": name, "status": "ok", "detail": f"last call succeeded: action={last_cloud_call.get('action')}"}


def telegram_status() -> dict:
    name = "Notification Agent (Telegram)"
    if not (config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID):
        return {"name": name, "status": "not_configured", "detail": "TELEGRAM_BOT_TOKEN/CHAT_ID not set — falls back to console"}

    try:
        resp = requests.get(
            f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/getMe", timeout=5
        )
        data = resp.json()
        if data.get("ok"):
            bot_name = data["result"].get("username", "?")
            return {"name": name, "status": "ok", "detail": f"connected as @{bot_name}"}
        return {"name": name, "status": "critical", "detail": f"token rejected: {data.get('description')}"}
    except requests.RequestException as exc:
        return {"name": name, "status": "warning", "detail": f"could not verify ({exc.__class__.__name__}) — will retry on next alert"}


def all_statuses() -> list[dict]:
    return [ollama_status(), gemini_status(), telegram_status()]
