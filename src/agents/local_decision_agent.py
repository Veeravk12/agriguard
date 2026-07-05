import json
from typing import Literal

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import InMemoryRunner
from google.genai import types
from pydantic import BaseModel, Field

from src import config

DECISION_PROMPT = """You are the Local Decision Agent for AgriGuard, a crop monitoring system.
Given a single consolidated sensor snapshot for one farm zone, recommend the next
agronomic action based only on plant/soil/pest need: soil_moisture_pct, pest_risk_score,
leaf_health_score, temperature_c.

wind_speed_kmh and power_available are NOT yours to judge — a separate deterministic
safety system enforces those operational constraints after your recommendation. Do not
let them change your action or confidence; recommend the action a plant/pest situation
alone calls for, and let the downstream safety layer block it if it's operationally unsafe.

If soil moisture and pest risk both call for action, pick whichever is more severe
relative to its own healthy range; don't default to "uncertain" just because two
concerns are present.

Snapshot:
{snapshot_json}
"""


class Decision(BaseModel):
    action: Literal["irrigate", "spray_pesticide", "no_action", "uncertain"]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


# gemma4:e4b is a thinking-capable model — without output_schema it just
# returns its raw chain-of-thought instead of JSON. output_schema forces
# Ollama's native `format` constraint; reasoning_effort="none" turns off
# thinking (LiteLLM maps this to Ollama's `think` param), which also cuts
# latency from ~15s to ~2.5s per decision — this agent needs to be fast.
_agent = Agent(
    name="local_decision_agent",
    model=LiteLlm(model=f"ollama_chat/{config.OLLAMA_MODEL}", reasoning_effort="none"),
    instruction="You are a careful agronomy decision assistant for a real farm. Be decisive.",
    output_schema=Decision,
    generate_content_config=types.GenerateContentConfig(temperature=0.0),  # reproducible demo runs
)
_runner = InMemoryRunner(agent=_agent, app_name="agriguard")
_USER_ID = "orchestrator"


def decide(snapshot: dict) -> dict:
    """Ask the local model for a first-pass decision on a consolidated snapshot.

    Falls back to "uncertain" (rather than raising) on non-JSON output, so a
    single malformed response escalates to the Cloud Reasoning Agent instead
    of crashing the decision cycle.
    """
    prompt = DECISION_PROMPT.format(snapshot_json=json.dumps(snapshot))
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

    try:
        return json.loads(reply_text.strip().strip("`"))
    except (json.JSONDecodeError, TypeError):
        return {
            "action": "uncertain",
            "confidence": 0.0,
            "reasoning": f"local model returned non-JSON output: {reply_text!r}",
        }
