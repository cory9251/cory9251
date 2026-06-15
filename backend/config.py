"""Central runtime config — env loading, logger, DB client, third-party SDK init.

All modules should import config primitives from here so we only load `.env`
once and only construct the Mongo client once. Importing this module has the
side effect of `load_dotenv()` and `resend.api_key = …`.
"""
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import logging
import resend
from motor.motor_asyncio import AsyncIOMotorClient

# ---- Required env vars (fail fast if missing) ------------------------------
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALG = "HS256"

# ---- Optional ---------------------------------------------------------------
APP_NAME = os.environ.get("APP_NAME", "gigblast")
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")
TWILIO_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM = os.environ.get("TWILIO_FROM_NUMBER", "")
VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_SUBJECT = os.environ.get("VAPID_SUBJECT", "mailto:admin@hcobcleaners.com")

# ---- Logger -----------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("gigblast")

# ---- Mongo client (single global) ------------------------------------------
client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

# ---- Resend init ------------------------------------------------------------
if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY
