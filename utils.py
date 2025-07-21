import os
import pandas as pd
from dotenv import load_dotenv
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from datetime import datetime
import re

load_dotenv()

api_id = int(os.getenv("TELEGRAM_API_ID"))
api_hash = os.getenv("TELEGRAM_API_HASH")
phone = os.getenv("TELEGRAM_PHONE_NUMBER")
session_string = os.getenv("TELETHON_SESSION")

client = TelegramClient(StringSession(session_string), api_id, api_hash)

def extract_post_content(text_paths, post_num):
    content = ''
    for text_path in text_paths:
        with open(text_path, 'r', encoding='utf-8') as f:
            content = f.read()

        match = re.search(
            r"AMZ_TELEGRAM.*?(POST\s*{}\s*CONTENT.*?END OF POST\s*{})".format(post_num, post_num),
            content, re.DOTALL | re.IGNORECASE
        )

        if match:
            post_content = match.group(1)
            post_content = re.sub(r"POST\s*\d+\s*CONTENT\s*BEGINS\s*HERE\s*:", "", post_content, flags=re.IGNORECASE)
            post_content = re.sub(r"END OF POST\s*\d+", "", post_content, flags=re.IGNORECASE)
            return post_content.strip()

    return None

async def send_telegram_message(image_path: str, text_paths: list, post_number: int = 1):
    await client.start()
    message = extract_post_content(text_paths, post_number)

    try:
        if image_path and message:
            await client.send_file('me', image_path, caption=message)
            status = 'Image + Text sent'
        elif image_path and not message:
            await client.send_file('me', image_path)
            status = 'Image only sent'
        elif not image_path and message:
            await client.send_message('me', message)
            status = 'Text only sent'
        else:
            status = f'Nothing to send for post {post_number}'

    except Exception as e:
        status = f'Failed: {str(e)}'

    log_entry = pd.DataFrame([{
        'filename': os.path.basename(image_path) if image_path else 'N/A',
        'post_number': post_number,
        'message': message[:100] if message else '',
        'status': status,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }])

    os.makedirs("logs", exist_ok=True)
    logfile = "logs/messages.xlsx"

    if os.path.exists(logfile):
        existing = pd.read_excel(logfile)
        pd.concat([existing, log_entry], ignore_index=True).to_excel(logfile, index=False)
    else:
        log_entry.to_excel(logfile, index=False)

    print(f"✅ {status}: Post {post_number}")
