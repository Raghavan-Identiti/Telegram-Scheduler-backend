# main.py
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, Form, Request, Query, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os, re, json
from typing import List
from datetime import date, datetime, timezone,timedelta
from logs_api import router as logs_router
from telegram_utils import CHANNELS, extract_all_posts_from_texts, send_telegram_message,get_blocked_times_from_sheet,initialize_google_sheets,sheets_available,api_id, api_hash, session_string,save_posts_to_channel_date_sheets,get_click_data_for_links
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
from clicksFind import get_clicks
ist = pytz.timezone("Asia/Kolkata")


UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI()  # <== All API routes will be prefixed with /api

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://telegram-scheduler-frontend.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static Mounts
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/logs", StaticFiles(directory="logs"), name="logs")
app.include_router(logs_router, prefix="/api")

@app.post("/api/sheets/connect-or-check")
async def connect_or_check(request: Request):
    global sheets_available
    body = await request.json()
    reconnect = body.get("reconnect", False)

    if reconnect or not sheets_available:
        # Attempt to reconnect
        success = initialize_google_sheets()
        sheets_available = success
        return {
            "connected": success,
            "message": "✅ Connected to Google Sheets" if success else "❌ Failed to connect Google Sheets"
        }
    else:
        # Just return current status
        return {
            "connected": sheets_available,
            "message": "✅ Google Sheets connected" if sheets_available else "❌ Google Sheets not connected"
        }

