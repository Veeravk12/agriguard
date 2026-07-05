import os

from dotenv import load_dotenv

load_dotenv()

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:e4b")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.5-flash"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Decision cycle
DECISION_CYCLE_SECONDS = 60
ZONE_IDS = ["zone_1"]

# Escalation
CONFIDENCE_THRESHOLD = 0.85

# Safety Rule Layer — deterministic, model-independent
MAX_WIND_SPEED_KMH_FOR_SPRAY = 15
RAIN_FORECAST_BLOCKS_IRRIGATION = True

# Estimated cost per Gemini call, for the cost-savings dashboard
ESTIMATED_GEMINI_COST_PER_CALL_USD = 0.01

DECISIONS_LOG_PATH = "data/logs/decisions_log.csv"
