# telegram_utils.py
import os
import json
import pandas as pd
from dotenv import load_dotenv
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from datetime import datetime, timezone, timedelta
import re
from typing import Dict, List
from telegram_scheduler import TelegramScheduler
from telethon.tl.functions.messages import SendMessageRequest, SendMediaRequest
from telethon.tl.types import InputPeerChannel, InputMediaUploadedPhoto, InputMediaUploadedDocument
import gspread
from google.oauth2 import service_account
import pytz

# --- Load environment variables ---
load_dotenv()

# --- Google Sheets Setup ---
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

SHEET_ID = "1seb2pGu1XekQmNcHC-6Ma_y9tGRyhTo33PrR8sA-EBc"  # ✅ Keep this here (public info)

CHANNELS = {
    'amazonindiaassociates': {
        'username': 'amazonindiaassociates',
        'sheet_name': 'Amazon_India_Associates'
    },
    'Amazon_Associates_FashionBeauty': {
        'username': 'Amazon_Associates_FashionBeauty', 
        'sheet_name': 'Fashion_Beauty'
    },
    'Amazon_Associates_HomeKitchen': {
        'username': 'Amazon_Associates_HomeKitchen',
        'sheet_name': 'Home_Kitchen'
    },
    'Amazon_Associates_Consumables': {
        'username': 'Amazon_Associates_Consumables',
        'sheet_name': 'Consumables'
    }
}

# Global variables for sheet connection
gc = None
sheet = None

# --- Enhanced Telegram Settings ---
MAX_CAPTION_LENGTH = 1024  # Telegram's actual limit
MAX_TEXT_LENGTH = 4096      # Telegram's message limit
CAPTION_SAFETY_BUFFER = 50
MESSAGE_DELAY_MINUTES = 1

def initialize_google_sheets():
    """Initialize Google Sheets connection securely without local service_account.json"""
    global gc, sheet
    try:
        # ✅ Load credentials JSON from environment variable
        google_creds_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
        if not google_creds_json:
            raise ValueError("❌ GOOGLE_SERVICE_ACCOUNT_JSON environment variable not set!")

        creds_dict = json.loads(google_creds_json)
        creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)

        gc = gspread.authorize(creds)
        workbook = gc.open_by_key(SHEET_ID)

        # ✅ Ensure each channel has its own sheet
        expected_headers = ["Post Number", "Category", "Date", "Time", "Status", "Message", "Channel"]

        for channel_id, channel_info in CHANNELS.items():
            sheet_name = channel_info['sheet_name']
            try:
                channel_sheet = workbook.worksheet(sheet_name)
            except gspread.WorksheetNotFound:
                print(f"📄 Creating new sheet: {sheet_name}")
                channel_sheet = workbook.add_worksheet(title=sheet_name, rows=1000, cols=10)
            
            # ✅ Ensure headers exist
            try:
                headers = channel_sheet.row_values(1)
                if not headers or headers != expected_headers:
                    print(f"📑 Setting up headers for {sheet_name}...")
                    channel_sheet.clear()
                    channel_sheet.append_row(expected_headers)
            except Exception as header_error:
                print(f"⚠️ Header setup error for {sheet_name}: {header_error}")
                channel_sheet.append_row(expected_headers)
        
        print("✅ Google Sheets connection successful for all channels")
        return True

    except Exception as e:
        print(f"❌ Google Sheets setup error: {e}")
        return False

# Initialize sheets connection
sheets_available = initialize_google_sheets()

# --- Telegram Credentials ---
api_id = int(os.getenv("TELEGRAM_API_ID"))
api_hash = os.getenv("TELEGRAM_API_HASH")
phone = os.getenv("TELEGRAM_PHONE_NUMBER")
session_string = os.getenv("TELETHON_SESSION")

client = TelegramClient(StringSession(session_string), api_id, api_hash)
scheduler = TelegramScheduler()


