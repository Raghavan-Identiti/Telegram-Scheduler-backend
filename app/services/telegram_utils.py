# app/services/telegram_utils.py
import os
import json
import time
from functools import wraps
import pandas as pd
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession
import urllib.request
from datetime import datetime, date, timezone, timedelta
import re
from typing import Dict, List, Any, Optional, Tuple
from dateutil import parser
import gspread
from google.oauth2 import service_account
import pytz

load_dotenv()

ist = pytz.timezone("Asia/Kolkata")

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
            settings = load_settings()
            google_creds_json = settings.get("google_service_account_json") or settings.get("service_account_json")
        if not google_creds_json:
            for fname in ["service_account.json", "credentials.json", "google_credentials.json", "/app/service_account.json", "app/service_account.json"]:
                if os.path.exists(fname):
                    try:
                        with open(fname, "r", encoding="utf-8") as f:
                            google_creds_json = f.read()
                            break
                    except Exception:
                        pass

        if not google_creds_json:
            sheets_available = False
            return False

        creds_dict = json.loads(google_creds_json) if isinstance(google_creds_json, str) else google_creds_json
        service_account_email = creds_dict.get("client_email", "")
        creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        gc = gspread.authorize(creds)
        sheets_available = True
        print(f"✅ Google Sheets authorized successfully for: {service_account_email}")
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

def get_date_tab_title(d: date, scheduled: bool = False) -> str:
    """
    Date tab format: strictly the date with ordinal suffix.
    e.g. '15th Oct 2026', '1st Oct 2026', '2nd Oct 2026'.
    """
    day = d.day
    suffix = get_ordinal_suffix(day)
    month = d.strftime("%b")
    year = d.year
    return f"{day}{suffix} {month} {year}"

def get_date_candidates(d: date, scheduled: bool = False) -> List[str]:
    """Generate variations of the date name to find existing subsheets"""
    day = d.day
    day_pad = d.strftime("%d")
    m_abbr = d.strftime("%b")
    m_full = d.strftime("%B")
    year = d.year

    suffix = get_ordinal_suffix(day)
    base_variants = [
        f"{day}{suffix} {m_abbr} {year}",           # 15th Oct 2026 / 1st Oct 2026
        f"{day}{suffix} {m_abbr.lower()} {year}",   # 15th oct 2026 / 1st oct 2026
        f"{day}{suffix} {m_full} {year}",           # 15th October 2026
        f"{day}{suffix} {m_full.lower()} {year}",   # 15th october 2026
        f"{day}{suffix} {m_abbr}",                  # 15th Oct
        f"{day}{suffix} {m_abbr.lower()}",          # 15th oct
        f"{day_pad} {m_abbr} {year}",               # 15 Oct 2026 / 01 Oct 2026
        f"{day} {m_abbr} {year}",                   # 15 Oct 2026 / 1 Oct 2026
        f"{day_pad} {m_abbr.lower()} {year}",       # 15 oct 2026 / 01 oct 2026
        f"{day} {m_abbr.lower()} {year}",           # 15 oct 2026 / 1 oct 2026
        f"{day_pad}_{m_abbr}_{year}",               # 15_Oct_2026
        f"{day}_{m_abbr}_{year}",                   # 15_Oct_2026
        f"{day_pad} {m_abbr}",                      # 15 Oct
        f"{day} {m_abbr}",                          # 15 Oct
        f"{day_pad} {m_full} {year}",               # 15 October 2026
        d.strftime("%Y-%m-%d"),                     # 2026-10-15
        d.strftime("%d-%m-%Y"),                     # 15-10-2026
        d.strftime("%d-%b-%Y"),                     # 15-Oct-2026
    ]

    scheduled_variants = [f"{v} - Scheduled Posts" for v in base_variants] + [f"{v} - Scheduled" for v in base_variants]
    return base_variants + scheduled_variants

