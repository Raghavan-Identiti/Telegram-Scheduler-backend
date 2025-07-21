from telethon.sync import TelegramClient
from telethon.sessions import StringSession

api_id = int(input("Enter your API ID: "))
api_hash = input("Enter your API HASH: ")

with TelegramClient(StringSession(), api_id, api_hash) as client:
    print("Your session string is:")
    print(client.session.save())
