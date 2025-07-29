from telethon.sync import TelegramClient

api_id = '28978014'
api_hash = '40c41b53d27230791abf8939cb18f111h'

with TelegramClient('session_name', api_id, api_hash) as client:
    for dialog in client.iter_dialogs():
        if dialog.is_channel:
            print(f"Title: {dialog.name}, Username: {dialog.entity.username}")
