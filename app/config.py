from dotenv import load_dotenv
import os

load_dotenv()

# per-bot settings
BOT_TOKEN = os.getenv("BOT_TOKEN")

# secrets
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
DATABASE_URL = DATABASE_URL.replace(
    "postgresql://",
    "postgresql+psycopg://",
    1,
)
GEMINI_MODEL = "gemini-3.5-flash"