def find_or_create_date_worksheet(workbook: gspread.Spreadsheet, d: date, scheduled: bool = False) -> gspread.Worksheet:
    """Finds an existing subsheet for this date or creates a new one at the bottom"""
    standard_title = get_date_tab_title(d, scheduled)
    candidates = [c.lower().replace(" ", "").replace("_", "").replace("-", "") for c in get_date_candidates(d, scheduled)]
    
    # 1. Check existing worksheets in the spreadsheet
    existing_sheets = workbook.worksheets()
    for ws in existing_sheets:
        norm_title = ws.title.lower().replace(" ", "").replace("_", "").replace("-", "")
        if norm_title in candidates:
            # If the title was in an older non-ordinal format (e.g. '01 Oct 2026' or '15 Oct 2026'),
            # update it to the user's requested standard date format ('15th Oct 2026')
            if norm_title != standard_title.lower().replace(" ", ""):
                try:
                    ws.update_title(standard_title)
                except Exception:
                    pass
            return ws

    # 2. Check if the spreadsheet is brand new with an empty default "Sheet1"
    if len(existing_sheets) == 1 and existing_sheets[0].title.lower() in ["sheet1", "sheet 1"]:
        try:
            if not existing_sheets[0].get_all_values():
                existing_sheets[0].update_title(standard_title)
                return existing_sheets[0]
        except Exception:
            pass

    # 3. Create a new subsheet at the bottom named strictly with the date
    ws = workbook.add_worksheet(title=standard_title, rows=1000, cols=20)
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

