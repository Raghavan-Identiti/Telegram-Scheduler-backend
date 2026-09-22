from telethon.sync import TelegramClient
from telethon.sessions import StringSession

api_id = 28978014
api_hash = '40c41b53d27230791abf8939cb18f111'

with TelegramClient(StringSession(), api_id, api_hash) as client:
    print("✅ SESSION STRING:\n", client.session.save())
