from telethon.sync import TelegramClient
from telethon.sessions import StringSession
import os

api_id = int(os.getenv("TELEGRAM_API_ID", "2040"))
api_hash = os.getenv("TELEGRAM_API_HASH", "")

print("Generating Telethon StringSession...")
with TelegramClient(StringSession(), api_id, api_hash) as client:
    print("\nYour TELEGRAM_SESSION_STRING is:\n")
    print(client.session.save())
