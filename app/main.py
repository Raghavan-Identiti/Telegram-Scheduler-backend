# app/main.py
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, Form, Request, Query, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os, re, json, time, asyncio
from typing import List, Dict, Any, Optional
from datetime import date, datetime, timezone, timedelta
import pandas as pd
import pytz
from pydantic import BaseModel
import openpyxl
from telethon import TelegramClient
from telethon.tl.types import MessageMediaPhoto
from telethon.sessions import StringSession
from telethon.tl.functions.messages import GetScheduledHistoryRequest
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.types import InputPeerChannel
from dateutil import parser

from app.routers.logs_api import router as logs_router
from app.routers.recurrence_scheduler import router as recurrence_router
from app.routers.whatsapp_routes import router as whatsapp_router
from app.services.whatsapp_worker import start_worker, stop_worker
from app.core.scheduler import scheduler
from apscheduler.triggers.cron import CronTrigger

from app.services.telegram_utils import (
    CHANNELS,
    extract_all_posts_from_texts,
    send_telegram_message,
    get_blocked_times_from_sheet,
    initialize_google_sheets,
    sheets_available,
    save_posts_to_channel_date_sheets,
    extract_links,
    extract_sheet_id_from_url,
    get_channel_sheet_target,
    load_settings,
    save_settings,
    DEFAULT_SHEET_ID,
    gc,
    service_account_email
)
from app.services.clicksFind import get_batch_clicks_data, get_clicks

ist = pytz.timezone("Asia/Kolkata")
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs("logs", exist_ok=True)

app = FastAPI(title="TeleQueue API")

# Comprehensive CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global exception handler to preserve CORS headers on error
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    print(f"🔥 Error on {request.url.path}: {exc}")
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"status": "error", "error": str(exc), "path": str(request.url.path)},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )

if os.path.exists("uploads"):
    app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
if os.path.exists("logs"):
    app.mount("/logs", StaticFiles(directory="logs"), name="logs")

app.include_router(logs_router, prefix="/api")
app.include_router(recurrence_router, prefix="/api")
app.include_router(whatsapp_router)

def get_telethon_creds():
    raw_id = os.getenv("TELEGRAM_API_ID", "2040")
    try:
        api_id_int = int(raw_id) if str(raw_id).strip() else 2040
    except Exception:
        api_id_int = 2040
    api_hash_val = os.getenv("TELEGRAM_API_HASH", "").strip()
    session_str = os.getenv("TELEGRAM_SESSION_STRING", "").strip()
    return api_id_int, api_hash_val, session_str

def parse_dt_flexible(dt_val: Any) -> datetime:
    if isinstance(dt_val, datetime):
        return dt_val
    if isinstance(dt_val, str):
        try:
            return parser.isoparse(dt_val)
        except Exception:
            return parser.parse(dt_val)
    raise ValueError(f"Cannot parse datetime from {dt_val}")

def round_to_nearest_5(dt: datetime) -> datetime:
    minute = dt.minute
    remainder = minute % 5
    if remainder < 3:
        minute -= remainder
    else:
        minute += (5 - remainder)
    if minute == 60:
        dt = dt.replace(minute=0) + timedelta(hours=1)
    else:
        dt = dt.replace(minute=minute)
    return dt.replace(second=0, microsecond=0)

