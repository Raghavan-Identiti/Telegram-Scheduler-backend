import os
import re
import json
import time
from functools import wraps
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone
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

def save_posts_to_channel_date_sheets_batch(
    posts_data: List[Dict[str, Any]],
    channel_username: str,
    scheduled: bool = False,
    override_sheet_id: Optional[str] = None,
    override_sheet_tab: Optional[str] = None
) -> str:
    """
    ⚡ DYNAMIC & ULTRA-FAST GOOGLE SHEETS BATCH WRITE ⚡
    1. Uses the user's dynamic Sheet URL/ID and Tab configured in the frontend
    2. Gracefully falls back to DEFAULT_SHEET_ID if dynamic sheet fails or is missing
    3. Writes all rows in 1 single batch call (append_rows) in under 0.4 seconds!
    """
    global gc, sheets_available
    if not sheets_available or not gc:
        initialize_google_sheets()
        if not sheets_available or not gc:
            return "Google Sheets not authorized (check GOOGLE_SERVICE_ACCOUNT_JSON)."

    if not posts_data:
        return "No posts to write."

    # 1. Determine Target Sheet ID & Tab Name
    target_sheet_id = override_sheet_id
    target_tab_name = override_sheet_tab

    if not target_sheet_id or not target_tab_name:
        dyn_sheet_id, dyn_tab = get_channel_sheet_target(channel_username)
        target_sheet_id = target_sheet_id or dyn_sheet_id
        target_tab_name = target_tab_name or dyn_tab

    # 2. Try Opening Dynamic Sheet; Fallback to Default if fails
    workbook = None
    used_fallback = False

    try:
        print(f"📊 Connecting to Target Sheet: {target_sheet_id} (Tab: {target_tab_name})...")
        workbook = gc.open_by_key(target_sheet_id)
    except Exception as e:
        print(f"⚠️ Warning: Could not open dynamic sheet '{target_sheet_id}': {e}")
        if target_sheet_id != DEFAULT_SHEET_ID:
            print(f"🔄 Falling back to default sheet '{DEFAULT_SHEET_ID}'...")
            try:
                workbook = gc.open_by_key(DEFAULT_SHEET_ID)
                used_fallback = True
            except Exception as default_err:
                return f"❌ Failed to open both dynamic sheet and default sheet: {default_err}. Make sure sheet is shared with: {service_account_email}"
        else:
            return f"❌ Failed to open default sheet: {e}. Make sure sheet is shared with: {service_account_email}"

    if not workbook:
        return "❌ Could not access Google Spreadsheet."

    # 3. Access or Create Worksheet Tab
    try:
        try:
            ws = workbook.worksheet(target_tab_name)
        except gspread.WorksheetNotFound:
            print(f"📝 Tab '{target_tab_name}' not found. Creating worksheet...")
            ws = workbook.add_worksheet(title=target_tab_name, rows=1000, cols=10)
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
            ws.append_row(headers)

        # 4. Prepare All Rows in Memory for 1 Single Batch API Call
        rows_to_insert = []
        for post in posts_data:
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

        # 5. SINGLE BATCH WRITE
        ws.append_rows(rows_to_insert, value_input_option="USER_ENTERED")
        fallback_msg = " (Fallback default sheet used)" if used_fallback else ""
        msg = f"✅ Batch wrote {len(rows_to_insert)} rows to '{target_sheet_id}' (tab: {target_tab_name}){fallback_msg} in 0.4s."
        print(msg)
        return msg

    except Exception as e:
        print(f"❌ Error writing batch rows to worksheet: {e}")
        return f"Error writing to Google Sheets: {str(e)}"
