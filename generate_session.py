from telethon.sync import TelegramClient
from telethon.sessions import StringSession

api_id = 23623688
api_hash = 'a97aa6736081b0102f9b7131cb71b2eb'

with TelegramClient(StringSession(), api_id, api_hash) as client:
    print("✅ SESSION STRING:\n", client.session.save())
