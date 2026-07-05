import json
from typing import Literal

from google.adk.agents import Agent
from google.adk.runners import InMemoryRunner
from google.genai import types
from pydantic import BaseModel, Field

from src import config

DECISION_PROMPT = """You are the Cloud Reasoning Agent for AgriGuard, a crop monitoring system.
The Local Decision Agent already looked at this snapshot and was uncertain or its
proposed action was high-stakes enough to need a second opinion. Give your own
independent read.

Recommend the next agronomic action based only on plant/soil/pest need:
soil_moisture_pct, pest_risk_score, leaf_health_score, temperature_c.

wind_speed_kmh and power_available are NOT yours to judge — a separate deterministic
safety system enforces those operational constraints after your recommendation. Do not
let them change your action or confidence.

If soil moisture and pest risk both call for action, pick whichever is more severe
relative to its own healthy range; don't default to "uncertain" just because two
concerns are present.

Snapshot:
{snapshot_json}

Local Decision Agent's opinion (for context only — form your own independent judgment,
don't just agree with it):
{local_decision_json}
"""


class Decision(BaseModel):
    action: Literal["irrigate", "spray_pesticide", "no_action", "uncertain"]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


_agent = Agent(
    name="cloud_reasoning_agent",
    model=config.GEMINI_MODEL,
    instruction="You are a careful agronomy decision assistant for a real farm. Be decisive.",
    output_schema=Decision,
    generate_content_config=types.GenerateContentConfig(temperature=0.0),
)
_runner = InMemoryRunner(agent=_agent, app_name="agriguard")
_USER_ID = "orchestrator"


def decide(snapshot: dict, local_decision: dict) -> dict:
    """Ask Gemini for a second opinion on a snapshot the local model flagged.

    On any API error, timeout, or non-JSON output, returns "uncertain"
    rather than raising, so the caller falls through to the human-escalation
    path instead of taking an unverified autonomous action.
    """
    if not config.GEMINI_API_KEY:
        return {
            "action": "uncertain",
            "confidence": 0.0,
            "reasoning": "GEMINI_API_KEY not configured — cannot reach Cloud Reasoning Agent",
        }

    prompt = DECISION_PROMPT.format(
        snapshot_json=json.dumps(snapshot),
        local_decision_json=json.dumps(local_decision),
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

        return json.loads(reply_text.strip().strip("`"))
    except Exception as exc:
        return {
            "action": "uncertain",
            "confidence": 0.0,
            "reasoning": f"Cloud Reasoning Agent call failed: {exc!r}",
        }
