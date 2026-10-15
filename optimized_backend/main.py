# optimized_backend/main.py
import os
import re
import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
import pytz
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.messages import GetScheduledHistoryRequest

from optimized_backend.clicksFind import get_batch_clicks_data
from optimized_backend.telegram_utils import (
    CHANNELS,
    extract_links,
    save_posts_to_channel_date_sheets_batch,
    initialize_google_sheets,
    sheets_available,
    api_id,
    api_hash,
    session_string,
    load_settings,
    save_settings,
    extract_sheet_id_from_url,
    get_channel_sheet_target,
    DEFAULT_SHEET_ID,
    gc,
    service_account_email
)

ist = pytz.timezone("Asia/Kolkata")

app = FastAPI(title="TeleQueue Dynamic Scraping & Sheets API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

telegram_client: Optional[TelegramClient] = None

async def get_telegram_client() -> TelegramClient:
    global telegram_client
    if telegram_client is None or not telegram_client.is_connected():
        telegram_client = TelegramClient(StringSession(session_string), int(api_id), api_hash)
        await telegram_client.connect()
    return telegram_client

class ReadPostsRequest(BaseModel):
    channel: str
    start_time: datetime
    end_time: datetime
    # Optional dynamic sheet overrides from frontend
    sheet_url: Optional[str] = None
    sheet_tab: Optional[str] = None

class TestSheetRequest(BaseModel):
    sheet_url: Optional[str] = None
    sheet_id: Optional[str] = None
    channel_id: Optional[str] = None

# =========================================================================
# 1. Dynamic Google Sheet Config Endpoints (Supports QPilot Frontend)
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
    """
    Save updated Google Sheet URLs and tab names per channel dynamically.
    Supports all frontend payload variations:
    - { "channels": [ { "channelId": "...", "sheetUrl": "...", "sheetTab": "..." } ] }
    - { "channel_sheets": { ... } }
    """
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
async def test_sheet_connection(req: TestSheetRequest):
    """
    Tests if a provided Google Sheet link is accessible and shared with the service account.
    Powers the 'Test Sheet' button in your QPilot frontend!
    """
    global gc, sheets_available
    if not sheets_available or not gc:
        initialize_google_sheets()

    raw_target = req.sheet_id or req.sheet_url
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
                "help": f"Please ensure the spreadsheet is shared with Editor permission with: {service_account_email}"
            }
        )

# =========================================================================
# 2. Optimized Scraper & Dynamic Sheet Writer
# =========================================================================