def to_utc_naive(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(tzinfo=None)

def round_to_nearest_5(dt: datetime) -> datetime:
    """
    Rounds time to the nearest 5-minute mark.
    Examples:
        10:27 → 10:25
        10:28 → 10:30
    """
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



# Add this parameter to the function signature
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

        # Parse selected channels
        selected_channels = json.loads(channels) if channels else []
        if not selected_channels:
            return JSONResponse(status_code=400, content={"error": "Please select at least one channel"})
        
        print(f"Selected channels: {selected_channels}")
        # Clear upload directory
        for f in os.listdir(UPLOAD_DIR):
            os.remove(os.path.join(UPLOAD_DIR, f))

        image_map = {}
        text_contents = []
        text_posts = {}

        # Save and process text files
        for file in text_files:
            filepath = os.path.join(UPLOAD_DIR, file.filename)
            with open(filepath, "wb") as f:
                f.write(await file.read())

            with open(filepath, 'r', encoding='utf-8') as f:
                text = f.read()
                text_contents.append(text)
        
        text_posts = extract_all_posts_from_texts(text_contents)

        print(f"📝 Extracted {len(text_posts)} posts from text files")

        # Save and process image files
        for file in image_files:
            fname = file.filename.lower()
            filepath = os.path.join(UPLOAD_DIR, file.filename)
            with open(filepath, "wb") as f:
                f.write(await file.read())

            match = re.search(r'(?:\*{0,2})\s*post\s*[-_\s]*(\d+)', fname, re.IGNORECASE)
            if match:
                post_num = int(match.group(1))
                image_map[post_num] = filepath
                print(f"🎯 Mapped image {file.filename} to post {post_num}")

        # Combine all post numbers
        all_post_nums = sorted(set(text_posts.keys()) | set(image_map.keys()))
        image_only_posts = [num for num in image_map if num not in text_posts]


        if image_only_posts and not send_image_only:
            return JSONResponse({
                "status": "confirm_image_only",
                "image_only_posts": image_only_posts
            })

        if not all_post_nums:
            return JSONResponse(status_code=400, content={"error": "No valid posts detected."})

        # Parse start and end date-times
        start_dt = round_to_nearest_5(ist.localize(datetime.fromisoformat(start_time.replace("Z", ""))))
        end_dt = round_to_nearest_5(ist.localize(parser.isoparse(end_time)))


        # Get blocked times from Google Sheet (these are naive datetime objects)
        sheet_blocked_times_naive = get_blocked_times_from_sheet(selected_channels)
        
        # Convert blocked times to IST timezone-aware datetimes for comparison
        blocked_times_ist = set()
        for naive_dt in sheet_blocked_times_naive:
            # Assume sheet times are in IST and make them timezone-aware
            if naive_dt.tzinfo is None:
                ist_dt = ist.localize(naive_dt)
            else:
                ist_dt = naive_dt.astimezone(ist)

            # Round to nearest 5 minutes to match our grid
            rounded_dt = round_to_nearest_5(ist_dt)
            blocked_times_ist.add(rounded_dt)
        
        print(f"📅 Blocked times from GSheet (IST): {sorted(blocked_times_ist)}")

        # Build 5-min grid inside the window
        ui_grid = []
        g = start_dt
        while g <= end_dt:
            ui_grid.append(round_to_nearest_5(g))
            g += timedelta(minutes=5)

        # Filter out blocked times from available slots
        available_slots = [slot for slot in ui_grid if slot not in blocked_times_ist]
        print(f"📊 Available slots: {len(available_slots)} out of {len(ui_grid)} total slots")

        # Scheduling logic
        post_times = {}
        assigned_slots = set()

        form_data = await request.form()
        times = form_data.getlist('times[]')
        print(f"📝 Raw times from form: {times}")

        if times:
            # Handle custom times from frontend
            for entry in times:
                if '|' in entry:
                    post_str, time_str = entry.split('|', 1)
                    try:
                        post_num = int(post_str.strip())
                        full_time = f"{start_dt.date()}T{time_str.strip()}"
                        dt_time = parse_custom_time(time_str.strip(), start_dt)
                        if not dt_time:
                            print(f"⚠️ Could not parse custom time: {time_str}")
                            continue
                        dt_time = round_to_nearest_5(ist.localize(dt_time)) if dt_time.tzinfo is None else dt_time


                        # Ensure custom time is on the same date as the selected date
                        if dt_time.date() != start_dt.date():
                            return JSONResponse(status_code=400, content={
                                "error": f"Custom time {time_str.strip()} must be on the selected date {start_dt.date()}"
                            })
                        
                        # Skip if blocked (this is the key fix)
                        if dt_time in blocked_times_ist:
                            print(f"⚠️ Custom time {dt_time} is blocked (from GSheet). Skipping post {post_num}.")
                            post_times[post_num] = None
                            continue

                        post_times[post_num] = dt_time
                        assigned_slots.add(dt_time)
                        print(f"✅ Custom time for post {post_num}: {dt_time}")
                    except Exception as e:
                        print(f"Invalid time format: {entry} - {e}")
                        continue

        # Get remaining available slots (excluding both blocked times and assigned slots)
        remaining_available_slots = [
            slot for slot in available_slots 
            if slot not in assigned_slots
        ]
        remaining_available_slots.sort()

        # Assign remaining posts
        unassigned_posts = [num for num in all_post_nums if num not in post_times]
        
        if interval_minutes > 0:
            # Fixed interval scheduling - only use available slots
            current_slot_index = 0
            current = start_dt
            
            for post_num in unassigned_posts:
                # Find next available slot at or after current time
                while current_slot_index < len(remaining_available_slots):
                    if remaining_available_slots[current_slot_index] >= current:
                        slot = remaining_available_slots[current_slot_index]
                        post_times[post_num] = slot
                        assigned_slots.add(slot)
                        remaining_available_slots.pop(current_slot_index)
                        print(f"✅ Interval scheduling: Post {post_num} at {slot}")
                        break
                    current_slot_index += 1
                else:
                    # No more available slots
                    post_times[post_num] = None
                    print(f"⚠️ No available slot for post {post_num}")
                
                current += timedelta(minutes=interval_minutes)
        else:
            # Auto distribute evenly across remaining available slots
            if len(unassigned_posts) <= len(remaining_available_slots):
                if len(unassigned_posts) > 1:
                    # Distribute evenly across available slots
                    step = len(remaining_available_slots) // len(unassigned_posts)
                    step = max(1, step)  # At least step of 1
                else:
                    step = 0
                
                for i, post_num in enumerate(unassigned_posts):
                    slot_index = min(i * step, len(remaining_available_slots) - 1)
                    slot = remaining_available_slots[slot_index]
                    post_times[post_num] = slot
                    assigned_slots.add(slot)
                    print(f"✅ Auto distribute: Post {post_num} at {slot}")
            else:
                # More posts than available slots - assign what we can
                for i, post_num in enumerate(unassigned_posts):
                    if i < len(remaining_available_slots):
                        slot = remaining_available_slots[i]
                        post_times[post_num] = slot
                        assigned_slots.add(slot)
                        print(f"✅ Auto distribute: Post {post_num} at {slot}")
                    else:
                        post_times[post_num] = None
                        print(f"⚠️ No available slot for post {post_num}")

        # Create time slots for frontend display
        all_blocked_times = blocked_times_ist | assigned_slots
        time_slots_for_frontend = []
        for slot in ui_grid:
            status = "blocked" if slot in blocked_times_ist else ("assigned" if slot in assigned_slots else "free")
            time_slots_for_frontend.append({
                "time": slot.strftime("%Y-%m-%d %H:%M"),
                "status": status
            })

        # Process and schedule posts
        preview_posts = []
        scheduled_count = 0
        failed_count = 0
        skipped_count = 0
        
        # Replace the section starting from "Process and schedule posts" until the return statement
        # Process and schedule posts for each channel
        all_results = []
        total_scheduled = 0
        total_failed = 0
        total_skipped = 0

        for channel_id in selected_channels:
            if channel_id not in CHANNELS:
                print(f"Unknown channel: {channel_id}")
                continue
                
            channel_username = CHANNELS[channel_id]['username']
            print(f"Processing channel: @{channel_username}")
            
            channel_scheduled = 0
            channel_failed = 0
            channel_skipped = 0
            channel_posts = []
            
            for post_num in all_post_nums:
                scheduled_time = post_times.get(post_num)
                image_path = image_map.get(post_num)
                post_data = text_posts.get(post_num, {})
                post_text = post_data.get('text') if isinstance(post_data, dict) else post_data
                category = post_data.get('category') if isinstance(post_data, dict) else None
                custom_time = post_data.get('custom_time') if isinstance(post_data, dict) else None

                if not scheduled_time:
                    channel_posts.append({
                        "post": post_num,
                        "image": os.path.basename(image_path) if image_path else None,
                        "text": post_text,
                        "category": category,
                        "custom_time": custom_time,
                        "time": "N/A",
                        "status": "skipped",
                        "error": "No available slot within selected window",
                        "channel": f"@{channel_username}"
                    })
                    channel_skipped += 1
                    continue

                # Double-check: don't schedule on blocked times
                if scheduled_time in blocked_times_ist:
                    channel_posts.append({
                        "post": post_num,
                        "image": os.path.basename(image_path) if image_path else None,
                        "text": post_text,
                        "category": category,
                        "custom_time": custom_time,
                        "time": scheduled_time.strftime("%H:%M"),
                        "status": "skipped",
                        "error": "Time slot is blocked in Google Sheet",
                        "channel": f"@{channel_username}"
                    })
                    channel_skipped += 1
                    continue

                # Schedule the post
                if not scheduled_time:
                    continue
                schedule_time = to_utc_naive(scheduled_time)
                try:
                    await send_telegram_message(
                        image_path=image_map.get(post_num),
                        post_text=post_text,
                        post_number=post_num,
                        category=category,
                        schedule_time=schedule_time,
                        channel_username=channel_username,
                        channel_id=channel_id
                    )
                    channel_scheduled += 1
                    status = "scheduled"
                    error = None
                    print(f"Scheduled post {post_num} to @{channel_username} at {scheduled_time}")
                except Exception as e:
                    status = "failed"
                    error = str(e)
                    channel_failed += 1
                    print(f"Failed to schedule post {post_num} to @{channel_username}: {e}")

                channel_posts.append({
                    "post": post_num,
                    "image": os.path.basename(image_path) if image_path else None,
                    "text": post_text,
                    "category": category,
                    "time": scheduled_time.strftime("%H:%M") if scheduled_time else "N/A",
                    "status": status,
                    "error": error,
                    "channel": f"@{channel_username}"
                })
            
            # Add channel results
            all_results.extend(channel_posts)
            total_scheduled += channel_scheduled
            total_failed += channel_failed
            total_skipped += channel_skipped
            
            print(f"Channel @{channel_username}: {channel_scheduled} scheduled, {channel_failed} failed, {channel_skipped} skipped")

        return JSONResponse({
            "status": f"Scheduled {total_scheduled} posts across {len(selected_channels)} channels, {total_failed} failed, {total_skipped} skipped",
            "posts": all_results,
            "scheduled": total_scheduled,
            "failed": total_failed,
            "skipped": total_skipped,
            "total": len(all_post_nums) * len(selected_channels),
            "blocked_slots": len(blocked_times_ist),
            "time_slots": time_slots_for_frontend,
            "channels_processed": len(selected_channels)
        })

    except Exception as e:
        print(f"Error in /api/auto-schedule: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error"})


