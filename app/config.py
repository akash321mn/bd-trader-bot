import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DERIV_APP_ID = os.getenv("DERIV_APP_ID", "1089")
OWNER_CONTACT = os.getenv("OWNER_CONTACT", "@X_Akash_Owner⚡")

# Comma-separated admin IDs -> set of ints
raw_admins = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = set()
for part in raw_admins.split(","):
    part = part.strip()
    if part.isdigit():
        ADMIN_IDS.add(int(part))
