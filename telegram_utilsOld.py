#telegram_utils.py
import os
import pandas as pd
from dotenv import load_dotenv
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from datetime import datetime,timezone
import re
from typing import Dict, List
from telegram_scheduler import TelegramScheduler
from datetime import datetime
from telethon.tl.functions.messages import SendMessageRequest, SendMediaRequest
from telethon.tl.types import InputPeerChannel, InputMediaUploadedPhoto, InputMediaUploadedDocument
import gspread
from google.oauth2.service_account import Credentials
import pytz

# --- Google Sheets Setup ---
SERVICE_ACCOUNT_FILE = "E:/Telegram_scheduler_python/backend/service_account.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", 
          "https://www.googleapis.com/auth/drive"]
SHEET_ID = "1seb2pGu1XekQmNcHC-6Ma_y9tGRyhTo33PrR8sA-EBc"  # from your sheet URL

# Global variables for sheet connection
gc = None
sheet = None

def initialize_google_sheets():
    """Initialize Google Sheets connection with proper error handling"""
    global gc, sheet
    try:
        creds = Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
        gc = gspread.authorize(creds)
        sheet = gc.open_by_key(SHEET_ID).sheet1
        
        # Ensure headers exist in the sheet
        try:
            headers = sheet.row_values(1)
            expected_headers = ["Post Number", "Category", "Date", "Time", "Status", "Message"]
            
            if not headers or headers != expected_headers:
                print("Setting up sheet headers...")
                sheet.clear()
                sheet.append_row(expected_headers)
                
        except Exception as header_error:
            print(f"Header setup error: {header_error}")
            sheet.append_row(["Post Number", "Category", "Date", "Time", "Status", "Message"])
        
        print("✅ Google Sheets connection successful")
        return True
    except FileNotFoundError:
        print(f"❌ Service account file not found: {SERVICE_ACCOUNT_FILE}")
        return False
    except Exception as e:
        import traceback
        print(f"❌ Google Sheets setup error: {type(e).__name__}: {e}")
        traceback.print_exc()
        return False

# Initialize sheets connection
sheets_available = initialize_google_sheets()

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

            # Extract content between start and end
            content = text[start_pos:end_pos].strip()
            
            # Parse the content
            lines = content.splitlines()
            category = None
            custom_time = None
            text_lines = []
            
            for line in lines:
                line_clean = line.strip()
                if not line_clean:
                    continue
                    
                # Check for category
                if line_clean.lower().startswith("category:"):
                    category = line_clean[len("category:"):].strip()
                    continue
                
                # Check for time
                time_match = time_pattern.search(line)
                if time_match:
                    custom_time = time_match.group(1)
                    print(f"🕐 Found custom time for post {post_num}: {custom_time}")
                    continue
                
                # Regular content line
                text_lines.append(line)

            clean_text = "\n".join(text_lines).strip()
            
            posts[post_num] = {
                "category": category,
                "text": clean_text,
                "custom_time": custom_time  # New field for custom time
            }
            
            print(f"📋 Extracted Post {post_num}: Category='{category}', CustomTime='{custom_time}', TextLength={len(clean_text)}")

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

def log_post_status_gsheet(post_number, category, status, schedule_time, message):
    """Log post status to Google Sheets with consistent formatting"""
    try:
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
            message_truncated
        ]
        
        # Log to console for debugging
        print(f"📝 Logging: Post {post_number} | {category} | {date_str} {time_str} | {status}")
        
        # Append to sheet
        success = append_row_to_sheet(values)
        
        if not success:
            # Fallback to local file logging if Google Sheets fails
            log_post_status_local_fallback(post_number, category, status, schedule_time, message)
            
    except Exception as e:
        print(f"❌ Error in log_post_status_gsheet: {e}")
        # Fallback to local logging
        log_post_status_local_fallback(post_number, category, status, schedule_time, message)

def log_post_status_local_fallback(post_number, category, status, schedule_time, message):
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

def get_blocked_times_from_sheet():
    """Return list of datetime objects (blocked slots) from Google Sheet logs"""
    if not sheets_available or not sheet:
        print("⚠️ Google Sheets not available, returning empty blocked times")
        return []
    
    blocked = []
    try:
        records = sheet.get_all_records()  # Returns list of dicts
        for rec in records:
            date = rec.get("Date", "").strip()
            time = rec.get("Time", "").strip()
            status = str(rec.get("Status", "")).strip()

            if not date or not time:
                continue

            # Block both ✅ and ❌ posts so slots aren't reused
            if status:
                try:
                    dt_str = f"{date} {time}"
                    # Try flexible parsing with multiple formats
                    dt = None
                    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M"]:
                        try:
                            dt = datetime.strptime(dt_str, fmt)
                            break
                        except ValueError:
                            continue
                    
                    if dt:
                        blocked.append(dt)
                    else:
                        print(f"⚠️ Could not parse datetime: {dt_str}")
                        
                except Exception as e:
                    print(f"⚠️ Skipping invalid datetime row: {rec} ({e})")
                    
    except Exception as e:
        print(f"❌ Error reading blocked times from sheet: {e}")

    print(f"📊 Found {len(blocked)} blocked time slots")
    return blocked

async def send_telegram_message(image_path: str, post_text: str, post_number: int, category: str, schedule_time: datetime):
    """Send Telegram message with improved error handling and consistent logging"""
    try:
        if not client.is_connected():
            await client.connect()
        if not await client.is_user_authorized():
            raise Exception("Telegram client not authorized")

        entity = await client.get_entity(target_channel)

        # Upload image if exists
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
                print(f"📤 Sent image with caption for post {post_number}")
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
                print(f"📤 Sent image + separate text for post {post_number}")
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
        log_post_status_gsheet(post_number, category, "✅ Scheduled", schedule_time, message)
        
    except Exception as e:
        error_msg = f"Failed: {str(e)}"
        print(f"❌ Failed to schedule post {post_number}: {e}")
        log_post_status_gsheet(post_number, category, f"❌ {error_msg}", schedule_time, message or "")

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