class ReadPostsRequest(BaseModel):
    channel: str
    start_time: datetime
    end_time: datetime

def extract_links(text: str):
    if not text:
        return []
    url_pattern = re.compile(r"(https?://\S+|amzaff\.in/\S+)")
    links = url_pattern.findall(text)
    return [str(l).strip() for l in links if l]

def normalize_post(post_info):
    """Ensure all required keys exist for save_posts_to_channel_date_sheets"""
    text_content = post_info.get("text") or post_info.get("Full_Text") or "📸 Image post"
    links = post_info.get("links") or post_info.get("Links") or extract_links(text_content)
    return {
        "text": text_content,
        "category": post_info.get("category") or "",
        "time": post_info.get("time"),
        "status": post_info.get("status") or "Live",
        "links": links,
        "Telegram-clicks": post_info.get("Telegram-clicks", 0),
        "Whatsapp-clicks": post_info.get("Whatsapp-clicks", 0),
    }

@app.post("/api/read-posts")
async def read_posts(req: ReadPostsRequest):
    posts_data = []
    start_time_utc = req.start_time.astimezone(pytz.UTC)
    end_time_utc = req.end_time.astimezone(pytz.UTC)

    async with TelegramClient(StringSession(session_string), api_id, api_hash) as client:
        async for msg in client.iter_messages(req.channel, offset_date=end_time_utc):
            if msg.date is None:
                continue
            msg_date_utc = msg.date.replace(tzinfo=pytz.UTC)
            if not (start_time_utc <= msg_date_utc <= end_time_utc):
                continue

            msg_date_ist = msg_date_utc.astimezone(pytz.timezone("Asia/Kolkata"))
            text_content = msg.text if msg.text else ""
            links = extract_links(text_content)

            # Get click data
            post_date_str = msg_date_ist.strftime("%Y-%m-%d")
            click_data = get_click_data_for_links(links, post_date_str)

            post_info = {
                "id": msg.id,
                "time": msg_date_ist.strftime("%Y-%m-%d %H:%M:%S"),
                "Telegram-Views": msg.views if hasattr(msg, "views") else 0,
                "Whatsapp-Views": 0,
                "Telegram-clicks": click_data["telegram_clicks"],
                "Whatsapp-clicks": click_data["whatsapp_clicks"],
                "text": text_content if text_content.strip() else "📸 Image post (no text or links)",
                "links": links,
                "category": "",
            }

            posts_data.append(normalize_post(post_info))

    save_msg = save_posts_to_channel_date_sheets(posts_data, req.channel, scheduled=False)
    return {
        "status": "success",
        "count": len(posts_data),
        "message": save_msg,
        "posts": posts_data,
        "date_range": {
            "start": req.start_time.strftime("%d %b %Y"),
            "end": req.end_time.strftime("%d %b %Y")
        },
        "channel": req.channel
    }

