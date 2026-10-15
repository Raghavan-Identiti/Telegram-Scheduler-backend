# app/services/telegram_utils.py
import os
import json
import time
from functools import wraps
import pandas as pd
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession
from datetime import datetime, timezone, timedelta
import re
from typing import Dict, List, Any, Optional, Tuple
import gspread
from google.oauth2 import service_account
import pytz

load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

DEFAULT_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "1seb2pGu1XekQmNcHC-6Ma_y9tGRyhTo33PrR8sA-EBc")
SHEET_ID = DEFAULT_SHEET_ID

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
    },
    'amazoninfluencerprogramindia': {
        'username': 'amazoninfluencerprogramindia',
        'sheet_name': 'Amazon Influencer Program India'
    }
}

def get_telethon_creds() -> Tuple[int, str, str]:
    raw_id = (
        os.getenv("TELEGRAM_API_ID") or
        os.getenv("API_ID") or
        os.getenv("TG_API_ID") or
        "2040"
    )
    try:
        api_id_int = int(str(raw_id).strip())
    except Exception:
        api_id_int = 2040

    api_hash_val = (
        os.getenv("TELEGRAM_API_HASH") or
        os.getenv("API_HASH") or
        os.getenv("TG_API_HASH") or
        ""
    ).strip()

    session_str = (
        os.getenv("TELEGRAM_SESSION_STRING") or
        os.getenv("SESSION_STRING") or
        os.getenv("STRING_SESSION") or
        os.getenv("TELEGRAM_SESSION") or
        os.getenv("TELEGRAM_STRING_SESSION") or
        os.getenv("TELETHON_SESSION") or
        ""
    ).strip()

    return api_id_int, api_hash_val, session_str

api_id, api_hash, session_string = get_telethon_creds()

gc: Optional[gspread.Client] = None
sheets_available = False
service_account_email = ""

MAX_CAPTION_LENGTH = 1024
MAX_TEXT_LENGTH = 4096
CAPTION_SAFETY_BUFFER = 50
MESSAGE_DELAY_MINUTES = 3
GSHEET_RETRIES = 3
GSHEET_RETRY_DELAY = 2

def get_settings_file_path() -> str:
    candidates = [
        os.path.join(os.getcwd(), "settings.json"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "settings.json"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "settings.json"),
        "/app/settings.json",
        "settings.json"
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return candidates[0]

def load_settings() -> Dict[str, Any]:
    filepath = get_settings_file_path()
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Error reading settings: {e}")
    return {"auto_fetch_enabled": True, "channel_sheets": {}}

def save_settings(settings: Dict[str, Any]) -> None:
    filepath = get_settings_file_path()
    try:
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
        print(f"💾 Settings saved successfully to {filepath}")
    except Exception as e:
        print(f"⚠️ Error saving settings to {filepath}: {e}")

def extract_sheet_id_from_url(url_or_id: str) -> str:
    if not url_or_id:
        return ""
    url_str = str(url_or_id).strip()
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url_str)
    if match:
        return match.group(1)
    return url_str

def initialize_google_sheets() -> bool:
    global gc, sheets_available, service_account_email
    try:
        google_creds_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
        if not google_creds_json:
            sheets_available = False
            return False

        creds_dict = json.loads(google_creds_json)
        service_account_email = creds_dict.get("client_email", "")
        creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        gc = gspread.authorize(creds)
        sheets_available = True
        return True
    except Exception as e:
        print(f"❌ Failed to authorize Google Sheets: {e}")
        sheets_available = False
        return False

def get_channel_sheet_target(channel_username: str) -> Tuple[str, str]:
    clean_username = channel_username.replace("@", "").strip().lower()
    settings = load_settings()
    channel_sheets = settings.get("channel_sheets", {})

    matched_config = None
    # 1. Exact or normalized key matching
    for k, v in channel_sheets.items():
        k_clean = k.replace("@", "").strip().lower()
        if k_clean == clean_username or k_clean == clean_username.replace("_", "").replace("-", ""):
            matched_config = v
            break

    # 2. Match against CHANNELS map
    default_tab = clean_username
    for cid, data in CHANNELS.items():
        if data["username"].lower() == clean_username or cid.lower() == clean_username:
            default_tab = data["sheet_name"]
            if not matched_config:
                for k, v in channel_sheets.items():
                    k_clean = k.replace("@", "").strip().lower()
                    if k_clean == cid.lower() or k_clean == data["username"].lower():
                        matched_config = v
                        break
            break

    if matched_config:
        surl = matched_config.get("sheet_url") or matched_config.get("sheetUrl") or ""
        sid = matched_config.get("sheet_id") or matched_config.get("sheetId") or extract_sheet_id_from_url(surl)
        tab = (
            matched_config.get("sheet_tab") or
            matched_config.get("sheetTab") or
            matched_config.get("tab_name") or
            matched_config.get("targetTab") or
            default_tab
        )
        if sid and sid.strip():
            return sid.strip(), (tab or default_tab).strip()

    return DEFAULT_SHEET_ID, default_tab

