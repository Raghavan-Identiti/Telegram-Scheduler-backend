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
    api_id,
    api_hash,
    session_string,
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
if os.path.exists("logs"):
    app.mount("/logs", StaticFiles(directory="logs"), name="logs")

app.include_router(logs_router, prefix="/api")
app.include_router(recurrence_router, prefix="/api")
app.include_router(whatsapp_router)

@app.get("/")
async def root():
    return {"status": "success", "message": "TeleQueue API is running!"}

# =========================================================================
# Dynamic Google Sheets Configuration (Powers QPilot Frontend)
# =========================================================================

@app.get("/api/sheets/config")
async def get_sheets_config():
    settings = load_settings()
    return {
        "status": "success",
        "default_sheet_id": DEFAULT_SHEET_ID,
        "service_account_email": service_account_email,
        "channel_sheets": settings.get("channel_sheets", {})
    }

@app.post("/api/sheets/update-config")
async def update_sheets_config(payload: Dict[str, Any]):
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

@app.post("/api/sheets/test-connection")
async def test_sheet_connection(request: Request):
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
                "help": f"Please ensure spreadsheet is shared with: {service_account_email}"
            }
        )

# =========================================================================
# Fast Content Reader & Auto-Fetch
# =========================================================================

class ReadPostsRequest(BaseModel):
    channel: str
    start_time: datetime
    end_time: datetime
    sheet_url: Optional[str] = None
    sheet_tab: Optional[str] = None

@app.post("/api/read-posts")
async def read_posts(req: ReadPostsRequest):
    """
    ⚡ ULTRA-FAST CONTENT READER ⚡
    1. Early break when reaching messages older than start_time
    2. Parallel link clicks fetching in 1s
    3. Writes to the channel's dynamic Google Sheet with automatic fallback
    """
    posts_data = []
    start_time_utc = req.start_time.astimezone(pytz.UTC)
    end_time_utc = req.end_time.astimezone(pytz.UTC)
    post_date_str = req.start_time.astimezone(ist).strftime("%Y-%m-%d")

    all_links = set()

    async with TelegramClient(StringSession(session_string), api_id, api_hash) as client:
        async for msg in client.iter_messages(req.channel, offset_date=end_time_utc):
            if msg.date is None:
                continue
            msg_date_utc = msg.date.replace(tzinfo=pytz.UTC)

            # 🚀 EARLY BREAK: Stop fetching as soon as we reach previous days!
            if msg_date_utc < start_time_utc:
                break
            if msg_date_utc > end_time_utc:
                continue

            msg_date_ist = msg_date_utc.astimezone(ist)
            text_content = msg.text or ""
            links = extract_links(text_content)
            for link in links:
                all_links.add(link)

            post_info = {
                "id": msg.id,
                "time": msg_date_ist.strftime("%Y-%m-%d %H:%M:%S"),
                "views": getattr(msg, "views", 0) or 0,
                "text": text_content if text_content.strip() else ("📸 Image post" if msg.media else ""),
                "links": links,
                "channel": req.channel,
                "category": "",
                "status": "Live",
                "media_type": "image" if msg.media else "text"
            }
            posts_data.append(post_info)

    # Parallel bulk click fetch
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

async def auto_fetch_yesterday_posts():
    print("⏰ Running optimized daily auto-fetch for yesterday's posts...")
    today_ist = datetime.now(ist)
    yesterday_ist = today_ist - timedelta(days=1)

    start_time_ist = yesterday_ist.replace(hour=0, minute=0, second=0, microsecond=0)
    end_time_ist = yesterday_ist.replace(hour=23, minute=59, second=59, microsecond=999999)

    start_time_utc = start_time_ist.astimezone(pytz.UTC)
    end_time_utc = end_time_ist.astimezone(pytz.UTC)
    post_date_str = yesterday_ist.strftime("%Y-%m-%d")

    async with TelegramClient(StringSession(session_string), api_id, api_hash) as client:
        for channel_id, data in CHANNELS.items():
            channel_username = data["username"]
            posts_data = []
            all_links = set()
            try:
                async for msg in client.iter_messages(channel_username, offset_date=end_time_utc):
                    if msg.date is None:
                        continue
                    msg_date_utc = msg.date.replace(tzinfo=pytz.UTC)
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

                    # Saves dynamically to the channel's sheet
                    save_msg = save_posts_to_channel_date_sheets(posts_data, channel_username, scheduled=False)
                    print(f"✅ Auto-fetched {len(posts_data)} posts for @{channel_username}: {save_msg}")

            except Exception as e:
                print(f"❌ Error auto-fetching for @{channel_username}: {e}")

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

@app.on_event("startup")
async def startup_event():
    start_worker()
    scheduler.start()

@app.on_event("shutdown")
async def shutdown_event():
    await stop_worker()