def to_utc_naive(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = ist.localize(dt)
    return dt.astimezone(timezone.utc).replace(tzinfo=None)

@app.get("/")
async def root():
    return {"status": "success", "message": "TeleQueue API is running!"}

# =========================================================================
# 1. Dynamic Google Sheets Config Endpoints
# =========================================================================

@app.get("/api/sheets/config")
async def get_sheets_config():
    """Retrieve dynamic Google Sheet configuration per channel"""
    settings = load_settings()
    return {
        "status": "success",
        "default_sheet_id": DEFAULT_SHEET_ID,
        "service_account_email": service_account_email,
        "channel_sheets": settings.get("channel_sheets", {})
    }

@app.post("/api/sheets/update-config")
async def update_sheets_config(payload: Dict[str, Any]):
    """Save updated Google Sheet URLs and tab names per channel dynamically"""
    settings = load_settings()
    sheet_map = settings.get("channel_sheets", {})

    channels_data = payload.get("channels")
    if channels_data is None and isinstance(payload.get("channel_sheets"), dict):
        sheet_map.update(payload["channel_sheets"])
    elif isinstance(channels_data, list):
        for item in channels_data:
            cid = item.get("channelId") or item.get("channel_id") or item.get("id") or item.get("channel")
            surl = item.get("sheetUrl") or item.get("sheet_url") or item.get("url") or item.get("link") or ""
            sid = item.get("sheetId") or item.get("sheet_id") or extract_sheet_id_from_url(surl)
            stab = item.get("sheetTab") or item.get("sheet_tab") or item.get("tab_name") or item.get("targetTab") or ""

            if cid:
                clean_cid = cid.replace("@", "").strip()
                sheet_map[clean_cid] = {
                    "sheet_id": sid,
                    "sheet_url": surl,
                    "sheet_tab": stab
                }

    settings["channel_sheets"] = sheet_map
    save_settings(settings)
    print(f"✅ Dynamic Google Sheets config updated in settings.json: {sheet_map}")

    return {
        "status": "success",
        "message": "Google Sheet configuration saved successfully",
        "channel_sheets": sheet_map
    }

@app.post("/api/sheets/connect-or-check")
async def connect_or_check(request: Request):
    """Check or reconnect Google Sheets service account"""
    global sheets_available
    try:
        body = await request.json()
    except Exception:
        body = {}
    reconnect = body.get("reconnect", False)

    if reconnect or not sheets_available:
        success = initialize_google_sheets()
        return {
            "connected": success,
            "message": "✅ Connected to Google Sheets" if success else "❌ Failed to connect Google Sheets. Check GOOGLE_SERVICE_ACCOUNT_JSON."
        }
    else:
        return {
            "connected": sheets_available,
            "message": "✅ Google Sheets connected" if sheets_available else "❌ Google Sheets not connected"
        }

@app.post("/api/sheets/test-connection")
async def test_sheet_connection(request: Request):
    """Tests if a specific sheet link can be opened by the service account"""
    global gc, sheets_available
    if not sheets_available or not gc:
        initialize_google_sheets()

    body = await request.json()
    raw_target = body.get("sheet_id") or body.get("sheet_url") or body.get("sheetUrl")
    if not raw_target:
        return JSONResponse(status_code=400, content={"status": "error", "message": "No sheet URL or ID provided."})

    target_id = extract_sheet_id_from_url(raw_target)
    try:
        sh = gc.open_by_key(target_id)
        tabs = [ws.title for ws in sh.worksheets()]
        return {
            "status": "success",
            "sheet_title": sh.title,
            "sheet_id": target_id,
            "worksheets": tabs,
            "message": f"✅ Connected successfully to '{sh.title}'. Found {len(tabs)} tabs."
        }
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "sheet_id": target_id,
                "message": f"❌ Could not access sheet: {str(e)}",
                "help": f"Please ensure spreadsheet is shared with Editor permission with: {service_account_email}"
            }
        )

# =========================================================================
# 2. Settings & Daily Auto-Fetch
# =========================================================================

class AutoFetchSettings(BaseModel):
    enabled: bool

@app.get("/api/settings/auto-fetch")
async def get_auto_fetch():
    settings = load_settings()
    return {"enabled": settings.get("auto_fetch_enabled", True)}

@app.post("/api/settings/auto-fetch")
async def set_auto_fetch(req: AutoFetchSettings):
    settings = load_settings()
    settings["auto_fetch_enabled"] = req.enabled
    save_settings(settings)
    update_scheduler_job()
    return {"status": "success", "enabled": req.enabled}

def update_scheduler_job():
    settings = load_settings()
    job_id = "daily_auto_fetch"
    if settings.get("auto_fetch_enabled", False):
        if not scheduler.get_job(job_id):
            scheduler.add_job(
                auto_fetch_yesterday_posts,
                trigger=CronTrigger(hour=6, minute=0, timezone=ist),
                id=job_id,
                replace_existing=True
            )
            print("✅ Scheduled daily auto-fetch job at 6:00 AM IST")
    else:
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
            print("🛑 Removed daily auto-fetch job")