def check_caption_length(text: str) -> Dict[str, any]:
    """
    Enhanced caption length checker with detailed analysis
    
    Returns:
        Dict with keys:
        - can_use_as_caption: bool
        - length: int
        - exceeds_by: int (if exceeds limit)
        - safe_caption: str (truncated version if needed)
        - remaining_text: str (text that couldn't fit in caption)
    """
    if not text:
        return {
            "can_use_as_caption": True,
            "length": 0,
            "exceeds_by": 0,
            "safe_caption": "",
            "remaining_text": ""
        }
    
    text = text.strip()
    safe_limit = MAX_CAPTION_LENGTH - CAPTION_SAFETY_BUFFER
    
    result = {
        "can_use_as_caption": len(text) <= safe_limit,
        "length": len(text),
        "exceeds_by": max(0, len(text) - safe_limit),
        "safe_caption": text,
        "remaining_text": ""
    }
    
    if not result["can_use_as_caption"]:
        # Find a good break point for truncation
        truncate_at = safe_limit
        
        # Look for natural break points (sentence endings, newlines)
        for i in range(safe_limit - 100, safe_limit):
            if i < len(text) and text[i] in '.!?\n':
                truncate_at = i + 1
                break
        
        # If no good break point, look for spaces
        if truncate_at == safe_limit:
            for i in range(safe_limit - 50, safe_limit):
                if i < len(text) and text[i] == ' ':
                    truncate_at = i
                    break
        
        result["safe_caption"] = text[:truncate_at].strip()
        result["remaining_text"] = text[truncate_at:].strip()
        
        print(f"⚠️ Caption too long ({len(text)} chars). Split at {truncate_at}: "
              f"Caption={len(result['safe_caption'])} chars, "
              f"Remaining={len(result['remaining_text'])} chars")
    
    return result

def calculate_delayed_schedule_time(original_time: datetime, delay_minutes: int = MESSAGE_DELAY_MINUTES) -> datetime:
    """
    Calculate delayed schedule time for separated text messages
    
    Args:
        original_time: Original scheduled time for the image
        delay_minutes: Minutes to delay the text message
    
    Returns:
        datetime: New schedule time for text message
    """
    return original_time + timedelta(minutes=delay_minutes)

def split_long_message(message, max_length=4096):
    """Enhanced message splitting with better handling"""
    if len(message) <= max_length:
        return [message]

    chunks = []
    remaining = message
    
    while len(remaining) > max_length:
        # Find the best split point
        split_index = max_length
        
        # Look for natural break points in reverse order
        for i in range(max_length - 100, max_length):
            if i < len(remaining):
                if remaining[i] in '\n\n':  # Paragraph break
                    split_index = i + 2
                    break
                elif remaining[i] in '.!?':  # Sentence end
                    split_index = i + 1
                    break
                elif remaining[i] == '\n':  # Line break
                    split_index = i + 1
                    break
                elif remaining[i] == ' ':  # Word boundary
                    split_index = i
                    break
        
        chunks.append(remaining[:split_index].strip())
        remaining = remaining[split_index:].strip()
    
    if remaining:
        chunks.append(remaining)
    
    return chunks

def extract_all_posts_from_texts(text_blocks: List[str]) -> Dict[int, str]:
    posts = {}

    # Much more flexible pattern for post detection
    # Matches: post-1, Post 1, **post-1**, post**-1**, POST_1, etc.
    post_start_pattern = re.compile(
        r'(?:^|\n)\s*(?:\*{0,2})\s*post\s*[-_\s]*(\d+)\s*(?:\*{0,2})\s*(?:\n|$)',
        re.IGNORECASE | re.MULTILINE
    )
    
    # End pattern - matches various end formats
    post_end_pattern = re.compile(
        r'(?:^|\n)\s*(?:\*{0,2})\s*post\s*[-_\s]*(\d+)\s*(?:end|copy|copies?|finish|done)\s*(?:\*{0,2})\s*(?:\n|$)',
        re.IGNORECASE | re.MULTILINE
    )

    section_start_pattern = re.compile(r'AMZ_TELEGRAM', re.IGNORECASE)

    # Enhanced time pattern - supports multiple formats
    time_pattern = re.compile(
        r'(?:^|\n)\s*time\s*[:\-=]\s*(\d{1,2}:\d{2}(?::\d{2})?)\s*(?:am|pm)?\s*(?:\n|$)',
        re.IGNORECASE | re.MULTILINE
    )

    for text in text_blocks:
        # Start from "AMZ_TELEGRAM" if present
        section_match = section_start_pattern.search(text)
        if section_match:
            text = text[section_match.end():]

        # Find all post starts
        start_matches = list(post_start_pattern.finditer(text))
        
        for i, start_match in enumerate(start_matches):
            post_num = int(start_match.group(1))
            start_pos = start_match.end()
            
            # Find the corresponding end for this post number
            end_pos = len(text)  # Default to end of text
            
            # Look for specific end pattern for this post number
            remaining_text = text[start_pos:]
            specific_end_pattern = re.compile(
                rf'(?:^|\n)\s*(?:\*{{0,2}})\s*post\s*[-_\s]*{post_num}\s*(?:end|copy|copies?|finish|done)\s*(?:\*{{0,2}})\s*(?:\n|$)',
                re.IGNORECASE | re.MULTILINE
            )
            
            end_match = specific_end_pattern.search(remaining_text)
            if end_match:
                end_pos = start_pos + end_match.start()
            else:
                # If no specific end found, use the next post start as boundary
                if i + 1 < len(start_matches):
                    next_start = start_matches[i + 1]
                    end_pos = next_start.start()

            content = text[start_pos:end_pos]
            lines = content.splitlines()
            category = None
            custom_time = None
            text_lines = []

            for line in lines:
                stripped = line.strip()
                # Category check
                if stripped.lower().startswith("category:"):
                    category = stripped[len("category:"):].strip()
                    continue
                # Time check
                time_match = time_pattern.search(line)
                if time_match:
                    custom_time = time_match.group(1)
                    print(f"🕐 Found custom time for post {post_num}: {custom_time}")
                    continue
                # Keep line exactly (including blank lines)
                text_lines.append(line)

            clean_text = "\n".join(text_lines).rstrip()

            
            posts[post_num] = {
                "category": category,
                "text": clean_text,
                "custom_time": custom_time  # New field for custom time
            }
            
            print(f"📋 Extracted Post {post_num}: Category='{category}', CustomTime='{custom_time}', TextLength={len(clean_text)}")

    return posts

