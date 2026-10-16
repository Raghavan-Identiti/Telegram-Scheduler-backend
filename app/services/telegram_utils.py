# app/services/telegram_utils.py
import os
import json
import time
from functools import wraps
import pandas as pd
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession
from datetime import datetime, date, timezone, timedelta
import re
from typing import Dict, List, Any, Optional, Tuple
from dateutil import parser
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

def get_ordinal_suffix(day: int) -> str:
    if 11 <= day <= 13:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")

def get_date_tab_title(d: date) -> str:
    """Standard date tab format: e.g. '17th Oct'"""
    day = d.day
    suffix = get_ordinal_suffix(day)
    month_abbr = d.strftime("%b")
    return f"{day}{suffix} {month_abbr}"

def get_date_candidates(d: date) -> List[str]:
    """Generate variations of the date name to find existing subsheets"""
    day = d.day
    suffix = get_ordinal_suffix(day)
    m_abbr = d.strftime("%b")
    m_full = d.strftime("%B")
    year = d.year
    return [
        f"{day}{suffix} {m_abbr}",          # 17th Oct
        f"{day} {m_abbr}",                  # 17 Oct
        f"{day}{suffix}_{m_abbr}",          # 17th_Oct
        f"{day}_{m_abbr}",                  # 17_Oct
        f"{day}{suffix} {m_abbr} {year}",   # 17th Oct 2026
        f"{day} {m_abbr} {year}",           # 17 Oct 2026
        f"{day}{suffix} {m_full}",          # 17th October
        f"{day} {m_full}",                  # 17 October
        d.strftime("%Y-%m-%d"),             # 2026-10-17
        d.strftime("%d-%m-%Y"),             # 17-10-2026
        d.strftime("%d-%b-%Y"),             # 17-Oct-2026
        d.strftime("%d-%b"),                # 17-Oct
        d.strftime("%d/%m/%Y"),             # 17/10/2026
    ]

def find_or_create_date_worksheet(workbook: gspread.Spreadsheet, d: date) -> gspread.Worksheet:
    """Finds an existing subsheet for this date or creates a new one at the bottom"""
    standard_title = get_date_tab_title(d)
    candidates = [c.lower().replace(" ", "").replace("_", "").replace("-", "") for c in get_date_candidates(d)]
    
    # 1. Check existing worksheets in the spreadsheet
    existing_sheets = workbook.worksheets()
    for ws in existing_sheets:
        norm_title = ws.title.lower().replace(" ", "").replace("_", "").replace("-", "")
        if norm_title in candidates:
            return ws

    # 2. Check if the spreadsheet is brand new with an empty default "Sheet1"
    if len(existing_sheets) == 1 and existing_sheets[0].title.lower() in ["sheet1", "sheet 1"]:
        try:
            if not existing_sheets[0].get_all_values():
                existing_sheets[0].update_title(standard_title)
                return existing_sheets[0]
        except Exception:
            pass

    # 3. Create a new subsheet at the bottom
    ws = workbook.add_worksheet(title=standard_title, rows=1000, cols=10)
    return ws

def extract_post_ist_date(post: Dict[str, Any]) -> date:
    """Extracts the IST calendar date from a post record"""
    for key in ["time", "date_time", "date", "DateTime", "Date & Time (IST)"]:
        raw = post.get(key)
        if raw:
            if isinstance(raw, datetime):
                dt = raw
            elif isinstance(raw, date):
                return raw
            elif isinstance(raw, str) and raw.strip():
                try:
                    clean = raw.replace("IST", "").strip()
                    dt = parser.parse(clean)
                except Exception:
                    continue
            else:
                continue

            if dt.tzinfo is None:
                dt = ist.localize(dt)
            else:
                dt = dt.astimezone(ist)
            return dt.date()

    return datetime.now(ist).date()

