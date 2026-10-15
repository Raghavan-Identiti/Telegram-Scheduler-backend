import asyncio
import os
from telethon import TelegramClient
from telethon.sessions import StringSession

api_id = int(os.getenv("TELEGRAM_API_ID", "2040"))
api_hash = os.getenv("TELEGRAM_API_HASH", "")
session_string = os.getenv("TELEGRAM_SESSION_STRING", "")

async def main():
    async with TelegramClient(StringSession(session_string), api_id, api_hash) as client:
        dialogs = await client.get_dialogs()
        for d in dialogs:
            if d.is_channel:
                print(f"Channel: {d.title} (ID: {d.id}, Username: @{d.entity.username})")

if __name__ == "__main__":
    asyncio.run(main())