async def scrape_and_process_channel(
    client: TelegramClient,
    channel_username: str,
    start_time_utc: datetime,
    end_time_utc: datetime,
    post_date_str: str,
    scheduled: bool = False,
    override_sheet_id: Optional[str] = None,
    override_sheet_tab: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    ⚡ ULTRA-FAST SCRAPER WITH DYNAMIC SHEET SYNC ⚡
    - Scrapes posts with early loop break (newest -> oldest)
    - Parallel batch fetches Quic.ly click tracking (<2s)
    - Writes to the channel's dynamic Google Sheet (or default fallback if fails)
    """
    raw_posts = []
    all_links_to_fetch = set()

    if not scheduled:
        async for msg in client.iter_messages(channel_username, offset_date=end_time_utc):
            if msg.date is None:
                continue
            msg_date_utc = msg.date.replace(tzinfo=pytz.UTC)

            # Early break when passing target day start
            if msg_date_utc < start_time_utc:
                break
            if msg_date_utc > end_time_utc:
                continue

            msg_date_ist = msg_date_utc.astimezone(ist)
            text_content = msg.text or ""
            links = extract_links(text_content)
            for link in links:
                all_links_to_fetch.add(link)

            raw_posts.append({
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
    else:
        result = await client(GetScheduledHistoryRequest(peer=channel_username, hash=0))
        for msg in result.messages:
            msg_date_ist = msg.date.astimezone(ist) if msg.date else datetime.now(ist)
            text_content = msg.message or ""
            links = extract_links(text_content)
            for link in links:
                all_links_to_fetch.add(link)

            raw_posts.append({
                "id": msg.id,
                "time": msg_date_ist.strftime("%Y-%m-%d %H:%M:%S"),
                "views": 0,
                "text": text_content if text_content.strip() else "📸 Image post",
                "links": links,
                "channel": channel_username,
                "category": "",
                "status": "Scheduled",
            })

    # Bulk parallel click data fetch (1-2s total)
    clicks_map = await get_batch_clicks_data(list(all_links_to_fetch), post_date_str)

    for post in raw_posts:
        tg_clicks = 0
        wa_clicks = 0
        for link in post["links"]:
            stats = clicks_map.get(link, {})
            tg_clicks += stats.get("telegram_clicks", 0)
            wa_clicks += stats.get("whatsapp_clicks", 0)
        post["Telegram-clicks"] = tg_clicks
        post["Whatsapp-clicks"] = wa_clicks

    # 🚀 DYNAMIC SHEET WRITE (with automatic fallback to default if dynamic fails)
    if raw_posts:
        save_msg = save_posts_to_channel_date_sheets_batch(
            posts_data=raw_posts,
            channel_username=channel_username,
            scheduled=scheduled,
            override_sheet_id=override_sheet_id,
            override_sheet_tab=override_sheet_tab
        )
        print(f"[{channel_username}] {save_msg}")

    return raw_posts


@app.post("/api/read-posts")
async def read_posts(req: ReadPostsRequest):
    """
    Content Reader API endpoint.
    Scrapes channel posts and saves to the user's dynamic sheet!
    """
    client = await get_telegram_client()
    start_time_utc = req.start_time.astimezone(pytz.UTC)
    end_time_utc = req.end_time.astimezone(pytz.UTC)
    post_date_str = req.start_time.astimezone(ist).strftime("%Y-%m-%d")

    override_id = extract_sheet_id_from_url(req.sheet_url) if req.sheet_url else None

    posts_data = await scrape_and_process_channel(
        client=client,
        channel_username=req.channel,
        start_time_utc=start_time_utc,
        end_time_utc=end_time_utc,
        post_date_str=post_date_str,
        scheduled=False,
        override_sheet_id=override_id,
        override_sheet_tab=req.sheet_tab
    )

    # Indicate target sheet in the response
    target_sheet_id, target_tab = get_channel_sheet_target(req.channel)
    if override_id:
        target_sheet_id = override_id
    if req.sheet_tab:
        target_tab = req.sheet_tab

    return {
        "status": "success",
        "count": len(posts_data),
        "channel": req.channel,
        "target_sheet_id": target_sheet_id,
        "target_tab": target_tab,
        "posts": posts_data
    }


@app.get("/api/auto-fetch-yesterday")
async def auto_fetch_yesterday():
    """
    Runs daily auto-fetch across all channels in parallel.
    Each channel writes into its own configured dynamic sheet!
    """
    client = await get_telegram_client()
    today_ist = datetime.now(ist)
    yesterday_ist = today_ist - timedelta(days=1)

    start_time_ist = yesterday_ist.replace(hour=0, minute=0, second=0, microsecond=0)
    end_time_ist = yesterday_ist.replace(hour=23, minute=59, second=59, microsecond=999999)

    start_time_utc = start_time_ist.astimezone(pytz.UTC)
    end_time_utc = end_time_ist.astimezone(pytz.UTC)
    post_date_str = yesterday_ist.strftime("%Y-%m-%d")

    tasks = []
    for _, data in CHANNELS.items():
        channel_username = data["username"]
        tasks.append(
            scrape_and_process_channel(
                client=client,
                channel_username=channel_username,
                start_time_utc=start_time_utc,
                end_time_utc=end_time_utc,
                post_date_str=post_date_str,
                scheduled=False
            )
        )

    results = await asyncio.gather(*tasks, return_exceptions=True)

    summary = []
    total_posts = 0
    for idx, (cid, data) in enumerate(CHANNELS.items()):
        res = results[idx]
        sheet_id, tab_name = get_channel_sheet_target(data["username"])
        if isinstance(res, Exception):
            summary.append({
                "channel": data["username"],
                "status": "error",
                "error": str(res),
                "target_sheet": sheet_id
            })
        else:
            summary.append({
                "channel": data["username"],
                "status": "success",
                "count": len(res),
                "target_sheet": sheet_id,
                "target_tab": tab_name
            })
            total_posts += len(res)

    return {
        "status": "success",
        "date": post_date_str,
        "total_posts_scraped": total_posts,
        "channels": summary
    }
