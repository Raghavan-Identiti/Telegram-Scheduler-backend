import os
import re
import json
import time
from functools import wraps
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, date, timezone
from dateutil import parser
import pytz
import gspread
from google.oauth2 import service_account

# Default channels and fallback sheet names
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

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# Default fallback Sheet ID (original fallback)
DEFAULT_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "1seb2pGu1XekQmNcHC-6Ma_y9tGRyhTo33PrR8sA-EBc")
api_id = os.getenv("TELEGRAM_API_ID", "2040")
api_hash = os.getenv("TELEGRAM_API_HASH", "")
session_string = os.getenv("TELEGRAM_SESSION_STRING", "")

gc: Optional[gspread.Client] = None
sheets_available = False
service_account_email = ""

def get_settings_file_path() -> str:
    """Find settings.json reliably across local, Docker, and Render environments"""
    candidates = [
        os.path.join(os.getcwd(), "settings.json"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "settings.json"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json"),
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
            print(f"⚠️ Error reading settings.json from {filepath}: {e}")
    return {"auto_fetch_enabled": True, "channel_sheets": {}}

def save_settings(settings: Dict[str, Any]) -> None:
    filepath = get_settings_file_path()
    try:
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
        print(f"💾 Settings saved successfully to {filepath}")
    except Exception as e:
        print(f"⚠️ Error saving settings.json to {filepath}: {e}")

def extract_sheet_id_from_url(url_or_id: str) -> str:
    """Extract clean Google Sheet ID from any standard URL format or direct ID"""
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
            print("⚠️ GOOGLE_SERVICE_ACCOUNT_JSON environment variable not set")
            sheets_available = False
            return False

        creds_dict = json.loads(google_creds_json)
        service_account_email = creds_dict.get("client_email", "")
        creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        gc = gspread.authorize(creds)
        sheets_available = True
        print(f"✅ Google Sheets Client authorized for service account: {service_account_email}")
        return True
    except Exception as e:
        print(f"❌ Failed to authorize Google Sheets API: {e}")
        sheets_available = False
        return False

def get_channel_sheet_target(channel_username: str) -> Tuple[str, str]:
    """
    Look up dynamic Google Sheet configuration for a channel.
    Returns (sheet_id, sheet_tab_name).
    If no dynamic config is present, returns (DEFAULT_SHEET_ID, default_tab_name).
    """
    clean_username = channel_username.replace("@", "").strip().lower()
    settings = load_settings()
    channel_sheets = settings.get("channel_sheets", {})

    # Match by key or username
    matched_config = None
    for k, v in channel_sheets.items():
        if k.replace("@", "").strip().lower() == clean_username:
            matched_config = v
            break

    # Determine default tab name
    default_tab = clean_username
    for cid, data in CHANNELS.items():
        if data["username"].lower() == clean_username:
            default_tab = data["sheet_name"]
            break

    if matched_config:
        sheet_url = matched_config.get("sheet_url") or matched_config.get("sheetUrl") or ""
        sheet_id = (
            matched_config.get("sheet_id") or
            matched_config.get("sheetId") or
            extract_sheet_id_from_url(sheet_url)
        )
        tab_name = (
            matched_config.get("sheet_tab") or
            matched_config.get("sheetTab") or
            matched_config.get("tab_name") or
            matched_config.get("targetTab") or
            default_tab
        )

        if sheet_id and sheet_id.strip():
            return sheet_id.strip(), tab_name.strip()

    return DEFAULT_SHEET_ID, default_tab

def extract_links(text: str) -> List[str]:
    """Fast compiled regex link extraction"""
    if not text:
        return []
    url_pattern = re.compile(r"[*_()<>]*\b(https?://\S+|amzaff\.in/\S+)\b[*_()<>]*", re.IGNORECASE)
    links = url_pattern.findall(text)
    return [re.sub(r"^[*_()<>]+|[*_()<>.,!?]+$", "", link).strip() for link in links if link.strip()]

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
    day = d.day
    suffix = get_ordinal_suffix(day)
    m_abbr = d.strftime("%b")
    m_full = d.strftime("%B")
    year = d.year
    return [
        f"{day}{suffix} {m_abbr}",
        f"{day} {m_abbr}",
        f"{day}{suffix}_{m_abbr}",
        f"{day}_{m_abbr}",
        f"{day}{suffix} {m_abbr} {year}",
        f"{day} {m_abbr} {year}",
        f"{day}{suffix} {m_full}",
        f"{day} {m_full}",
        d.strftime("%Y-%m-%d"),
        d.strftime("%d-%m-%Y"),
        d.strftime("%d-%b-%Y"),
        d.strftime("%d-%b"),
        d.strftime("%d/%m/%Y"),
    ]

def find_or_create_date_worksheet(workbook: gspread.Spreadsheet, d: date) -> gspread.Worksheet:
    standard_title = get_date_tab_title(d)
    candidates = [c.lower().replace(" ", "").replace("_", "").replace("-", "") for c in get_date_candidates(d)]
    
    existing_sheets = workbook.worksheets()
    for ws in existing_sheets:
        norm_title = ws.title.lower().replace(" ", "").replace("_", "").replace("-", "")
        if norm_title in candidates:
            return ws

    if len(existing_sheets) == 1 and existing_sheets[0].title.lower() in ["sheet1", "sheet 1"]:
        try:
            if not existing_sheets[0].get_all_values():
                existing_sheets[0].update_title(standard_title)
                return existing_sheets[0]
        except Exception:
            pass

    ws = workbook.add_worksheet(title=standard_title, rows=1000, cols=10)
    return ws

def extract_post_ist_date(post: Dict[str, Any]) -> date:
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

            ist = pytz.timezone("Asia/Kolkata")
            if dt.tzinfo is None:
                dt = ist.localize(dt)
            else:
                dt = dt.astimezone(ist)
            return dt.date()

    return datetime.now(pytz.timezone("Asia/Kolkata")).date()

def save_posts_to_channel_date_sheets_batch(
    posts_data: List[Dict[str, Any]],
    channel_username: str,
    scheduled: bool = False,
    override_sheet_id: Optional[str] = None,
    override_sheet_tab: Optional[str] = None
) -> str:
    """
    ⚡ DYNAMIC & ULTRA-FAST GOOGLE SHEETS BATCH WRITE WITH DAILY SUBSHEETS ⚡
    1. Channel has one Google Sheet link.
    2. Inside that sheet, each day has its individual subsheet at the bottom.
    3. Posts in a date range are grouped by date and cleanly synced.
    """
    global gc, sheets_available
    if not sheets_available or not gc:
        initialize_google_sheets()
        if not sheets_available or not gc:
            return "Google Sheets not authorized (check GOOGLE_SERVICE_ACCOUNT_JSON)."

    if not posts_data:
        return "No posts to write."

    target_sheet_id = override_sheet_id
    if not target_sheet_id:
        dyn_sheet_id, _ = get_channel_sheet_target(channel_username)
        target_sheet_id = dyn_sheet_id or DEFAULT_SHEET_ID

    target_sheet_id = str(target_sheet_id or DEFAULT_SHEET_ID).strip()
    workbook = None
    used_fallback = False

    try:
        print(f"📊 Connecting to Target Sheet: {target_sheet_id}...")
        workbook = gc.open_by_key(target_sheet_id)
    except Exception as e:
        print(f"⚠️ Warning: Could not open dynamic sheet '{target_sheet_id}': {e}")
        try:
            workbook = gc.open_by_key(DEFAULT_SHEET_ID)
            used_fallback = True
            target_sheet_id = DEFAULT_SHEET_ID
        except Exception as default_err:
            return f"❌ Failed to open sheet: {default_err}. Make sure sheet is shared with: {service_account_email}"

    if not workbook:
        return "❌ Could not access Google Spreadsheet."

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

    for d in sorted(posts_by_date.keys()):
        day_posts = posts_by_date[d]
        try:
            ws = None
            known_channel_names = [
                channel_username.lower().replace("@", "").strip(),
                "amazon_india_associates", "fashion_beauty", "home_kitchen", "consumables", "posts"
            ]
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

            rows_to_insert = []
            for post in day_posts:
                time_val = str(post.get("time", ""))
                views_val = post.get("views", 0)
                tg_clicks = post.get("Telegram-clicks", 0)
                wa_clicks = post.get("Whatsapp-clicks", 0)
                links_val = ", ".join(post.get("links", []))
                text_val = str(post.get("text", "")).replace("\n", " ").strip()[:500]
                status_val = "Scheduled" if scheduled else post.get("status", "Live")
                post_id = post.get("id", "")

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

            full_table = [headers] + rows_to_insert
            try:
                ws.clear()
                try:
                    ws.update("A1", full_table, value_input_option="USER_ENTERED")
                except TypeError:
                    ws.update(full_table, value_input_option="USER_ENTERED")
            except Exception as e_up:
                try:
                    ws.append_rows(rows_to_insert, value_input_option="USER_ENTERED")
                except Exception:
                    pass

            synced_summary.append(f"{ws.title} ({len(rows_to_insert)} posts)")

        except Exception as e_day:
            synced_summary.append(f"{get_date_tab_title(d)} (notice: {e_day})")

    fallback_msg = " (Fallback default sheet used)" if used_fallback else ""
    return f"✅ Synced {len(posts_data)} posts into {len(synced_summary)} daily subsheets in Google Sheet: {', '.join(synced_summary)}{fallback_msg}"
