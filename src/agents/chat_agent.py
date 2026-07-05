"""Free-form Telegram chat with the farm assistant — answers questions using
the latest sensor snapshot and recent decision history as context. Kept on
the local Ollama model only: it's free and unlimited, so a chat conversation
can't eat into the scarce Gemini quota.
"""

import json

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import InMemoryRunner
from google.genai import types

from src import config

CHAT_PROMPT = """You are AgriGuard, the farm owner's personal assistant, chatting with them
over Telegram. Talk like a helpful person, not a report generator — if they just say hi,
greet them back warmly and ask if they'd like an update, don't dump raw data on them
unprompted. Keep it brief (a couple of sentences), plain text, no markdown.

If there's a decision awaiting their reply below, weave a natural mention of it into your
response — e.g. "by the way, there's a decision waiting on you, reply with the number to
confirm it" — don't ignore it even if their message was just a greeting. You can't take
actions yourself in this chat; if they want to approve or change something, tell them to
reply with the option number from the actual alert instead.

Current zone snapshot:
{snapshot_json}

Recent resolved decisions (most recent first):
{recent_json}

Decision currently awaiting the farm owner's reply, if any:
{pending_json}

Farm owner's message:
{message}
"""

_agent = Agent(
    name="chat_agent",
    model=LiteLlm(model=f"ollama_chat/{config.OLLAMA_MODEL}", reasoning_effort="none"),
    instruction="You are a warm, proactive farm assistant who keeps the farm owner in the "
                "loop on anything needing their attention, while chatting naturally. Keep "
                "replies short.",
    generate_content_config=types.GenerateContentConfig(temperature=0.5),
)
_runner = InMemoryRunner(agent=_agent, app_name="agriguard")
_USER_ID = "telegram_chat"


def reply(message: str, snapshot: dict, recent_decisions: list[dict], pending: dict | None = None) -> str:
    """Ask the local model to answer a free-form question. Falls back to a
    plain apology instead of raising if Ollama is unreachable."""
    prompt = CHAT_PROMPT.format(
        snapshot_json=json.dumps(snapshot),
        recent_json=json.dumps(recent_decisions),
        pending_json=json.dumps(pending) if pending else "None",
        message=message,
    )
    try:
        session = _runner.session_service.create_session_sync(
            app_name="agriguard", user_id=_USER_ID
        )
        reply_text = ""
        for event in _runner.run(
            user_id=_USER_ID,
            session_id=session.id,
            new_message=types.Content(role="user", parts=[types.Part(text=prompt)]),
        ):
            if event.is_final_response() and event.content and event.content.parts:
                reply_text = event.content.parts[0].text or ""
        return reply_text.strip() or "Sorry, I didn't get anything back for that — try asking again."
    except Exception as exc:
        return f"Sorry, I couldn't reach the local model just now ({exc.__class__.__name__})."
