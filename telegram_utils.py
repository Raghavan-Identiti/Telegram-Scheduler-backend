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
        r'post[-_ ]?(\d+)(?:\s?)?\s*\n(.*?)\npost[-_ ]?\1(?:\s+end|\s+copies?)?\s*(?:end)?',
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

def log_post_status(post_number, category, status, schedule_time, message, excel_path=None):
    # Split datetime into date and time components
    date_str = schedule_time.strftime("%Y-%m-%d")
    time_str = schedule_time.strftime("%H:%M:%S")

    new_log = {
        "Post Number": post_number,
        "Category": category if category else 'Uncategorized',
        "Date": date_str,
        "Time": time_str,
        "Status": status,
        "Message": message.strip() if message else '',
    }

    os.makedirs("logs", exist_ok=True)

    if not excel_path:
        excel_path = os.path.join("logs", "post_logs.xlsx")

    if os.path.exists(excel_path):
        df = pd.read_excel(excel_path)
        df = pd.concat([df, pd.DataFrame([new_log])], ignore_index=True)
    else:
        df = pd.DataFrame([new_log])

    df.to_excel(excel_path, index=False)

async def send_telegram_message(image_path: str, post_text: str, post_number: int, category: str, schedule_time: datetime):
    if not client.is_connected():
        await client.connect()
    if not await client.is_user_authorized():
        raise Exception("Telegram client not authorized")

    entity = await client.get_entity(target_channel)

    # Upload image if exists
    media = None
    try:

        if image_path:
            with open(image_path, 'rb') as file:
                media = await client.upload_file(file)

        message = (post_text or "").strip()  # ensures string

        MAX_CAPTION_LENGTH = 1024
        MAX_TEXT_LENGTH = 4096

        if media and message:
            if len(message) <= MAX_CAPTION_LENGTH:
                # Send image with caption (safe)
                input_media = InputMediaUploadedPhoto(file=media)
                await client(SendMediaRequest(
                    peer=entity,
                    media=input_media,
                    message=message,
                    schedule_date=schedule_time
                ))
            else:
                # Caption too long, send image first without caption
                input_media = InputMediaUploadedPhoto(file=media)
                await client(SendMediaRequest(
                    peer=entity,
                    media=input_media,
                    message="",  # no caption
                    schedule_date=schedule_time
                ))
                # Then send the text separately as a message
                # (Add a small delay to avoid flooding)
                import asyncio
                await asyncio.sleep(1)
                # Truncate text if longer than max allowed
                chunks = [message[i:i+MAX_TEXT_LENGTH] for i in range(0, len(message), MAX_TEXT_LENGTH)]
                for chunk in chunks:
                    await client(SendMessageRequest(
                        peer=entity,
                        message=chunk,
                        schedule_date=schedule_time
                    ))
        elif media:
            # Image only
            input_media = InputMediaUploadedPhoto(file=media)
            await client(SendMediaRequest(
                peer=entity,
                media=input_media,
                message="",
                schedule_date=schedule_time
            ))
        elif message:
            # Text only
            chunks = [message[i:i+MAX_TEXT_LENGTH] for i in range(0, len(message), MAX_TEXT_LENGTH)]
            for chunk in chunks:
                await client(SendMessageRequest(
                    peer=entity,
                    message=chunk,
                    schedule_date=schedule_time
                ))
        else:
            # Nothing to send
            print(f"Nothing to send for post {post_number}")


        print(f"✅ Scheduled post {post_number} at {schedule_time}")
        log_post_status(post_number, category, "✅ Scheduled", schedule_time, message)
    except Exception as e:
        print(f"❌ Failed to schedule post {post_number}: {e}")
        log_post_status(post_number, category, f"❌ Failed: {str(e)}", schedule_time,message)


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