# =========================================================================
# 3. Channels & Post Summaries
# =========================================================================

@app.get("/api/channels")
async def get_available_channels():
    channels_list = []
    for channel_id, data in CHANNELS.items():
        channels_list.append({
            "id": channel_id,
            "username": data["username"],
            "name": data.get("name", data["username"].replace("@", "").title())
        })
    return {"status": "success", "channels": channels_list, "total": len(channels_list)}

@app.get("/api/posts-summary")
async def get_posts_summary(
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    channels: str = Query(None, description="Comma-separated channel IDs")
):
    results = []
    api_id_int, api_hash_val, session_str = get_telethon_creds()
    if not session_str:
        return {"status": "success", "date": date, "channels": [], "totals": {"live_posts": 0, "scheduled_posts": 0, "total_posts": 0}}

    try:
        target_date = datetime.strptime(date, "%Y-%m-%d")
        start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
        end_of_day = target_date.replace(hour=23, minute=59, second=59, microsecond=999999, tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    target_channels = CHANNELS
    if channels:
        channel_ids = [id.strip() for id in channels.split(",")]
        target_channels = {k: v for k, v in CHANNELS.items() if k in channel_ids}

    try:
        async with TelegramClient(StringSession(session_str), api_id_int, api_hash_val) as client:
            for channel_id, data in target_channels.items():
                username = data["username"]
                live_count = 0
                scheduled_count = 0
                try:
                    entity = await client.get_entity(username)
                    async for message in client.iter_messages(entity, offset_date=end_of_day):
                        if not message.date:
                            continue
                        msg_date = message.date if message.date.tzinfo == timezone.utc else message.date.astimezone(timezone.utc)
                        if msg_date < start_of_day:
                            break
                        if start_of_day <= msg_date <= end_of_day:
                            live_count += 1

                    try:
                        scheduled_result = await client(GetScheduledHistoryRequest(peer=entity, hash=0))
                        for msg in getattr(scheduled_result, 'messages', []):
                            if not msg.date:
                                continue
                            sched_date = msg.date if msg.date.tzinfo == timezone.utc else msg.date.astimezone(timezone.utc)
                            if start_of_day <= sched_date <= end_of_day:
                                scheduled_count += 1
                    except Exception:
                        pass

                    results.append({
                        "channel_id": channel_id,
                        "channel_username": username,
                        "live_posts": live_count,
                        "scheduled_posts": scheduled_count,
                    })
                except Exception as e:
                    results.append({
                        "channel_id": channel_id,
                        "channel_username": username,
                        "live_posts": 0,
                        "scheduled_posts": 0,
                        "error": str(e)
                    })
    except Exception as e:
        print(f"Error in get_posts_summary: {e}")

    total_live = sum(ch.get("live_posts", 0) for ch in results)
    total_sched = sum(ch.get("scheduled_posts", 0) for ch in results)
    return {
        "status": "success",
        "date": date,
        "channels": results,
        "total_channels": len(results),
        "totals": {
            "live_posts": total_live,
            "scheduled_posts": total_sched,
            "total_posts": total_live + total_sched
        }
    }

@app.get("/api/posts-range")
async def get_posts_range(
    start_date: str = Query(..., description="Start date in YYYY-MM-DD format"),
    end_date: str = Query(..., description="End date in YYYY-MM-DD format"),
    channels: str = Query(None, description="Comma-separated channel IDs")
):
    results = []
    api_id_int, api_hash_val, session_str = get_telethon_creds()
    if not session_str:
        return {"status": "success", "channels": [], "totals": {"live_posts": 0, "scheduled_posts": 0, "total_posts": 0}}

    start = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)

    target_channels = CHANNELS
    if channels:
        channel_ids = [id.strip() for id in channels.split(",")]
        target_channels = {k: v for k, v in CHANNELS.items() if k in channel_ids}

    try:
        async with TelegramClient(StringSession(session_str), api_id_int, api_hash_val) as client:
            for channel_id, data in target_channels.items():
                username = data["username"]
                live_count = 0
                scheduled_count = 0
                try:
                    entity = await client.get_entity(username)
                    async for message in client.iter_messages(entity, offset_date=end):
                        if not message.date:
                            continue
                        msg_date = message.date if message.date.tzinfo == timezone.utc else message.date.astimezone(timezone.utc)
                        if msg_date < start:
                            break
                        if start <= msg_date <= end:
                            live_count += 1

                    try:
                        scheduled_result = await client(GetScheduledHistoryRequest(peer=entity, hash=0))
                        for msg in getattr(scheduled_result, 'messages', []):
                            if not msg.date:
                                continue
                            sched_date = msg.date if msg.date.tzinfo == timezone.utc else msg.date.astimezone(timezone.utc)
                            if start <= sched_date <= end:
                                scheduled_count += 1
                    except Exception:
                        pass

                    results.append({
                        "channel_id": channel_id,
                        "channel_username": username,
                        "live_posts": live_count,
                        "scheduled_posts": scheduled_count,
                    })
                except Exception as e:
                    results.append({"channel_id": channel_id, "channel_username": username, "live_posts": 0, "scheduled_posts": 0, "error": str(e)})
    except Exception as e:
        print(f"Error in get_posts_range: {e}")

    total_live = sum(ch.get("live_posts", 0) for ch in results)
    total_sched = sum(ch.get("scheduled_posts", 0) for ch in results)
    return {
        "status": "success",
        "start_date": start_date,
        "end_date": end_date,
        "channels": results,
        "totals": {"live_posts": total_live, "scheduled_posts": total_sched, "total_posts": total_live + total_sched}
    }