@app.post("/api/scheduled-posts")
async def read_scheduled_messages(req: ReadPostsRequest):
    scheduled_posts = []

    async with TelegramClient(StringSession(session_string), api_id, api_hash) as client:
        result = await client(GetScheduledHistoryRequest(peer=req.channel, hash=0))
        for msg in result.messages:
            msg_date_ist = msg.date.astimezone(pytz.timezone("Asia/Kolkata")) if msg.date else datetime.now().astimezone(pytz.timezone("Asia/Kolkata"))
            text_content = msg.message or ""
            links = extract_links(text_content)

            post_date_str = msg_date_ist.strftime("%Y-%m-%d")
            click_data = get_click_data_for_links(links, post_date_str)

            post_info = {
                "id": msg.id,
                "time": msg_date_ist.strftime("%Y-%m-%d %H:%M:%S"),
                "text": text_content if text_content.strip() else "📸 Image post (no text or links)",
                "links": links,
                "category": "",
                "status": "Scheduled",
                "Telegram-clicks": click_data["telegram_clicks"],
                "Whatsapp-clicks": click_data["whatsapp_clicks"],
            }

            scheduled_posts.append(normalize_post(post_info))

    save_msg = save_posts_to_channel_date_sheets(scheduled_posts, req.channel, scheduled=True)
    return {
        "status": "success",
        "count": len(scheduled_posts),
        "message": save_msg,
        "scheduled_posts": scheduled_posts
    }