def parse_custom_time(time_str: str, base_date: datetime) -> datetime:
    """
    Parse custom time from text file and combine with base date.
    Supports formats: HH:MM, HH:MM:SS, HH:MM AM/PM
    """
    if not time_str:
        return None
    
    time_str = time_str.strip()
    
    # Remove AM/PM for now (we'll handle 24-hour format)
    am_pm = None
    if time_str.lower().endswith(('am', 'pm')):
        am_pm = time_str[-2:].lower()
        time_str = time_str[:-2].strip()
    
    try:
        # Try different time formats
        time_formats = ["%H:%M:%S", "%H:%M"]
        time_obj = None
        
        for fmt in time_formats:
            try:
                time_obj = datetime.strptime(time_str, fmt).time()
                break
            except ValueError:
                continue
        
        if not time_obj:
            print(f"⚠️ Could not parse time format: {time_str}")
            return None
        
        # Handle AM/PM
        if am_pm:
            hour = time_obj.hour
            if am_pm == 'pm' and hour != 12:
                hour += 12
            elif am_pm == 'am' and hour == 12:
                hour = 0
            time_obj = time_obj.replace(hour=hour)
        
        # Combine with base date
        result = datetime.combine(base_date.date(), time_obj)
        return result
        
    except Exception as e:
        print(f"❌ Error parsing custom time '{time_str}': {e}")
        return None

def safe_truncate_text(text, max_length=100):
    """Safely truncate text for logging, ensuring it doesn't break"""
    if not text:
        return ""
    
    text = str(text).strip()
    if len(text) <= max_length:
        return text
    
    # Find a good break point (space, newline, or punctuation)
    truncate_at = max_length
    for i in range(max_length - 10, max_length):
        if i < len(text) and text[i] in ' \n.!?':
            truncate_at = i
            break
    
    return text[:truncate_at] + "..."

def format_datetime_consistently(dt):
    """Format datetime consistently for logging"""
    if dt is None:
        return datetime.now(timezone.utc)
    
    # Ensure we have timezone info
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    return dt

def append_row_to_sheet(values):
    """Append row to Google Sheet with retry logic"""
    if not sheets_available or not sheet:
        print("❌ Google Sheets not available")
        return False
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # Ensure all values are strings and properly formatted
            formatted_values = []
            for val in values:
                if val is None:
                    formatted_values.append("")
                else:
                    formatted_values.append(str(val).strip())
            
            sheet.append_row(formatted_values)
            print(f"✅ Successfully logged to Google Sheets (attempt {attempt + 1})")
            return True
            
        except Exception as e:
            print(f"❌ Attempt {attempt + 1} failed to append row: {e}")
            if attempt == max_retries - 1:
                print("❌ All attempts failed to write to Google Sheets")
                return False
            
            # Wait before retry
            import time
            time.sleep(2 ** attempt)  # Exponential backoff
    
    return False

