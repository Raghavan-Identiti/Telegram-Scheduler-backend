#telegram_utils.py
import os
import pandas as pd
from dotenv import load_dotenv
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from datetime import datetime
import re
from typing import Dict, List
from telegram_scheduler import TelegramScheduler
from datetime import datetime
from telethon.tl.functions.messages import SendMessageRequest, SendMediaRequest
from telethon.tl.types import InputPeerChannel, InputMediaUploadedPhoto, InputMediaUploadedDocument
from telethon.tl.functions.channels import GetChannelsRequest
from telethon.tl.types import InputChannel
from telethon.tl.types import InputPeerUser
from telethon.tl.functions.messages import UploadMediaRequest

scheduler = TelegramScheduler()

load_dotenv()

api_id = int(os.getenv("TELEGRAM_API_ID"))
api_hash = os.getenv("TELEGRAM_API_HASH")
phone = os.getenv("TELEGRAM_PHONE_NUMBER")
session_string = os.getenv("TELETHON_SESSION")
target_channel = os.getenv("TELEGRAM_TARGET_CHANNEL", "amazonindiaassociates")  # Just username, NOT t.me link
client = TelegramClient(StringSession(session_string), api_id, api_hash)

def extract_all_posts_from_texts(text_blocks: List[str]) -> Dict[int, str]:
    posts = {}

    # Pattern: post-1 ... post-1 end (any separator: -, _, space)
    post_block_pattern = re.compile(
        r'post[-_ ]?(\d+)\s*\n(.*?)\npost[-_ ]?\1\s*end',
        re.IGNORECASE | re.DOTALL
    )

    section_start_pattern = re.compile(r'AMZ_TELEGRAM', re.IGNORECASE)

    for text in text_blocks:
        # Start from "AMZ_TELEGRAM" if present
        section_match = section_start_pattern.search(text)
        if section_match:
            text = text[section_match.end():]

        # Find all post blocks in this text block
        for match in post_block_pattern.finditer(text):
            post_num = int(match.group(1))
            content = match.group(2).strip()
            # Try to extract category from the first line
            lines = content.splitlines()
            category = None
            text_lines = lines

            if lines and lines[0].lower().startswith("category:"):
                category = lines[0][len("category:"):].strip()
                text_lines = lines[1:]  # Remaining lines are the actual post

            clean_text = "\n".join(text_lines).strip()
            posts[post_num] = {
                "category": category,
                "text": clean_text
            }

    return posts

def split_long_message(message, max_length=4096):
    if len(message) <= max_length:
        return [message]

    chunks = []
    while len(message) > max_length:
        split_index = message.rfind("\n", 0, max_length)
        if split_index == -1:
            split_index = max_length
        chunks.append(message[:split_index])
        message = message[split_index:].lstrip()
    chunks.append(message)
    return chunks

# async def send_telegram_message(image_path: str, post_text: str, post_number: int = 1, category: str = None, target_channel: str = None,schedule_time: datetime = None):
#     if not client.is_connected():
#         await client.connect()

#     if not await client.is_user_authorized():
#         raise Exception("Telegram client not authorized")
#         await client.start(phone)
    
#     print("🧪 post_text type:", type(post_text))
#     print("🧪 post_text value:", post_text)
#     if isinstance(post_text, dict):
#         message = post_text.get("text", "").strip()
#     elif isinstance(post_text, str):
#         message = post_text.strip()
#     else:
#         message = ""

#     message = post_text.strip() if post_text else ""
#     message_parts = split_long_message(message) if message else []
#     status = ''

#     try:
#         entity = await client.get_entity(target_channel)
#         if image_path and message_parts:
#             caption = message_parts[0][:1024]
#             await client.send_file(entity, image_path, caption=caption, schedule=schedule_time)
#             for part in message_parts[1:]:
#                 await client.send_message(entity, part, schedule=schedule_time)
#             status = f'Scheduled Image + Text at {schedule_time}'

#         elif image_path and not message_parts:
#             await client.send_file(entity, image_path, schedule=schedule_time)
#             status = f'Scheduled Image only at {schedule_time}'

#         elif not image_path and message_parts:
#             for part in message_parts:
#                 await client.send_message(entity, part, schedule=schedule_time)
#             status = f'Scheduled Text only at {schedule_time}'

#         else:
#             status = f'Nothing to send for post {post_number}'

#     except Exception as e:
#         status = f'Failed: {str(e)}'

#     log_entry = pd.DataFrame([{
#         'filename': os.path.basename(image_path) if image_path else 'N/A',
#         'post_number': post_number,
#         'category': category if category else 'Uncategorized',
#         'message': message[:100] if message else '',
#         'status': status,
#         'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
#     }])

#     os.makedirs("logs", exist_ok=True)
#     logfile = "logs/messages.xlsx"

#     if os.path.exists(logfile):
#         existing = pd.read_excel(logfile)
#         combined = pd.concat([existing, log_entry], ignore_index=True)
#         combined.to_excel(logfile, index=False)
#     else:
#         log_entry.to_excel(logfile, index=False)

#     print(f"✅ {status}: Post {post_number}")



async def send_telegram_message(image_path: str, post_text: str, post_number: int, category: str, schedule_time: datetime):
    await client.connect()
    if not await client.is_user_authorized():
        raise Exception("Telegram client not authorized")

    entity = await client.get_entity(target_channel)

    # Upload image if exists
    media = None
    if image_path:
        with open(image_path, 'rb') as file:
            media = await client.upload_file(file)

    message = post_text or ""

    if media:
        input_media = InputMediaUploadedPhoto(file=media)
        await client(SendMediaRequest(
            peer=entity,
            media=input_media,
            message=message,
            schedule_date=schedule_time
        ))
    else:
        await client(SendMessageRequest(
            peer=entity,
            message=message,
            schedule_date=schedule_time
        ))

    print(f"✅ Scheduled post {post_number} at {schedule_time}")

def match_image_to_post(post_number: int, image_filenames: list[str]) -> str | None:
    """
    Find image filename matching post_number, allowing flexible naming:
    Matches 'post-1.jpg', 'post_01-final.png', 'post1.jpeg', etc.
    Returns filename if found, else None.
    """
    post_str_patterns = [
        rf"post[-_]?0*{post_number}\b",  # Correct use of \b
        rf"post0*{post_number}\b"
    ]

    for filename in image_filenames:
        filename_lower = filename.lower()
        for pattern in post_str_patterns:
            if re.search(pattern, filename_lower):
                return filename
    return None