@app.get("/api/posts-summary")
async def get_posts_summary(
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    channels: str = Query(None, description="Comma-separated channel IDs")
):
    results = []
    
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d")
        start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
        end_of_day = target_date.replace(hour=23, minute=59, second=59, microsecond=999999, tzinfo=timezone.utc)
        
        print(f"📅 Fetching posts for date: {date}")
        print(f"   Start: {start_of_day}")
        print(f"   End: {end_of_day}")
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    target_channels = CHANNELS
    if channels:
        channel_ids = [id.strip() for id in channels.split(",")]
        target_channels = {k: v for k, v in CHANNELS.items() if k in channel_ids}
    
    async with TelegramClient(StringSession(session_string), api_id, api_hash) as client:
        for channel_id, data in target_channels.items():
            username = data["username"]
            try:
                entity = await client.get_entity(username)
                
                live_count = 0
                messages_found = []
                async for message in client.iter_messages(
                    entity,
                    limit=None,
                    reverse=False
                ):
                    msg_date = message.date
                    if msg_date.tzinfo is None:
                        msg_date = msg_date.replace(tzinfo=timezone.utc)
                    elif msg_date.tzinfo != timezone.utc:
                        msg_date = msg_date.astimezone(timezone.utc)
                    
                    if msg_date >= start_of_day and msg_date <= end_of_day:
                        messages_found.append(message)
                        live_count += 1
                    elif msg_date < start_of_day:
                        break
                
                print(f"📊 Found {live_count} live messages for @{username} on {date}")
                
                scheduled_count = 0
                try:
                    scheduled_result = await client(
                        GetScheduledHistoryRequest(peer=entity, hash=0)
                    )
                    
                    if hasattr(scheduled_result, 'messages'):
                        for msg in scheduled_result.messages:
                            sched_date = msg.date
                            if sched_date.tzinfo is None:
                                sched_date = sched_date.replace(tzinfo=timezone.utc)
                            elif sched_date.tzinfo != timezone.utc:
                                sched_date = sched_date.astimezone(timezone.utc)
                            
                            if sched_date >= start_of_day and sched_date <= end_of_day:
                                scheduled_count += 1
                    
                    print(f"📊 Found {scheduled_count} scheduled messages for @{username} on {date}")
                    
                except Exception as sched_err:
                    print(f"⚠️ Could not fetch scheduled posts for @{username}: {sched_err}")
                
                results.append({
                    "channel_id": channel_id,
                    "channel_username": username,
                    "live_posts": live_count,
                    "scheduled_posts": scheduled_count,
                })
                
                print(f"✅ @{username}: Live = {live_count}, Scheduled = {scheduled_count}")
                
            except Exception as e:
                print(f"⚠️ Failed to get data for @{username}: {e}")
                results.append({
                    "channel_id": channel_id,
                    "channel_username": username,
                    "live_posts": 0,
                    "scheduled_posts": 0,
                    "error": str(e)
                })
    
    total_live = sum(ch.get("live_posts", 0) for ch in results)
    total_scheduled = sum(ch.get("scheduled_posts", 0) for ch in results)
    
    return {
        "status": "success",
        "date": date,
        "channels": results,
        "total_channels": len(results),
        "totals": {
            "live_posts": total_live,
            "scheduled_posts": total_scheduled,
            "total_posts": total_live + total_scheduled
        }
    }

@app.get("/api/channels")
async def get_available_channels():
    channels_list = []
    for channel_id, data in CHANNELS.items():
        channels_list.append({
            "id": channel_id,
            "username": data["username"],
            "name": data.get("name", data["username"].replace("@", "").title())
        })
    
    return {
        "status": "success",
        "channels": channels_list,
        "total": len(channels_list)
    }