def log_post_status_gsheet(post_number, category, status, schedule_time, message, channel_id):
    """Log post status to Google Sheets with consistent formatting"""
    if not sheets_available or not gc:
        log_post_status_local_fallback(post_number, category, status, schedule_time, message, channel_id)
        return

    try:
        workbook = gc.open_by_key(SHEET_ID)
        sheet_name = CHANNELS[channel_id]['sheet_name']
        channel_sheet = workbook.worksheet(sheet_name)
        
        # Format datetime consistently
        schedule_time = format_datetime_consistently(schedule_time)
        
        # Convert to Asia/Kolkata (IST)
        local_tz = pytz.timezone("Asia/Kolkata")
        local_time = schedule_time.astimezone(local_tz)
        
        # Format date and time consistently
        date_str = local_time.strftime("%Y-%m-%d")
        time_str = local_time.strftime("%H:%M:%S")
        
        # Ensure consistent data types and format
        post_number = int(post_number) if post_number else 0
        category = str(category).strip() if category else 'Uncategorized'
        status = str(status).strip() if status else 'Unknown'
        
        # Truncate message to prevent sheet issues
        message_truncated = safe_truncate_text(message, 200)
        
        values = [
            post_number,
            category,
            date_str,
            time_str,
            status,
            message_truncated,
            CHANNELS[channel_id]['username']
        ]
        
        # Log to console for debugging
        print(f"📝 Logging: Post {post_number} | {category} | {date_str} {time_str} | {status}")
        
        # Append to sheet
        success = append_row_to_sheet_channel(channel_sheet, values)
        
        if not success:
            log_post_status_local_fallback(post_number, category, status, schedule_time, message, channel_id)
            
    except Exception as e:
        print(f"❌ Error in log_post_status_gsheet: {e}")
        log_post_status_local_fallback(post_number, category, status, schedule_time, message, channel_id)

