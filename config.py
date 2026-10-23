import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
WIKI_LANGUAGE = os.getenv("WIKI_LANGUAGE", "ru").strip()
WIKI_USER_AGENT = os.getenv(
    "WIKI_USER_AGENT",
    "WikiDuelBot/1.0 (https://t.me/WikiDuelBot; contact@example.com)"
).strip()

DB_PATH = BASE_DIR / "wiki_duel.db"