@app.get("/api/posts-range")
async def get_posts_range(
    start_date: str = Query(..., description="Start date in YYYY-MM-DD format"),
    end_date: str = Query(..., description="End date in YYYY-MM-DD format"),
    channels: str = Query(None, description="Comma-separated channel IDs")
):
    """
    Get posts for a date range with optional channel filtering.
    
    Example: /api/posts-range?start_date=2025-09-01&end_date=2025-09-30&channels=1,2
    """
    results = []
    
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        end = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
        
        if start > end:
            raise HTTPException(status_code=400, detail="start_date must be before end_date")
            
        # Check if date range is too large (optional safety check)
        date_diff = (end - start).days
        if date_diff > 31:
            raise HTTPException(status_code=400, detail="Date range cannot exceed 31 days")
            
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    # Filter channels if specified
    target_channels = CHANNELS
    if channels:
        channel_ids = [id.strip() for id in channels.split(",")]
        target_channels = {k: v for k, v in CHANNELS.items() if k in channel_ids}
    
    async with TelegramClient(StringSession(session_string), api_id, api_hash) as client:
        for channel_id, data in target_channels.items():
            username = data["username"]
            try:
                entity = await client.get_entity(username)
                
                # Count live posts in range
                live_count = 0
                async for message in client.iter_messages(
                    entity,
                    limit=None,
                    reverse=False
                ):
                    # Convert message date to UTC
                    msg_date = message.date
                    if msg_date.tzinfo is None:
                        msg_date = msg_date.replace(tzinfo=timezone.utc)
                    elif msg_date.tzinfo != timezone.utc:
                        msg_date = msg_date.astimezone(timezone.utc)
                    
                    if msg_date >= start and msg_date <= end:
                        live_count += 1
                    elif msg_date < start:
                        break
                
                # Count scheduled posts in range
                scheduled_count = 0
                try:
                    scheduled_result = await client(
                        GetScheduledHistoryRequest(peer=entity, hash=0)
                    )
                    
                    if hasattr(scheduled_result, 'messages'):
                        for msg in scheduled_result.messages:
                            sched_date = msg.date
                            if sched_date.tzinfo is None:
                                sched_date = sched_date.replace(tzinfo=timezone.utc)
                            elif sched_date.tzinfo != timezone.utc:
                                sched_date = sched_date.astimezone(timezone.utc)
                            
                            if sched_date >= start and sched_date <= end:
                                scheduled_count += 1
                                
                except Exception as sched_err:
                    print(f"⚠️ Could not fetch scheduled posts for @{username}: {sched_err}")
                
                results.append({
                    "channel_id": channel_id,
                    "channel_username": username,
                    "live_posts": live_count,
                    "scheduled_posts": scheduled_count,
                })
                
                print(f"✅ @{username} ({start_date} to {end_date}): Live = {live_count}, Scheduled = {scheduled_count}")
                
            except Exception as e:
                print(f"⚠️ Failed to get data for @{username}: {e}")
                results.append({
                    "channel_id": channel_id,
                    "channel_username": username,
                    "live_posts": 0,
                    "scheduled_posts": 0,
                    "error": str(e)
                })
    
    # Calculate totals
    total_live = sum(ch.get("live_posts", 0) for ch in results)
    total_scheduled = sum(ch.get("scheduled_posts", 0) for ch in results)
    
    return {
        "status": "success",
        "start_date": start_date,
        "end_date": end_date,
        "channels": results,
        "total_channels": len(results),
        "date_range_days": (end - start).days + 1,
        "totals": {
            "live_posts": total_live,
            "scheduled_posts": total_scheduled,
            "total_posts": total_live + total_scheduled
        }
    }

def save_to_excel(posts, filename="posts.xlsx"):
    import openpyxl
    from openpyxl.styles import Alignment

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Posts"

    headers = ["Post ID", "Date & Time (IST)", "Views", "Text", "Links"]
    ws.append(headers)

    for post in posts:
        time_str = datetime.strptime(
            post['time'], "%Y-%m-%d %H:%M:%S"
        ).strftime("%d %b %Y, %I:%M %p")

        links_str = ", ".join(post["links"]) if post["links"] else ""

        ws.append([
            post["id"],
            time_str + " IST",
            post["views"],
            post["text"],
            # post["image"],
            links_str
        ])

    for col in ws.columns:
        for cell in col:
            cell.alignment = Alignment(wrap_text=True, vertical="top")

    wb.save(filename)
    return filename