# =========================================================================
# 4. Ultra-Fast Content Reader (POST /api/read-posts)
# =========================================================================

class ReadPostsRequest(BaseModel):
    channel: str
    start_time: Any
    end_time: Any
    sheet_url: Optional[str] = None
    sheet_tab: Optional[str] = None

@app.post("/api/read-posts")
async def read_posts(req: ReadPostsRequest):
    """
    ⚡ ULTRA-FAST CONTENT READER WITH DYNAMIC SHEET SYNC ⚡
    - Scrapes posts with early loop break (newest -> oldest)
    - Parallel batch fetches Quic.ly click tracking (<2s)
    - Writes to the channel's dynamic Google Sheet with automatic fallback
    """
    api_id_int, api_hash_val, session_str = get_telethon_creds()
    if not session_str:
        return JSONResponse(status_code=400, content={"error": "TELEGRAM_SESSION_STRING environment variable is not configured."})

    try:
        start_dt = parse_dt_flexible(req.start_time)
        end_dt = parse_dt_flexible(req.end_time)
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": f"Invalid start_time or end_time: {e}"})

    start_time_utc = start_dt.astimezone(timezone.utc)
    end_time_utc = end_dt.astimezone(timezone.utc)
    post_date_str = start_dt.astimezone(ist).strftime("%Y-%m-%d")

    posts_data = []
    all_links = set()

    try:
        async with TelegramClient(StringSession(session_str), api_id_int, api_hash_val) as client:
            async for msg in client.iter_messages(req.channel, offset_date=end_time_utc):
                if msg.date is None:
                    continue
                msg_date_utc = msg.date if msg.date.tzinfo == timezone.utc else msg.date.astimezone(timezone.utc)

                # 🚀 CRITICAL FIX: Early break!
                if msg_date_utc < start_time_utc:
                    break
                if msg_date_utc > end_time_utc:
                    continue

                msg_date_ist = msg_date_utc.astimezone(ist)
                text_content = msg.text or ""
                links = extract_links(text_content)
                for l in links:
                    all_links.add(l)

                posts_data.append({
                    "id": msg.id,
                    "time": msg_date_ist.strftime("%Y-%m-%d %H:%M:%S"),
                    "views": getattr(msg, "views", 0) or 0,
                    "text": text_content if text_content.strip() else ("📸 Image post" if msg.media else ""),
                    "links": links,
                    "channel": req.channel,
                    "category": "",
                    "status": "Live",
                    "media_type": "image" if msg.media else "text"
                })

        # Fast parallel click fetching
        clicks_map = await get_batch_clicks_data(list(all_links), post_date_str)
        for p in posts_data:
            tg = 0
            wa = 0
            for l in p["links"]:
                st = clicks_map.get(l, {})
                tg += st.get("telegram_clicks", 0)
                wa += st.get("whatsapp_clicks", 0)
            p["Telegram-clicks"] = tg
            p["Whatsapp-clicks"] = wa

        # 🚀 Dynamic Sheet write with fallback
        override_id = extract_sheet_id_from_url(req.sheet_url) if req.sheet_url else None
        save_msg = save_posts_to_channel_date_sheets(
            posts_data=posts_data,
            channel_username=req.channel,
            scheduled=False,
            override_sheet_id=override_id,
            override_sheet_tab=req.sheet_tab
        )

        target_sheet_id, target_tab = get_channel_sheet_target(req.channel)
        if override_id:
            target_sheet_id = override_id
        if req.sheet_tab:
            target_tab = req.sheet_tab

        return {
            "status": "success",
            "count": len(posts_data),
            "message": save_msg,
            "target_sheet_id": target_sheet_id,
            "target_tab": target_tab,
            "posts": posts_data,
            "channel": req.channel
        }

    except Exception as e:
        print(f"❌ Error in read_posts: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

@app.post("/api/scheduled-posts")
async def read_scheduled_messages(req: ReadPostsRequest):
    api_id_int, api_hash_val, session_str = get_telethon_creds()
    if not session_str:
        return JSONResponse(status_code=400, content={"error": "TELEGRAM_SESSION_STRING not set"})

    try:
        start_dt = parse_dt_flexible(req.start_time)
        post_date_str = start_dt.astimezone(ist).strftime("%Y-%m-%d")
    except Exception:
        post_date_str = datetime.now(ist).strftime("%Y-%m-%d")

    scheduled_posts = []
    all_links = set()

    try:
        async with TelegramClient(StringSession(session_str), api_id_int, api_hash_val) as client:
            result = await client(GetScheduledHistoryRequest(peer=req.channel, hash=0))
            for msg in getattr(result, "messages", []):
                msg_date_ist = msg.date.astimezone(ist) if msg.date else datetime.now(ist)
                text_content = msg.message or ""
                links = extract_links(text_content)
                for l in links:
                    all_links.add(l)

                scheduled_posts.append({
                    "id": msg.id,
                    "time": msg_date_ist.strftime("%Y-%m-%d %H:%M:%S"),
                    "views": 0,
                    "text": text_content if text_content.strip() else "📸 Image post",
                    "links": links,
                    "channel": req.channel,
                    "category": "",
                    "status": "Scheduled"
                })

        clicks_map = await get_batch_clicks_data(list(all_links), post_date_str)
        for p in scheduled_posts:
            tg = 0
            wa = 0
            for l in p["links"]:
                st = clicks_map.get(l, {})
                tg += st.get("telegram_clicks", 0)
                wa += st.get("whatsapp_clicks", 0)
            p["Telegram-clicks"] = tg
            p["Whatsapp-clicks"] = wa

        override_id = extract_sheet_id_from_url(req.sheet_url) if req.sheet_url else None
        save_msg = save_posts_to_channel_date_sheets(
            posts_data=scheduled_posts,
            channel_username=req.channel,
            scheduled=True,
            override_sheet_id=override_id,
            override_sheet_tab=req.sheet_tab
        )

        return {
            "status": "success",
            "count": len(scheduled_posts),
            "message": save_msg,
            "scheduled_posts": scheduled_posts
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

# =========================================================================
# 5. Auto-Scheduler & Calendar Slots
# =========================================================================

@app.get("/api/calendar-slots")
def get_calendar_slots(date: str = Query(..., description="Format: YYYY-MM-DD")):
    log_file = os.path.join("logs", "post_logs.xlsx")
    if not os.path.exists(log_file):
        return []

    try:
        df = pd.read_excel(log_file)
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce').dt.date
        df['Time'] = pd.to_datetime(df['Time'], format='%H:%M:%S', errors='coerce').dt.time

        selected_date = datetime.strptime(date, "%Y-%m-%d").date()
        day_posts = df[df['Date'] == selected_date]

        slots = []
        for _, row in day_posts.iterrows():
            if pd.isna(row['Time']):
                continue
            full_datetime = datetime.combine(row['Date'], row['Time'])
            slots.append({
                "time": full_datetime.isoformat(),
                "status": "booked",
                "post": row.get('Post Number', '')
            })
        return slots
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/auto-schedule")
async def auto_schedule(
    request: Request,
    background_tasks: BackgroundTasks,
    text_files: List[UploadFile] = File([]),
    image_files: List[UploadFile] = File([]),
    start_time: str = Form(...),
    end_time: str = Form(...),
    channels: str = Form(...),
    send_image_only: bool = Form(default=False),
    interval_minutes: int = Form(default=0),
    scheduling_mode: str = Form(default="auto")
):
    try:
        selected_channels = json.loads(channels) if channels else []
        if not selected_channels:
            return JSONResponse(status_code=400, content={"error": "Please select at least one channel"})

        for f in os.listdir(UPLOAD_DIR):
            try:
                os.remove(os.path.join(UPLOAD_DIR, f))
            except Exception:
                pass

        image_map = {}
        text_contents = []

        for file in text_files:
            filepath = os.path.join(UPLOAD_DIR, file.filename)
            with open(filepath, "wb") as f:
                f.write(await file.read())
            with open(filepath, 'r', encoding='utf-8') as f:
                text_contents.append(f.read())

        text_posts = extract_all_posts_from_texts(text_contents)

        for file in image_files:
            fname = file.filename.lower()
            filepath = os.path.join(UPLOAD_DIR, file.filename)
            with open(filepath, "wb") as f:
                f.write(await file.read())
            match = re.search(r'(?:\*{0,2})\s*post\s*[-_\s]*(\d+)', fname, re.IGNORECASE)
            if match:
                post_num = int(match.group(1))
                image_map[post_num] = filepath

        all_post_nums = sorted(set(text_posts.keys()) | set(image_map.keys()))
        image_only_posts = [num for num in image_map if num not in text_posts]

        if image_only_posts and not send_image_only:
            return JSONResponse({
                "status": "confirm_image_only",
                "image_only_posts": image_only_posts
            })

        if not all_post_nums:
            return JSONResponse(status_code=400, content={"error": "No valid posts detected."})

        start_dt = round_to_nearest_5(ist.localize(datetime.fromisoformat(start_time.replace("Z", ""))))
        end_dt = round_to_nearest_5(ist.localize(parser.isoparse(end_time)))

        sheet_blocked_times_naive = get_blocked_times_from_sheet(selected_channels)
        blocked_times_ist = set()
        for naive_dt in sheet_blocked_times_naive:
            ist_dt = ist.localize(naive_dt) if naive_dt.tzinfo is None else naive_dt.astimezone(ist)
            blocked_times_ist.add(round_to_nearest_5(ist_dt))

        ui_grid = []
        g = start_dt
        while g <= end_dt:
            ui_grid.append(round_to_nearest_5(g))
            g += timedelta(minutes=5)

        available_slots = [slot for slot in ui_grid if slot not in blocked_times_ist]
        post_times = {}
        assigned_slots = set()

        form_data = await request.form()
        times = form_data.getlist('times[]')
        if times:
            for entry in times:
                if '|' in entry:
                    post_str, time_str = entry.split('|', 1)
                    try:
                        post_num = int(post_str.strip())
                        parts = time_str.strip().split(':')
                        h, m = int(parts[0]), int(parts[1])
                        dt_time = start_dt.replace(hour=h, minute=m, second=0, microsecond=0)
                        if dt_time in blocked_times_ist:
                            post_times[post_num] = None
                            continue
                        post_times[post_num] = dt_time
                        assigned_slots.add(dt_time)
                    except Exception:
                        continue

        remaining_slots = [s for s in available_slots if s not in assigned_slots]
        remaining_slots.sort()
        unassigned_posts = [num for num in all_post_nums if num not in post_times]

        if interval_minutes > 0:
            current = start_dt
            idx = 0
            for post_num in unassigned_posts:
                while idx < len(remaining_slots):
                    if remaining_slots[idx] >= current:
                        slot = remaining_slots.pop(idx)
                        post_times[post_num] = slot
                        assigned_slots.add(slot)
                        break
                    idx += 1
                else:
                    post_times[post_num] = None
                current += timedelta(minutes=interval_minutes)
        else:
            if len(unassigned_posts) <= len(remaining_slots):
                step = max(1, len(remaining_slots) // max(1, len(unassigned_posts)))
                for i, post_num in enumerate(unassigned_posts):
                    s_idx = min(i * step, len(remaining_slots) - 1)
                    slot = remaining_slots[s_idx]
                    post_times[post_num] = slot
                    assigned_slots.add(slot)
            else:
                for i, post_num in enumerate(unassigned_posts):
                    if i < len(remaining_slots):
                        post_times[post_num] = remaining_slots[i]
                        assigned_slots.add(remaining_slots[i])
                    else:
                        post_times[post_num] = None

        all_results = []
        total_scheduled = 0
        total_failed = 0
        total_skipped = 0

        for channel_id in selected_channels:
            if channel_id not in CHANNELS:
                continue
            channel_username = CHANNELS[channel_id]['username']
            for post_num in all_post_nums:
                scheduled_time = post_times.get(post_num)
                image_path = image_map.get(post_num)
                post_data = text_posts.get(post_num, {})
                post_text = post_data.get('text') if isinstance(post_data, dict) else post_data
                category = post_data.get('category') if isinstance(post_data, dict) else None

                if not scheduled_time:
                    total_skipped += 1
                    continue

                schedule_time_utc = to_utc_naive(scheduled_time)
                try:
                    await send_telegram_message(
                        image_path=image_path,
                        post_text=post_text,
                        post_number=post_num,
                        category=category,
                        schedule_time=schedule_time_utc,
                        channel_username=channel_username,
                        channel_id=channel_id
                    )
                    total_scheduled += 1
                    status = "scheduled"
                except Exception:
                    total_failed += 1
                    status = "failed"

                all_results.append({
                    "post": post_num,
                    "image": os.path.basename(image_path) if image_path else None,
                    "text": post_text,
                    "time": scheduled_time.strftime("%H:%M"),
                    "status": status,
                    "channel": f"@{channel_username}"
                })

        return JSONResponse({
            "status": f"Scheduled {total_scheduled} posts across {len(selected_channels)} channels",
            "posts": all_results,
            "scheduled": total_scheduled,
            "failed": total_failed,
            "skipped": total_skipped,
            "total": len(all_post_nums) * len(selected_channels),
            "channels_processed": len(selected_channels)
        })

    except Exception as e:
        print(f"Error in /api/auto-schedule: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/bulk-schedule")
async def bulk_schedule(background_tasks: BackgroundTasks, files: List[UploadFile] = File(...), schedule_data: str = Form(...)):
    try:
        schedule_list = json.loads(schedule_data)
        post_time_map = schedule_list if isinstance(schedule_list, dict) else {item['post']: item['time'] for item in schedule_list if item.get('time')}

        image_files = {}
        text_paths = []
        for file in files:
            file_path = os.path.join(UPLOAD_DIR, file.filename)
            with open(file_path, "wb") as f:
                f.write(await file.read())
            name_lower = file.filename.lower()
            if name_lower.endswith(".txt"):
                text_paths.append(file_path)
            elif name_lower.endswith((".jpg", ".jpeg", ".png")):
                match = re.search(r'post(\d+)', name_lower)
                post_num = int(match.group(1)) if match else len(image_files) + 1
                image_files[post_num] = file_path

        txt_contents = []
        for path in text_paths:
            with open(path, 'r', encoding='utf-8') as f:
                txt_contents.append(f.read())
        text_posts = extract_all_posts_from_texts(txt_contents)
        all_post_nums = set(image_files.keys()).union(set(text_posts.keys()))

        scheduled_count = 0
        for post_num in sorted(all_post_nums):
            normalized_keys = {re.sub(r'[\W_]', '', k.lower()): v for k, v in post_time_map.items()}
            post_key = re.sub(r'[\W_]', '', f"post{post_num}.jpg".lower())
            time_str = normalized_keys.get(post_key)
            if not time_str:
                continue

            post_data = text_posts.get(post_num, {})
            post_text = post_data.get('text') if isinstance(post_data, dict) else None
            category = post_data.get('category') if isinstance(post_data, dict) else None
            schedule_time = round_to_nearest_5(datetime.fromisoformat(time_str))

            await send_telegram_message(
                image_path=image_files.get(post_num),
                post_text=post_text,
                post_number=post_num,
                category=category,
                schedule_time=schedule_time
            )
            scheduled_count += 1

        return JSONResponse({"status": f"{scheduled_count} posts scheduled successfully"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# =========================================================================
# 6. Startup & Daily Job
# =========================================================================

async def auto_fetch_yesterday_posts():
    print("⏰ Running daily auto-fetch for yesterday's posts...")
    today_ist = datetime.now(ist)
    yesterday_ist = today_ist - timedelta(days=1)

    start_time_ist = yesterday_ist.replace(hour=0, minute=0, second=0, microsecond=0)
    end_time_ist = yesterday_ist.replace(hour=23, minute=59, second=59, microsecond=999999)

    start_time_utc = start_time_ist.astimezone(timezone.utc)
    end_time_utc = end_time_ist.astimezone(timezone.utc)
    post_date_str = yesterday_ist.strftime("%Y-%m-%d")

    api_id_int, api_hash_val, session_str = get_telethon_creds()
    if not session_str:
        return

    try:
        async with TelegramClient(StringSession(session_str), api_id_int, api_hash_val) as client:
            for channel_id, data in CHANNELS.items():
                channel_username = data["username"]
                posts_data = []
                all_links = set()
                try:
                    async for msg in client.iter_messages(channel_username, offset_date=end_time_utc):
                        if not msg.date:
                            continue
                        msg_date_utc = msg.date if msg.date.tzinfo == timezone.utc else msg.date.astimezone(timezone.utc)
                        if msg_date_utc < start_time_utc:
                            break
                        if msg_date_utc > end_time_utc:
                            continue

                        msg_date_ist = msg_date_utc.astimezone(ist)
                        text_content = msg.text or ""
                        links = extract_links(text_content)
                        for l in links:
                            all_links.add(l)

                        posts_data.append({
                            "id": msg.id,
                            "time": msg_date_ist.strftime("%Y-%m-%d %H:%M:%S"),
                            "views": getattr(msg, "views", 0) or 0,
                            "text": text_content if text_content.strip() else ("📸 Image post" if msg.media else ""),
                            "links": links,
                            "channel": channel_username,
                            "category": "",
                            "status": "Live",
                            "media_type": "image" if msg.media else "text"
                        })

                    if posts_data:
                        clicks_map = await get_batch_clicks_data(list(all_links), post_date_str)
                        for p in posts_data:
                            tg = 0
                            wa = 0
                            for l in p["links"]:
                                st = clicks_map.get(l, {})
                                tg += st.get("telegram_clicks", 0)
                                wa += st.get("whatsapp_clicks", 0)
                            p["Telegram-clicks"] = tg
                            p["Whatsapp-clicks"] = wa

                        save_msg = save_posts_to_channel_date_sheets(posts_data, channel_username, scheduled=False)
                        print(f"✅ Auto-fetched {len(posts_data)} posts for @{channel_username}: {save_msg}")
                except Exception as e:
                    print(f"❌ Error auto-fetching for @{channel_username}: {e}")
    except Exception as e:
        print(f"Error in auto_fetch_yesterday_posts: {e}")

@app.on_event("startup")
async def startup_event():
    start_worker()
    scheduler.start()
    update_scheduler_job()

@app.on_event("shutdown")
async def shutdown_event():
    await stop_worker()
