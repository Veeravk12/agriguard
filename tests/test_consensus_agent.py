"""Tests for the Consensus Agent and Notification Agent — both pure Python,
no LLM involved, so synthetic local/cloud decisions exercise real logic
rather than simulating model behavior.

In practice gemma4:e4b (local) and gemini-2.5-flash (cloud) agree far more
often than they diverge, so these tests cover the disagreement/human-
escalation path directly instead of hoping live calls happen to disagree.
"""

from src import config
from src.agents import consensus_agent, notification_agent, query_agent


def test_agree_on_same_confident_action():
    local = {"action": "spray_pesticide", "confidence": 0.95, "reasoning": "pest risk high"}
    cloud = {"action": "spray_pesticide", "confidence": 0.9, "reasoning": "pest risk high"}
    resolution, decision_source = consensus_agent.decide(local, cloud)
    assert resolution == "agree"
    assert decision_source == "escalated_to_gemini"


def test_disagree_on_different_actions():
    local = {"action": "irrigate", "confidence": 0.9, "reasoning": "soil moisture low"}
    cloud = {"action": "spray_pesticide", "confidence": 0.85, "reasoning": "pest risk high"}
    resolution, decision_source = consensus_agent.decide(local, cloud)
    assert resolution == "disagree"
    assert decision_source == "escalated_to_human"


def test_disagree_when_both_uncertain():
    local = {"action": "uncertain", "confidence": 0.5, "reasoning": "conflicting signals"}
    cloud = {"action": "uncertain", "confidence": 0.4, "reasoning": "conflicting signals"}
    resolution, decision_source = consensus_agent.decide(local, cloud)
    assert resolution == "disagree"
    assert decision_source == "escalated_to_human"


def test_notify_falls_back_to_console_without_telegram_config(capsys, monkeypatch):
    # Force "not configured" regardless of the developer's real .env, so this
    # test stays deterministic and never hits the live Telegram API.
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setattr(config, "TELEGRAM_CHAT_ID", "")

    channel = notification_agent.notify("zone_1: models disagree, no action taken")
    captured = capsys.readouterr()
    assert channel == "console"
    assert "zone_1" in captured.out
    assert "models disagree" in captured.out


def test_format_disagreement_alert_is_readable_not_a_dict_dump():
    snapshot = {"soil_moisture_pct": 38, "pest_risk_score": 0.7, "power_available": True}
    local = {"action": "irrigate", "confidence": 0.9, "reasoning": "soil moisture low"}
    cloud = {"action": "spray_pesticide", "confidence": 0.85, "reasoning": "pest risk high"}

    alert = notification_agent.format_disagreement_alert("zone_1", snapshot, local, cloud)

    assert "zone_1" in alert
    assert "Soil moisture: 38%" in alert
    assert "Power available: Yes" in alert
    assert "IRRIGATE" in alert and "SPRAY_PESTICIDE" in alert
    assert "{'action'" not in alert  # not a raw dict repr
    assert "1. Irrigate" in alert and "2. Spray pesticide" in alert and "3. No action" in alert


def test_build_options_dedupes_and_always_offers_no_action():
    assert query_agent.build_options("irrigate", "irrigate") == ["irrigate", "no_action"]
    assert query_agent.build_options("irrigate", "spray_pesticide") == ["irrigate", "spray_pesticide", "no_action"]
    assert query_agent.build_options("no_action", "uncertain") == ["no_action"]


def test_parse_reply_numeric_picks_from_menu():
    options = ["irrigate", "spray_pesticide", "no_action"]
    assert query_agent.parse_reply("1", options) == "irrigate"
    assert query_agent.parse_reply("2.", options) == "spray_pesticide"
    assert query_agent.parse_reply("3)", options) == "no_action"
    assert query_agent.parse_reply("9", options) is None


def test_parse_reply_falls_back_to_keywords_without_a_menu():
    assert query_agent.parse_reply("please spray it") == "spray_pesticide"
    assert query_agent.parse_reply("water the field") == "irrigate"
    assert query_agent.parse_reply("skip it") == "no_action"
    assert query_agent.parse_reply("what does that mean") is None


def test_is_status_query_recognizes_status_words():
    assert query_agent.is_status_query("status")
    assert query_agent.is_status_query("what's happening out there?")
    assert not query_agent.is_status_query("spray")
