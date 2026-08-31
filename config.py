import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "kinza_crm.db"))

# ID администраторов через запятую в .env: ADMIN_IDS=12345678,87654321
raw_admins = os.getenv("ADMIN_IDS", "")
ADMIN_IDS =