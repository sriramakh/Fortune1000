import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
PROFILES_DIR = DATA_DIR / "profiles"
NEWS_DIR = DATA_DIR / "news"
EVENTS_DIR = DATA_DIR / "events"
COMBINED_DIR = DATA_DIR / "combined"
PROGRESS_DIR = DATA_DIR / "progress"
LOGS_DIR = BASE_DIR / "logs"

# SearXNG
SEARXNG_BASE_URL = "http://localhost:8080/search"
SEARXNG_CONCURRENCY = 15
SEARXNG_DELAY = 0.2  # seconds between requests

# MiniMax (fast - for news/events)
MINIMAX_API_TOKEN = os.getenv("MINIMAX_API_TOKEN", "")
MINIMAX_MODEL = "MiniMax-M2.7"
MINIMAX_CONCURRENCY = 10
MINIMAX_RPM = 60

# OpenAI GPT-4o-mini (quality - for profiles)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = "gpt-4o-mini"
OPENAI_CONCURRENCY = 5
OPENAI_RPM = 500

# Logo
LOGO_DEV_TOKEN = os.getenv("LOGO_DEV_TOKEN", "")
GOOGLE_FAVICON_URL = "https://www.google.com/s2/favicons?domain={domain}&sz=128"

# LLM provider for news/events: "minimax" or "openai"
# Set to "openai" to skip MiniMax entirely (e.g., if MiniMax has no balance)
NEWS_LLM_PROVIDER = os.getenv("NEWS_LLM_PROVIDER", "minimax")

# Retry
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2