def extract_links(text: str) -> List[str]:
    if not text:
        return []
    url_pattern = re.compile(r"[*_()<>]*\b(https?://\S+|amzaff\.in/\S+)\b[*_()<>]*", re.IGNORECASE)
    links = url_pattern.findall(text)
    return [re.sub(r"^[*_()<>]+|[*_()<>.,!?]+$", "", link).strip() for link in links if link.strip()]

def get_click_data_for_links(links: List[str], date_str: str) -> Dict[str, int]:
    from app.services.clicksFind import get_clicks
    total_tg = 0
    total_wa = 0
    for link in links:
        data = get_clicks(link, date_str)
        if data and isinstance(data, list):
            for entry in data:
                acc = str(entry.get("account", "")).lower()
                clicks = int(entry.get("clicks", 0) or 0)
                if "telegram" in acc or "tg" in acc:
                    total_tg += clicks
                elif "whatsapp" in acc or "wa" in acc:
                    total_wa += clicks
                else:
                    total_tg += clicks
    return {"telegram_clicks": total_tg, "whatsapp_clicks": total_wa}

def extract_all_posts_from_texts(text_blocks: List[str]) -> Dict[int, Dict[str, Any]]:
    posts = {}
    post_start_pattern = re.compile(
        r'(?:^|\n)\s*(?:\*{0,2})\s*post\s*[-_\s]*(\d+)\s*(?:\*{0,2})\s*(?:\n|$)',
        re.IGNORECASE | re.MULTILINE
    )
    section_start_pattern = re.compile(r'AMZ_TELEGRAM', re.IGNORECASE)
    time_pattern = re.compile(
        r'(?:^|\n)\s*time\s*[:\-=]\s*(\d{1,2}:\d{2}(?::\d{2})?)\s*(?:am|pm)?\s*(?:\n|$)',
        re.IGNORECASE | re.MULTILINE
    )

    for text in text_blocks:
        sec = section_start_pattern.search(text)
        if sec:
            text = text[sec.end():]

        start_matches = list(post_start_pattern.finditer(text))
        for i, sm in enumerate(start_matches):
            post_num = int(sm.group(1))
            start_pos = sm.end()
            end_pos = len(text)

            specific_end = re.compile(
                rf'(?:^|\n)\s*(?:\*{{0,2}})\s*post\s*[-_\s]*{post_num}\s*(?:end|copy|finish|done)\s*(?:\*{{0,2}})\s*(?:\n|$)',
                re.IGNORECASE | re.MULTILINE
            )
            em = specific_end.search(text[start_pos:])
            if em:
                end_pos = start_pos + em.start()
            elif i + 1 < len(start_matches):
                end_pos = start_matches[i + 1].start()

            content = text[start_pos:end_pos]
            lines = content.splitlines()
            category = None
            custom_time = None
            text_lines = []

            for line in lines:
                s = line.strip()
                if s.lower().startswith("category:"):
                    category = s[9:].strip()
                    continue
                tm = time_pattern.search(line)
                if tm:
                    custom_time = tm.group(1)
                    continue
                text_lines.append(line)

            clean = "\n".join(text_lines).rstrip()
            posts[post_num] = {
                "category": category,
                "text": clean,
                "custom_time": custom_time
            }
    return posts

def get_blocked_times_from_sheet(channels: List[str]) -> List[datetime]:
    global gc, sheets_available
    blocked = []
    if not sheets_available or not gc:
        initialize_google_sheets()
        if not sheets_available or not gc:
            return blocked

    # Try reading existing scheduled times
    try:
        sh = gc.open_by_key(DEFAULT_SHEET_ID)
        for ws in sh.worksheets()[:2]:
            try:
                records = ws.get_all_values()
                for row in records[1:]:
                    if len(row) > 1 and row[1]:
                        try:
                            t_str = row[1].replace("IST", "").strip()
                            dt = datetime.strptime(t_str, "%Y-%m-%d %H:%M:%S")
                            blocked.append(dt)
                        except Exception:
                            pass
            except Exception:
                pass
    except Exception as e:
        print(f"⚠️ Error reading blocked times from sheet: {e}")
    return blocked