def format_time_12hr(time_str_or_dt: Any) -> str:
    """Formats timestamp into 12-hour AM/PM format (e.g. '7:11 PM') exactly as in screenshot"""
    if not time_str_or_dt:
        return ""
    try:
        if isinstance(time_str_or_dt, datetime):
            dt = time_str_or_dt
        else:
            clean = str(time_str_or_dt).replace("IST", "").strip()
            dt = parser.parse(clean)
        
        # Format as e.g. '7:11 PM'
        hour = dt.hour % 12
        if hour == 0:
            hour = 12
        ampm = "AM" if dt.hour < 12 else "PM"
        return f"{hour}:{dt.minute:02d} {ampm}"
    except Exception:
        return str(time_str_or_dt)

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
    - In that sheet, each day has its individual subsheet at the bottom (e.g. '01 Jul 2026', '10 Aug 2026').
    - When running the Content Reader in a date range (date A to date B), posts are grouped by
      date, and each date's posts are cleanly synced into their respective daily subsheet!
    - Exact columns: Col B=Post Number, Col C=Time, Col D=Status, Col E=Message, Col F=Telegram Links,
      Col G=WhatsApp Links, Col H=Views, Col I=Telegram Clicks, Col J=WhatsApp Clicks.
    - Includes bottom Total row with sums.
    """
    global gc, sheets_available
    if not sheets_available or not gc:
        initialize_google_sheets()
        if not sheets_available or not gc:
            return "Google Sheets service account not authorized. Scraped posts returned."

    if not posts_data:
        return "No posts to write."

    # 1. Determine Target Channel Spreadsheet Link / ID
    target_sheet_input = override_sheet_id
    if not target_sheet_input:
        dyn_id, _ = get_channel_sheet_target(channel_username)
        target_sheet_input = dyn_id or DEFAULT_SHEET_ID

    target_sheet_input = str(target_sheet_input or DEFAULT_SHEET_ID).strip()
    clean_target_id = extract_sheet_id_from_url(target_sheet_input)

    # 2. Open Target Channel Sheet directly (Write ONLY to the given sheet link)
    workbook = None
    try:
        if target_sheet_input.startswith("http"):
            try:
                workbook = gc.open_by_url(target_sheet_input)
            except Exception:
                workbook = gc.open_by_key(clean_target_id)
        else:
            workbook = gc.open_by_key(clean_target_id)
    except Exception as e:
        help_email = f" Please ensure the spreadsheet is shared with Editor permission with: {service_account_email}" if service_account_email else ""
        return f"❌ Could not access your specified sheet link ({target_sheet_input}): {e}.{help_email}"

    if not workbook:
        return f"❌ Could not open target sheet ({target_sheet_input})"

    # 3. Group all scraped posts by their individual IST calendar date
    posts_by_date: Dict[date, List[Dict[str, Any]]] = {}
    for post in posts_data:
        d = extract_post_ist_date(post)
        posts_by_date.setdefault(d, []).append(post)

    # Headers starting strictly at Column A matching user screenshot
    headers = [
        "Post Number",
        "Time",
        "Status",
        "Message",
        "Telegram Links",
        "WhatsApp Links",
        "Views",
        "Telegram Clicks",
        "WhatsApp Clicks"
    ]

    synced_summary = []

    # 4. Write each day's posts into that day's individual date subsheet at the bottom
    for d in sorted(posts_by_date.keys()):
        day_posts = posts_by_date[d]
        try:
            # Subsheet name is ALWAYS the date (never AMZ_TELEGRAM or generic channel name)
            ws = find_or_create_date_worksheet(workbook, d, scheduled=scheduled)

            rows_to_insert = []
            day_total_views = 0
            day_total_tg_clicks = 0
            day_total_wa_clicks = 0

            for idx, post in enumerate(day_posts, start=1):
                post_num = idx
                time_val = format_time_12hr(post.get("time") or post.get("date_time") or post.get("date") or "")
                status_val = "Scheduled" if scheduled else str(post.get("status") or "Live")
                
                text_val = str(post.get("text") or post.get("message") or post.get("Full_Text") or "").strip()
                if not text_val:
                    text_val = "Image post (no text or links)"

                tg_links_list = post.get("telegram_links") or []
                wa_links_list = post.get("whatsapp_links") or []
                general_links = post.get("links") or post.get("Links") or []

                if not tg_links_list and general_links:
                    tg_links_list = [l for l in general_links if "amzaff" in l or "amazon" in l or "t.me" in l]
                if not wa_links_list and general_links:
                    wa_links_list = [l for l in general_links if "amzaff" in l or "wa.me" in l]

                tg_links_str = " ".join(tg_links_list) if isinstance(tg_links_list, list) else str(tg_links_list)
                wa_links_str = " ".join(wa_links_list) if isinstance(wa_links_list, list) else str(wa_links_list)

                views_val = int(post.get("views") or post.get("Views") or 0)
                tg_clicks = int(post.get("telegram_clicks") or post.get("Telegram_clicks") or post.get("Telegram-clicks") or 0)
                wa_clicks = int(post.get("whatsapp_clicks") or post.get("Whatsapp_clicks") or post.get("Whatsapp-clicks") or 0)

                day_total_views += views_val
                day_total_tg_clicks += tg_clicks
                day_total_wa_clicks += wa_clicks

                rows_to_insert.append([
                    post_num,                   # Col A: Post Number
                    time_val,                   # Col B: Time
                    status_val,                 # Col C: Status
                    text_val,                   # Col D: Message
                    tg_links_str,               # Col E: Telegram Links
                    wa_links_str,               # Col F: WhatsApp Links
                    views_val,                  # Col G: Views
                    tg_clicks,                  # Col H: Telegram Clicks
                    wa_clicks                   # Col I: WhatsApp Clicks
                ])

            # Bottom Total row matching Screenshot 1 (Total in Col F, Views in Col G, TG in Col H, WA in Col I)
            total_row = [
                "",                             # Col A
                "",                             # Col B
                "",                             # Col C
                "",                             # Col D
                "",                             # Col E
                "Total",                        # Col F: Total label
                day_total_views,                # Col G: Total Views sum
                day_total_tg_clicks,            # Col H: Total TG clicks sum
                day_total_wa_clicks             # Col I: Total WA clicks sum
            ]
            rows_to_insert.append(total_row)

            # Write headers and rows in one single lightning-fast batch update
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

            # Highlight Total row cells (F to I) in light green (#93c47d) like in screenshot
            try:
                total_row_idx = len(full_table)
                ws.format(f"F{total_row_idx}:I{total_row_idx}", {
                    "backgroundColor": {
                        "red": 0.576,
                        "green": 0.768,
                        "blue": 0.490
                    },
                    "textFormat": {
                        "bold": True,
                        "foregroundColor": {"red": 0.0, "green": 0.0, "blue": 0.0}
                    }
                })
            except Exception:
                pass

            synced_summary.append(f"{ws.title} ({len(day_posts)} posts)")

        except Exception as e_day:
            print(f"❌ Error syncing date subsheet for date {d}: {e_day}")
            synced_summary.append(f"{get_date_tab_title(d, scheduled)} (notice: {e_day})")

    return f"✅ Synced {len(posts_data)} posts into {len(synced_summary)} daily subsheets in sheet '{workbook.title}': {', '.join(synced_summary)}"

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

def scrape_public_channel_posts(
    channel_username: str,
    start_time_utc: datetime,
    end_time_utc: datetime,
    max_pages: int = 4
) -> List[Dict[str, Any]]:
    """
    Scrapes real public posts from https://t.me/s/{channel_username}
    Extracts post ID, IST timestamp, views, links, text.
    Handles date range filtering accurately.
    """
    clean_channel = channel_username.replace("@", "").strip()
    posts_data = []
    seen_ids = set()

    current_url = f"https://t.me/s/{clean_channel}"
    page = 0

    while current_url and page < max_pages:
        page += 1
        try:
            req = urllib.request.Request(
                current_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )
            html = urllib.request.urlopen(req, timeout=10).read().decode("utf-8")
        except Exception as e:
            print(f"⚠️ Error fetching t.me/s/{clean_channel}: {e}")
            break

        matches = list(re.finditer(
            r"<div class=\"tgme_widget_message text_not_supported_wrap js-widget_message\"[^>]*data-post=\"([^\"]+)\"(.*?)(?=<div class=\"tgme_widget_message text_not_supported_wrap|\Z)",
            html,
            re.DOTALL
        ))
        if not matches:
            break

        reached_earlier = False
        earliest_id = None

        for m in reversed(matches):
            post_full_id = m.group(1)
            pid_str = post_full_id.split("/")[-1]
            try:
                pid = int(pid_str)
            except Exception:
                pid = pid_str

            if pid_str in seen_ids:
                continue
            seen_ids.add(pid_str)

            body = m.group(2)
            t_m = re.search(r"<time[^>]*datetime=\"([^\"]+)\"", body)
            v_m = re.search(r"<span class=\"tgme_widget_message_views\">([^<]+)</span>", body)
            txt_m = re.search(r"<div class=\"tgme_widget_message_text[^\"]*\"[^>]*>(.*?)</div>\s*<div class=\"tgme_widget_message_footer", body, re.DOTALL)

            if not t_m:
                continue

            dt_iso = t_m.group(1)
            try:
                dt_utc = datetime.fromisoformat(dt_iso.replace("Z", "+00:00"))
            except Exception:
                continue

            if dt_utc > end_time_utc:
                continue
            if dt_utc < start_time_utc:
                reached_earlier = True
                continue

            dt_ist = dt_utc.astimezone(ist)
            time_str = dt_ist.strftime("%Y-%m-%d %H:%M:%S")
            date_str = dt_ist.strftime("%Y-%m-%d")
            ist_formatted = dt_ist.strftime("%d %b %Y, %I:%M %p IST")

            # Parse views (e.g. 1.2K -> 1200)
            views_raw = v_m.group(1).strip() if v_m else "0"
            views_val = 0
            if "k" in views_raw.lower():
                try:
                    views_val = int(float(views_raw.lower().replace("k", "")) * 1000)
                except Exception:
                    views_val = 0
            elif "m" in views_raw.lower():
                try:
                    views_val = int(float(views_raw.lower().replace("m", "")) * 1000000)
                except Exception:
                    views_val = 0
            else:
                try:
                    views_val = int(views_raw.replace(",", ""))
                except Exception:
                    views_val = 0

            raw_txt = txt_m.group(1) if txt_m else ""
            clean_txt = re.sub(r"<br\s*/?>", " ", raw_txt)
            clean_txt = re.sub(r"<[^>]+>", " ", clean_txt).strip()
            links = extract_links(clean_txt)

            snippet = clean_txt if clean_txt else "📸 Image post"

            posts_data.append({
                "id": pid,
                "post_id": pid,
                "postNumber": pid,
                "Post ID": pid,
                "time": time_str,
                "date": date_str,
                "date_time": time_str,
                "DateTime": time_str,
                "Date & Time (IST)": ist_formatted,
                "views": views_val,
                "Views": views_val,
                "text": snippet,
                "message": snippet,
                "Full_Text": snippet,
                "links": links,
                "Links": links,
                "channel": clean_channel,
                "Channel": clean_channel,
                "category": "",
                "status": "Live",
                "Status": "Live",
                "media_type": "image" if ("tgme_widget_message_photo" in body or "tgme_widget_message_video" in body) else "text",
                "image": "",
                "telegram_clicks": 0,
                "Telegram_clicks": 0,
                "Telegram-clicks": 0,
                "whatsapp_clicks": 0,
                "Whatsapp_clicks": 0,
                "Whatsapp-clicks": 0,
            })

            if earliest_id is None or (isinstance(pid, int) and pid < earliest_id):
                if isinstance(pid, int):
                    earliest_id = pid

        if reached_earlier or not earliest_id:
            break

        prev_link = re.search(r"<link\s+rel=\"prev\"\s+href=\"([^\"]+)\"", html)
        if prev_link:
            current_url = f"https://t.me{prev_link.group(1)}"
        else:
            current_url = f"https://t.me/s/{clean_channel}?before={earliest_id}"

    posts_data.sort(key=lambda p: str(p.get("time", "")))
    return posts_data