def save_posts_to_channel_date_sheets(
    posts_data: List[Dict[str, Any]],
    channel_username: str,
    scheduled: bool = False,
    override_sheet_id: Optional[str] = None,
    override_sheet_tab: Optional[str] = None
) -> str:
    """
    ⚡ DYNAMIC CHANNEL SPREADSHEET & DAILY SUBSHEETS WRITER ⚡
    - For each channel, there is ONE dedicated Google Sheet link (e.g. for @amazonindiaassociates).
    - In that sheet, each day has its individual subsheet at the bottom (e.g. '17th Oct', '16th Oct').
    - When running the Content Reader in a date range (date A to date B), posts are grouped by
      date, and each date's posts are cleanly synced into their respective daily subsheet!
    """
    global gc, sheets_available
    if not sheets_available or not gc:
        initialize_google_sheets()
        if not sheets_available or not gc:
            return "Google Sheets service account not authorized. Scraped posts returned."

    if not posts_data:
        return "No posts to write."

    # 1. Determine Target Channel Spreadsheet ID
    target_sheet_id = override_sheet_id
    if not target_sheet_id:
        dyn_id, _ = get_channel_sheet_target(channel_username)
        target_sheet_id = dyn_id or DEFAULT_SHEET_ID

    target_sheet_id = str(target_sheet_id or DEFAULT_SHEET_ID).strip()

    # 2. Open Target Channel Sheet; Fallback to Default if needed
    workbook = None
    used_fallback = False

    try:
        workbook = gc.open_by_key(target_sheet_id)
    except Exception as e:
        print(f"⚠️ Could not open sheet '{target_sheet_id}': {e}. Falling back to default '{DEFAULT_SHEET_ID}'...")
        try:
            workbook = gc.open_by_key(DEFAULT_SHEET_ID)
            used_fallback = True
            target_sheet_id = DEFAULT_SHEET_ID
        except Exception as e2:
            return f"Notice: Could not access Google Sheets ({e2}). Ensure sheet is shared with: {service_account_email}"

    if not workbook:
        return "Notice: Google Sheets not accessible"

    # 3. Group all scraped posts by their individual IST calendar date
    posts_by_date: Dict[date, List[Dict[str, Any]]] = {}
    for post in posts_data:
        d = extract_post_ist_date(post)
        posts_by_date.setdefault(d, []).append(post)

    headers = [
        "Post ID",
        "Date & Time (IST)",
        "Views",
        "Telegram Clicks",
        "WhatsApp Clicks",
        "Links",
        "Text",
        "Status"
    ]

    synced_summary = []

    # 4. Write each day's posts into that day's individual subsheet at the bottom
    for d in sorted(posts_by_date.keys()):
        day_posts = posts_by_date[d]
        try:
            ws = None
            known_channel_names = [
                channel_username.lower().replace("@", "").strip(),
                "amazon_india_associates", "fashion_beauty", "home_kitchen", "consumables", "posts"
            ]
            # If user explicitly requested a specific non-channel tab name for a single date
            if (
                override_sheet_tab and
                len(posts_by_date) == 1 and
                override_sheet_tab.lower().strip() not in known_channel_names
            ):
                try:
                    ws = workbook.worksheet(override_sheet_tab.strip())
                except gspread.WorksheetNotFound:
                    ws = workbook.add_worksheet(title=override_sheet_tab.strip(), rows=1000, cols=10)

            if ws is None:
                ws = find_or_create_date_worksheet(workbook, d)

            # Build rows to insert
            rows_to_insert = []
            for post in day_posts:
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

            # Write headers and fresh rows in one clean update
            full_table = [headers] + rows_to_insert
            try:
                ws.clear()
                try:
                    ws.update("A1", full_table, value_input_option="USER_ENTERED")
                except TypeError:
                    ws.update(full_table, value_input_option="USER_ENTERED")
            except Exception as e_up:
                print(f"⚠️ ws.update fallback for subsheet '{ws.title}': {e_up}")
                try:
                    ws.append_rows(rows_to_insert, value_input_option="USER_ENTERED")
                except Exception as e_app:
                    print(f"❌ Error appending rows to subsheet '{ws.title}': {e_app}")

            synced_summary.append(f"{ws.title} ({len(rows_to_insert)} posts)")

        except Exception as e_day:
            print(f"❌ Error syncing date subsheet for date {d}: {e_day}")
            synced_summary.append(f"{get_date_tab_title(d)} (notice: {e_day})")

    fallback_note = " (Fallback default sheet used - share new sheet with editor rights)" if used_fallback else ""
    return f"✅ Synced {len(posts_data)} posts into {len(synced_summary)} daily subsheets in Google Sheet: {', '.join(synced_summary)}{fallback_note}"

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
