from telethon import TelegramClient
import asyncio

api_id = 123456
api_hash = "your_api_hash"

async def logout():
    client = TelegramClient("session", api_id, api_hash)
    await client.start()
    await client.log_out()  # logs out from Telegram
    await client.disconnect()
    print("Logged out and session removed!")

asyncio.run(logout())