@app.get("/api/calendar-slots")
def get_calendar_slots(date: str = Query(..., description="Format: YYYY-MM-DD")):
    log_file = os.path.join("logs", "post_logs.xlsx")
    if not os.path.exists(log_file):
        return []

    try:
        df = pd.read_excel(log_file)
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce').dt.date
        df['Time'] = pd.to_datetime(df['Time'], format='%H:%M:%S', errors='coerce').dt.time

        # Filter by requested date
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
                "post": row['Post Number']
            })

        return slots
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/bulk-schedule")
async def bulk_schedule(background_tasks: BackgroundTasks, files: List[UploadFile] = File(...), schedule_data: str = Form(...)):
    try:
        # Clear previous uploads
        print("Received schedule_data:", schedule_data)
        schedule_list = json.loads(schedule_data)
        print("Parsed schedule list:", schedule_list)
        if isinstance(schedule_list, dict):
            post_time_map = schedule_list  # Already in the right form
        else:
            # fallback for old format
            post_time_map = {item['post']: item['time'] for item in schedule_list if item['time']}
        for f in os.listdir(UPLOAD_DIR):
            os.remove(os.path.join(UPLOAD_DIR, f))

        image_files = {}
        text_paths = []

        # Save uploaded files
        for file in files:
            file_path = os.path.join(UPLOAD_DIR, file.filename)
            with open(file_path, "wb") as f:
                f.write(await file.read())

            name_lower = file.filename.lower().replace(" ", "").replace("_", "")
            if name_lower.endswith(".txt"):
                text_paths.append(file_path)
            elif name_lower.endswith((".jpg", ".jpeg", ".png")):
                match = re.search(r'post(\d+)', name_lower)
                post_num = int(match.group(1)) if match else len(image_files) + 1
                image_files[post_num] = file_path

        if not text_paths:
            return JSONResponse(status_code=400, content={"error": "No .txt files provided"})

        if not image_files:
            return JSONResponse(status_code=400, content={"error": "No image files matched 'postX'"})

       # Extract post numbers from both image filenames and text files
        image_post_nums = set(image_files.keys())

        txt_contents = []
        for path in text_paths:
            with open(path, 'r', encoding='utf-8') as f:
                txt_contents.append(f.read())

        text_posts = extract_all_posts_from_texts(txt_contents)
        text_post_nums = set(text_posts.keys())

        # A post is defined by having either image or text (or both), but only counted once
        all_post_nums = image_post_nums.union(text_post_nums)

        # Schedule each post with the full context of txt files
        # base_time = datetime.fromisoformat(scheduled_time) if scheduled_time else datetime.now()

        for post_num in sorted(all_post_nums):
            normalized_keys = {
            re.sub(r'[\W_]', '', k.lower()): v
            for k, v in post_time_map.items()
            }
            post_key_raw = f"post{post_num}.jpg"
            post_key = re.sub(r'[\W_]', '', post_key_raw.lower())  # removes dots, dashes, underscores
            time_str = normalized_keys.get(post_key)
            print(f"🔍 Matching key: {post_key} -> time: {time_str}")
            if not time_str:
                continue  # Skip if no schedule provided

            post_data = text_posts.get(post_num, {})
            post_text = post_data.get('text') if isinstance(post_data, dict) else None
            category = post_data.get('category') if isinstance(post_data, dict) else None
            print(f"📌 Scheduling Post {post_num} at {time_str} with image={image_files.get(post_num)}, text={post_text}")
            schedule_time = round_to_nearest_5(datetime.fromisoformat(time_str))
            await send_telegram_message(
                image_path=image_files.get(post_num),
                post_text=post_text,
                post_number=post_num,
                category=category,
                schedule_time=schedule_time
            )

        return JSONResponse({"status": f"{len(all_post_nums)} posts scheduled successfully"})

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})