def save_posts_to_channel_date_sheets(
    posts_data: List[Dict[str, Any]],
    channel_username: str,
    scheduled: bool = False,
    override_sheet_id: Optional[str] = None,
    override_sheet_tab: Optional[str] = None
) -> str:
    """
    ⚡ DYNAMIC BATCH SHEET WRITER ⚡
    Uses dynamic Google Sheet from frontend settings, falls back to default if failed,
    and batch writes in 1 single call!
    """
    global gc, sheets_available
    if not sheets_available or not gc:
        initialize_google_sheets()
        if not sheets_available or not gc:
            return "Google Sheets service account not authorized. Scraped posts returned."

    if not posts_data:
        return "No posts to write."

    # 1. Look up dynamic sheet ID and target tab
    target_sheet_id = override_sheet_id
    target_tab_name = override_sheet_tab

    if not target_sheet_id or not target_tab_name:
        dyn_id, dyn_tab = get_channel_sheet_target(channel_username)
        target_sheet_id = target_sheet_id or dyn_id
        target_tab_name = target_tab_name or dyn_tab

    target_sheet_id = (target_sheet_id or DEFAULT_SHEET_ID).strip()
    target_tab_name = (target_tab_name or "Posts").strip()
    if not target_tab_name:
        target_tab_name = "Posts"

    # 2. Try Opening Dynamic Sheet; Fallback to Default
    workbook = None
    used_fallback = False

    try:
        workbook = gc.open_by_key(target_sheet_id)
    except Exception as e:
        print(f"⚠️ Could not open dynamic sheet '{target_sheet_id}': {e}. Falling back to default '{DEFAULT_SHEET_ID}'...")
        try:
            workbook = gc.open_by_key(DEFAULT_SHEET_ID)
            used_fallback = True
        except Exception as e2:
            return f"Notice: Could not access Google Sheets ({e2}). Ensure sheet is shared with {service_account_email}"

    if not workbook:
        return "Notice: Google Sheets not accessible"

    try:
        try:
            ws = workbook.worksheet(target_tab_name)
        except gspread.WorksheetNotFound:
            ws = workbook.add_worksheet(title=target_tab_name, rows=1000, cols=10)
            headers = ["Post ID", "Date & Time (IST)", "Views", "Telegram Clicks", "WhatsApp Clicks", "Links", "Text", "Status"]
            ws.append_row(headers)

        rows_to_insert = []
        for post in posts_data:
            time_val = str(post.get("time") or post.get("date_time") or post.get("date") or "")
            views_val = post.get("views") or post.get("Views") or 0
            tg_clicks = post.get("Telegram-clicks") or post.get("telegram_clicks") or post.get("Telegram_clicks") or 0
            wa_clicks = post.get("Whatsapp-clicks") or post.get("whatsapp_clicks") or post.get("Whatsapp_clicks") or 0
            links_list = post.get("links") or post.get("Links") or []
            links_val = ", ".join(links_list) if isinstance(links_list, list) else str(links_list)
            text_val = str(post.get("text") or post.get("message") or post.get("Full_Text") or "").replace("\n", " ").strip()[:500]
            status_val = "Scheduled" if scheduled else str(post.get("status") or "Live")
            post_id = str(post.get("id") or post.get("post_id") or post.get("postNumber") or "")

            rows_to_insert.append([
                post_id,
                time_val,
                views_val,
                tg_clicks,
                wa_clicks,
                links_val,
                text_val,
                status_val
            ])

        ws.append_rows(rows_to_insert, value_input_option="USER_ENTERED")
        fallback_note = " (Fallback default sheet used - share new sheet with editor rights)" if used_fallback else ""
        return f"✅ Saved {len(rows_to_insert)} posts to '{target_sheet_id}' [{target_tab_name}]{fallback_note}"

    except Exception as e:
        print(f"❌ Error writing batch rows: {e}")
        return f"Posts scraped, notice writing to Google Sheet: {e}"

async def send_telegram_message(
    image_path: Optional[str],
    post_text: Optional[str],
    post_number: Any,
    category: Optional[str],
    schedule_time: datetime,
    channel_username: Optional[str] = None,
    channel_id: Optional[str] = None
):
    """Schedules or dispatches message to Telegram channel"""
    global api_id, api_hash, session_string
    target_channel = channel_username or "amazonindiaassociates"
    
    async with TelegramClient(StringSession(session_string), api_id, api_hash) as client:
        caption = post_text or ""
        if image_path and os.path.exists(image_path):
            await client.send_file(
                entity=target_channel,
                file=image_path,
                caption=caption[:1024],
                schedule_date=schedule_time
            )
        elif post_text:
            await client.send_message(
                entity=target_channel,
                message=post_text[:4096],
                schedule_date=schedule_time
            )