def append_row_to_sheet_channel(channel_sheet, values):
    """Append row to specific channel sheet with retry logic"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # Ensure all values are strings and properly formatted
            formatted_values = []
            for val in values:
                if val is None:
                    formatted_values.append("")
                else:
                    formatted_values.append(str(val).strip())
            
            channel_sheet.append_row(formatted_values)
            print(f"✅ Successfully logged to Google Sheets (attempt {attempt + 1})")
            return True
            
        except Exception as e:
            print(f"❌ Attempt {attempt + 1} failed to append row: {e}")
            if attempt == max_retries - 1:
                print("❌ All attempts failed to write to Google Sheets")
                return False
            
            # Wait before retry
            import time
            time.sleep(2 ** attempt)  # Exponential backoff
    
    return False

def log_post_status_local_fallback(post_number, category, status, schedule_time, message, channel_id):
    """Fallback logging to local Excel file if Google Sheets fails"""
    try:
        # Format datetime consistently
        schedule_time = format_datetime_consistently(schedule_time)
        
        # Convert to Asia/Kolkata (IST)
        local_tz = pytz.timezone("Asia/Kolkata")
        local_time = schedule_time.astimezone(local_tz)
        
        date_str = local_time.strftime("%Y-%m-%d")
        time_str = local_time.strftime("%H:%M:%S")
        
        new_log = {
            "Post Number": int(post_number) if post_number else 0,
            "Category": str(category).strip() if category else 'Uncategorized',
            "Date": date_str,
            "Time": time_str,
            "Status": str(status).strip() if status else 'Unknown',
            "Message": safe_truncate_text(message, 200),
            "Channel": CHANNELS.get(channel_id, {}).get('username', channel_id)
        }

        os.makedirs("logs", exist_ok=True)
        excel_path = os.path.join("logs", "post_logs.xlsx")

        if os.path.exists(excel_path):
            df = pd.read_excel(excel_path)
            df = pd.concat([df, pd.DataFrame([new_log])], ignore_index=True)
        else:
            df = pd.DataFrame([new_log])

        df.to_excel(excel_path, index=False)
        print(f"📁 Logged to local fallback file: {excel_path}")
        
    except Exception as e:
        print(f"❌ Even fallback logging failed: {e}")

def get_blocked_times_from_sheet(channel_ids=None):
    """Return blocked times, optionally filtered by channel"""
    if not gc:
        print("⚠️ Google Sheets connection not available, trying to initialize...")
        if not initialize_google_sheets():
            return []
    
    blocked = []
    try:
        workbook = gc.open_by_key(SHEET_ID)
        channels_to_check = channel_ids or list(CHANNELS.keys())
        
        for channel_id in channels_to_check:
            sheet_name = CHANNELS[channel_id]['sheet_name']
            try:
                channel_sheet = workbook.worksheet(sheet_name)
                records = channel_sheet.get_all_records()
                
                for rec in records:
                    date = str(rec.get("Date", "")).strip()
                    time = str(rec.get("Time", "")).strip()
                    status = str(rec.get("Status", "")).strip()

                    if not date or not time:
                        continue

                    if status:  # Any non-empty status means this time slot was used
                        dt_str = f"{date} {time}"
                        dt = None

                        # Flexible parsing to match both logging styles
                        formats = [
                            "%Y-%m-%d %H:%M:%S",
                            "%Y-%m-%d %H:%M",
                            "%d/%m/%Y %H:%M:%S", 
                            "%d/%m/%Y %H:%M",
                            "%Y/%m/%d %H:%M:%S",
                            "%Y/%m/%d %H:%M",
                            "%m/%d/%Y %H:%M:%S",
                            "%m/%d/%Y %H:%M",
                        ]

                        for fmt in formats:
                            try:
                                dt = datetime.strptime(dt_str, fmt)
                                break
                            except ValueError:
                                continue

                        if dt:
                            blocked.append(dt)
                            print(f"🚫 Blocked time slot found: {dt} (Status: {status}) from {sheet_name}")
                        else:
                            print(f"⚠️ Could not parse datetime: {dt_str}")
                            
            except gspread.WorksheetNotFound:
                print(f"Sheet {sheet_name} not found, skipping")
                continue
                
    except Exception as e:
        print(f"❌ Error reading blocked times: {e}")
    
    print(f"📊 Total blocked time slots found: {len(blocked)}")
    return blocked
    
async def send_telegram_message(image_path: str, post_text: str, post_number: int, category: str, schedule_time: datetime, channel_username: str, channel_id: str):
    """Send Telegram message with improved error handling and consistent logging"""
    try:
        if not client.is_connected():
            await client.connect()
        if not await client.is_user_authorized():
            raise Exception("Telegram client not authorized")

        entity = await client.get_entity(channel_username)

        media = None
        
        if image_path and os.path.exists(image_path):
            try:
                with open(image_path, 'rb') as file:
                    media = await client.upload_file(file)
                print(f"📸 Image uploaded successfully: {image_path}")
            except Exception as img_error:
                print(f"⚠️ Failed to upload image {image_path}: {img_error}")
                media = None

        message = (post_text or "").strip()  # ensures string

        caption_check = check_caption_length(message)

        if media and message:
            if caption_check["can_use_as_caption"]:
                # Caption fits - send with image
                input_media = InputMediaUploadedPhoto(file=media)
                await client(SendMediaRequest(
                    peer=entity,
                    media=input_media,
                    message=caption_check["safe_caption"],  # safe version
                    schedule_date=schedule_time
                ))
                print(f"✅ Sent image with caption for post {post_number} at {schedule_time}")
            
            else:
                # Caption too long - new strategy:
                # Step 1: Send image with NO caption
                input_media = InputMediaUploadedPhoto(file=media)
                await client(SendMediaRequest(
                    peer=entity,
                    media=input_media,
                    message="",  # no caption
                    schedule_date=schedule_time
                ))
                print(f"📸 Sent image only (caption too long) at {schedule_time}")

                # Step 2: Send full text after 1 min
                text_schedule_time = calculate_delayed_schedule_time(schedule_time, MESSAGE_DELAY_MINUTES)
                text_chunks = split_long_message(message, MAX_TEXT_LENGTH)

                for i, chunk in enumerate(text_chunks):
                    chunk_schedule_time = text_schedule_time + timedelta(seconds=i * 30)
                    await client(SendMessageRequest(
                        peer=entity,
                        message=chunk,
                        schedule_date=chunk_schedule_time
                    ))
                    print(f"📝 Scheduled text chunk {i+1}/{len(text_chunks)} ({len(chunk)} chars) at {chunk_schedule_time}")

                # Log both separately
                log_post_status_gsheet(post_number, category, "✅ Scheduled (Image only)", schedule_time, "", channel_id)
                log_post_status_gsheet(f"{post_number}-text", category, "✅ Scheduled (Text)", text_schedule_time, message, channel_id)
                log_post_status_gsheet(post_number, category, "⚠️ No Content", schedule_time, "No text or image provided", channel_id)
                log_post_status_gsheet(post_number, category, "✅ Scheduled", schedule_time, message, channel_id)
                log_post_status_gsheet(post_number, category, f"❌ {error_msg}", schedule_time, message or "", channel_id)

  
        elif media:
            # Image only
            input_media = InputMediaUploadedPhoto(file=media)
            await client(SendMediaRequest(
                peer=entity,
                media=input_media,
                message="",
                schedule_date=schedule_time
            ))
            print(f"📤 Sent image only for post {post_number}")
        elif message:
            # Text only
            chunks = [message[i:i+MAX_TEXT_LENGTH] for i in range(0, len(message), MAX_TEXT_LENGTH)]
            for chunk in chunks:
                await client(SendMessageRequest(
                    peer=entity,
                    message=chunk,
                    schedule_date=schedule_time
                ))
            print(f"📤 Sent text only for post {post_number}")
        else:
            # Nothing to send
            print(f"⚠️ Nothing to send for post {post_number}")
            log_post_status_gsheet(post_number, category, "⚠️ No Content", schedule_time, "No text or image provided")
            return

        print(f"✅ Successfully scheduled post {post_number} at {schedule_time}")
        log_post_status_gsheet(post_number, category, "✅ Scheduled", schedule_time, message, channel_id)
        
    except Exception as e:
        error_msg = f"Failed: {str(e)}"
        print(f"❌ Failed to schedule post {post_number}: {e}")
        log_post_status_gsheet(post_number, category, f"❌ {error_msg}", schedule_time, message or "", channel_id)

def match_image_to_post(post_number: int, image_filenames: list[str]) -> str | None:
    """
    Find image filename matching post_number with ultra-flexible naming:
    Matches: 'post-1.jpg', 'post_01-final.png', 'post1.jpeg', 'Post 1.jpg',
            '**post-1**.png', 'post**-1**.jpg', 'POST_1.gif', etc.
    Returns filename if found, else None.
    """
    if not image_filenames:
        return None
    
    # Multiple patterns for maximum flexibility
    post_str_patterns = [
        rf'(?:\*{{0,2}})\s*post\s*[-_\s]*0*{post_number}\b',  # post-1, post 1, **post-1**
        rf'post\s*(?:\*{{0,2}})[-_\s]*0*{post_number}\b',     # post**-1**, post_1
        rf'(?:\*{{0,2}})\s*post0*{post_number}\b',            # **post1**, post01
        rf'post[-_]?0*{post_number}(?=[\.\s\*])',             # post-1.jpg, post1.png
    ]

    for filename in image_filenames:
        if not filename:
            continue
            
        filename_clean = filename.lower().strip()
        
        for pattern in post_str_patterns:
            if re.search(pattern, filename_clean, re.IGNORECASE):
                print(f"🎯 Matched image '{filename}' to post {post_number} using pattern: {pattern}")
                return filename
    
    print(f"❓ No image found for post {post_number} in files: {[f for f in image_filenames[:3]]}{'...' if len(image_filenames) > 3 else ''}")
    return None

def validate_post_structure(text_content: str) -> Dict[str, any]:
    """
    Validate and analyze post structure in text content.
    Returns statistics and validation info.
    """
    validation_result = {
        "valid": True,
        "posts_found": 0,
        "posts_with_times": 0,
        "posts_with_categories": 0,
        "errors": [],
        "warnings": [],
        "post_details": []
    }
    
    try:
        posts = extract_all_posts_from_texts([text_content])
        validation_result["posts_found"] = len(posts)
        
        for post_num, post_data in posts.items():
            detail = {
                "post_number": post_num,
                "has_text": bool(post_data.get('text')),
                "has_category": bool(post_data.get('category')),
                "has_custom_time": bool(post_data.get('custom_time')),
                "text_length": len(post_data.get('text', ''))
            }
            
            if post_data.get('category'):
                validation_result["posts_with_categories"] += 1
            
            if post_data.get('custom_time'):
                validation_result["posts_with_times"] += 1
                # Validate time format
                parsed_time = parse_custom_time(post_data['custom_time'], datetime.now())
                if not parsed_time:
                    validation_result["errors"].append(f"Invalid time format in post {post_num}: {post_data['custom_time']}")
                    validation_result["valid"] = False
            
            if not post_data.get('text') or len(post_data.get('text', '').strip()) < 10:
                validation_result["warnings"].append(f"Post {post_num} has very short or no text content")
            
            validation_result["post_details"].append(detail)
    
    except Exception as e:
        validation_result["valid"] = False
        validation_result["errors"].append(f"Failed to parse posts: {str(e)}")
    
    return validation_result

def group_posts_by_date(posts):
    """Group posts by date for separate worksheets"""
    from collections import defaultdict
    
    date_groups = defaultdict(list)
    
    for post in posts:
        # Extract date from post time
        post_date = datetime.strptime(post["time"], "%Y-%m-%d %H:%M:%S").date()
        date_str = post_date.strftime("%d_%b_%Y")  # Format: 22_Sep_2025
        date_groups[date_str].append(post)
    
    return dict(date_groups)
# Add this missing function to your telegram_utils.py (around line 70, after other utility functions)

def extract_links(text: str):
    """Extract links from text content"""
    if not text:
        return []
    url_pattern = re.compile(r"(https?://\S+|amzaff\.in/\S+)")
    links = url_pattern.findall(text)
    return [str(l).strip() for l in links if l]

# FIXED: Update the get_channel_sheet_id function to handle channel name properly
def get_channel_sheet_id(channel_name: str):
    """
    Map channel names to their dedicated Google Sheet IDs
    """
    # Clean the channel name - remove @ if present
    clean_channel_name = channel_name.replace('@', '')
    
    CHANNEL_SHEETS = {
        'amazonindiaassociates': '18HviAE73HrRThTlotvUIPWAbRIlIH17MGBUNj4-2Hgw',
        'Amazon_Associates_FashionBeauty': '1Nq1R38-uYLVPzdH2yGorG7XVyfLcxVTBEYQUqF7J_sQ', 
        'Amazon_Associates_HomeKitchen': '12vjND6MPAXR_5heIdBqUaGOf4VVvUQvONRkLwcmE7UA',
        'Amazon_Associates_Consumables': '1smDQFHgQ0HT2_R8nKFgY527wqbdFUuyeHLbL6zWgmk0'
    }
    
    sheet_id = CHANNEL_SHEETS.get(clean_channel_name, None)
    if sheet_id:
        print(f"📊 Using dedicated sheet for {clean_channel_name}: {sheet_id}")
        return sheet_id
    else:
        print(f"⚠️ No dedicated sheet found for {clean_channel_name}, using default: {SHEET_ID}")
        return SHEET_ID

# FIXED: Update create_channel_date_worksheet with better logging
def create_channel_date_worksheet(channel_name: str, date_str: str, headers: List[str], scheduled: bool = False):
    """Create worksheet with format: 'DD Mon YYYY' or 'DD Mon YYYY - Scheduled Posts' """
    global gc
    if not gc:
        print("🔄 Initializing Google Sheets connection...")
        if not initialize_google_sheets():
            print("❌ Failed to initialize Google Sheets")
            return None

    try:
        # Get the correct sheet ID for this channel
        sheet_id = get_channel_sheet_id(channel_name)
        sh = gc.open_by_key(sheet_id)

        # Convert "22_Sep_2025" → "22 Sep 2025"
        try:
            date_obj = datetime.datetime.strptime(date_str, "%d_%b_%Y")
            worksheet_name = date_obj.strftime("%d %b %Y")
        except Exception:
            worksheet_name = date_str.replace("_", " ")

        #  If scheduled, append suffix to keep sheet separate
        if scheduled:
            worksheet_name += " - Scheduled Posts"

        print(f"📝 Looking for worksheet: {worksheet_name}")

        # Check if worksheet already exists
        try:
            ws = sh.worksheet(worksheet_name)
            print(f"📋 Worksheet '{worksheet_name}' already exists in sheet {sheet_id}")
            return ws
        except gspread.WorksheetNotFound:
            # Create new worksheet
            ws = sh.add_worksheet(title=worksheet_name, rows=1000, cols=20)
            ws.append_row(headers)
            print(f"✅ Created new worksheet: '{worksheet_name}'")
            return ws

    except Exception as e:
        print(f"❌ Worksheet creation error for {channel_name}: {e}")
        return None

# FIXED: Update save_posts_to_channel_date_sheets with better logging
# telegram_utils.py (Updated sections for click tracking)

# Add this to your existing telegram_utils.py file
# This shows the updated save_posts_to_channel_date_sheets function
import os
import requests

API_URL = os.getenv("LINK_CLICKS_API")
API_KEY = "f073c95a0227414d8e053fdfa19ece0dbe29ea9a8b3fb08e2c8186fabce64bb4"
def get_click_data_for_links(links, date_str):
    """
    Return dict with totals and per-link clicks.
    """
    telegram_total = 0
    whatsapp_total = 0
    telegram_per_link = {}
    whatsapp_per_link = {}

    for link in links:
        print(f"Fetching clicks for {link}")
        normalized_link = link.replace("http://", "").replace("https://", "")
        print(f"⚠️ Fetching clicks for {normalized_link}")
        headers = {"X-API-KEY": API_KEY, "Content-Type": "application/json"}
        payload = {"shortened_url": normalized_link, "date": date_str}
        print(f"Payload {payload}")

        try:
            response = requests.post(API_URL, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()  
            print(f"Response {data}")
        except Exception as e:
            print(f"⚠️ Error fetching clicks for {normalized_link}: {e}")
            continue

        for item in data:
            acc = item.get("account")
            clicks = item.get("clicks", 0)
            shortened_url = item.get("shortened_url", normalized_link)

            if acc == "telegram":
                telegram_total += clicks
                telegram_per_link[shortened_url] = clicks
            elif acc == "whatsapp":
                whatsapp_total += clicks
                whatsapp_per_link[shortened_url] = clicks

    return {
        "telegram_clicks": telegram_total,
        "whatsapp_clicks": whatsapp_total,
        "telegram_clicks_per_link": telegram_per_link,
        "whatsapp_clicks_per_link": whatsapp_per_link
    }


def save_posts_to_channel_date_sheets(posts: list, channel: str, scheduled: bool = False):
    """
    Save posts to Google Sheets per channel and date, including click data.
    Each link and its clicks are recorded in separate columns.
    """
    if not posts:
        return "No posts to save."

    sheet_id = get_channel_sheet_id(channel)
    sh = gc.open_by_key(sheet_id)

    headers = ["Post Number", "Category", "Time", "Status", "Message", "Channel",
               "Links", "Telegram Clicks", "WhatsApp Clicks"]

    for post_num, post in enumerate(posts, start=1):
        # Get message text
        post_text = post.get("text") or post.get("message") or ""
        
        # Get category
        category = post.get("category") or post.get("category_name") or ""
        
        # Get post time
        post_time = post.get("time") or post.get("custom_time") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        date_only = post_time.split(" ")[0]
        
        # Extract links if not present
        links = post.get("links") or extract_links(post_text)
        
        # Get click data
        click_data = get_click_data_for_links(links, date_only)
        
        telegram_clicks_str = ", ".join([f"{l} ({c})" for l, c in click_data["telegram_clicks_per_link"].items()])
        whatsapp_clicks_str = ", ".join([f"{l} ({c})" for l, c in click_data["whatsapp_clicks_per_link"].items()])
        
        # Create or get worksheet
        post_date_str = datetime.strptime(date_only, "%Y-%m-%d").strftime("%d_%b_%Y")
        ws = create_channel_date_worksheet(channel, post_date_str, headers, scheduled)
        if not ws:
            print(f"❌ Unable to get worksheet for {channel} {post_date_str}")
            continue
        
        # Determine next empty row
        next_row = len(ws.get_all_values()) + 1
        
        # Build row
        row_data = [
            post_num,
            category,
            post_time,
            post.get("status", "Live"),
            post_text,
            channel,
            ", ".join(links),
            telegram_clicks_str,
            whatsapp_clicks_str
        ]
        
        ws.insert_row(row_data, next_row)
        print(f"✅ Post {post_num} saved to {channel} sheet '{ws.title}'")


    return f"✅ {len(posts)} posts saved to {channel} sheet."

# Alternative helper function to separate links by platform
def categorize_links_by_platform(links):
    """
    Categorize links based on their domain
    Returns dict with telegram_links and whatsapp_links
    """
    telegram_links = []
    whatsapp_links = []
    
    for link in links:
        link_lower = link.lower()
        # You can customize these patterns based on your link structure
        if 'amzaff.in' in link_lower:
            # Telegram links typically use .in domain
            telegram_links.append(link)
        elif 'amzaff.to' in link_lower:
            # WhatsApp links typically use .to domain
            whatsapp_links.append(link)
        else:
            # Default: add to both or handle based on your logic
            telegram_links.append(link)
    
    return {
        "telegram_links": telegram_links,
        "whatsapp_links": whatsapp_links
    }