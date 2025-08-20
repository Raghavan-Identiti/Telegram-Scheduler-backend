# main.py
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, Form, Request,Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os, re, json
from typing import List
from datetime import datetime, timezone,timedelta
from logs_api import router as logs_router
from telegram_utils import extract_all_posts_from_texts, send_telegram_message,get_blocked_times_from_sheet
import pandas as pd


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

def get_blocked_times(log_path="logs/post_logs.xlsx"):
    blocked_times = []
    if os.path.exists(log_path):
        df = pd.read_excel(log_path)
        for _, row in df.iterrows():
            if pd.isna(row.get('Date')) or pd.isna(row.get('Time')):
                continue
            try:
                dt_str = f"{row['Date']} {row['Time']}"
                dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                dt = round_to_nearest_5(dt.replace(second=0, microsecond=0))  # 👈 normalize
                blocked_times.append(dt)
            except Exception as e:
                print(f"Skipping invalid log row: {e}")
    return blocked_times

@app.post("/api/auto-schedule")
async def auto_schedule(
    request: Request,
    background_tasks: BackgroundTasks,
    text_files: List[UploadFile] = File([]),
    image_files: List[UploadFile] = File([]),
    start_time: str = Form(...),
    end_time: str = Form(...),
    times: List[str] = Form(default=[]),
    send_image_only: bool = Form(default=False),
    interval_minutes: int = Form(default=0)  # 0 = Auto distribute
):
    try:
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

        # Extract posts from text
        text_posts = extract_all_posts_from_texts(text_contents)

        # Save and process image files
        for file in image_files:
            fname = file.filename.lower()
            filepath = os.path.join(UPLOAD_DIR, file.filename)
            with open(filepath, "wb") as f:
                f.write(await file.read())

            match = re.search(r'post[-_ ]?0*(\d+)', fname, re.IGNORECASE)
            if match:
                post_num = int(match.group(1))
                image_map[post_num] = filepath

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
        start_dt = round_to_nearest_5(datetime.fromisoformat(start_time))
        end_dt = round_to_nearest_5(datetime.fromisoformat(end_time))

        # Already-blocked times from logs
        log_blocked_times = set(get_blocked_times_from_sheet())
        assigned_slots = set()
        blocked_times = log_blocked_times | assigned_slots

        # Build 5-min grid inside the window
        ui_grid = []
        g = start_dt
        while g <= end_dt:
            ui_grid.append(round_to_nearest_5(g))
            g += timedelta(minutes=5)

        # Scheduling logic
        post_times = {}

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
                        dt_time = round_to_nearest_5(datetime.fromisoformat(full_time))

                        if dt_time < start_dt or dt_time > end_dt:
                            return JSONResponse(status_code=400, content={
                                "error": f"Custom time {time_str.strip()} is outside the selected window"
                            })
                        if dt_time in log_blocked_times:
                            print(f"⚠️ Custom time {time_str.strip()} is blocked, marking as N/A")
                            post_times[post_num] = None
                            continue

                        post_times[post_num] = dt_time
                        assigned_slots.add(dt_time)
                        print(f"✅ Custom time for post {post_num}: {dt_time}")
                    except Exception as e:
                        print(f"Invalid time format: {entry} - {e}")
                        continue

        # Assign remaining posts
        if interval_minutes > 0:
            # Fixed interval scheduling
            current = start_dt + timedelta(minutes=interval_minutes)
            for post_num in all_post_nums:
                if post_num not in post_times:
                    if current <= end_dt:
                        slot = round_to_nearest_5(current)
                        if slot not in log_blocked_times:
                            post_times[post_num] = slot
                            assigned_slots.add(slot)
                        else:
                            post_times[post_num] = None
                        current += timedelta(minutes=interval_minutes)
                    else:
                        post_times[post_num] = None
        else:
            # Auto distribute evenly
            unassigned_posts = [num for num in all_post_nums if num not in post_times]
            total_posts = len(unassigned_posts)
            if total_posts > 1:
                step = int((end_dt - start_dt).total_seconds() // 60 // (total_posts - 1))
            else:
                step = 0
            current = start_dt
            for post_num in unassigned_posts:
                slot = round_to_nearest_5(current)
                if slot not in log_blocked_times:
                    post_times[post_num] = slot
                    assigned_slots.add(slot)
                else:
                    post_times[post_num] = None
                current += timedelta(minutes=step or 1)

        # Merge assigned + logged blocked
        blocked_times = set(log_blocked_times) | assigned_slots

        # Free slots for UI
        time_slots_for_frontend = []
        for slot in ui_grid:
            time_slots_for_frontend.append({
                "time": slot.strftime("%Y-%m-%d %H:%M"),
                "status": "blocked" if slot in blocked_times else "free"
            })

        # Send / preview
        preview_posts = []
        scheduled_count = 0
        failed_count = 0
        for post_num in all_post_nums:
            scheduled_time = post_times.get(post_num)
            image_path = image_map.get(post_num)
            post_data = text_posts.get(post_num, {})
            post_text = post_data.get('text') if isinstance(post_data, dict) else post_data
            category = post_data.get('category') if isinstance(post_data, dict) else None

            if not scheduled_time:
                preview_posts.append({
                    "post": post_num,
                    "image": os.path.basename(image_path) if image_path else None,
                    "text": post_text,
                    "category": category,
                    "time": "N/A",
                    "status": "skipped",
                    "error": "No available slot within window"
                })
                continue

            schedule_time = to_utc_naive(scheduled_time)
            try:
                await send_telegram_message(
                    image_path=image_map.get(post_num),
                    post_text=post_text,
                    post_number=post_num,
                    category=category,
                    schedule_time=schedule_time
                )
                scheduled_count += 1
                status = "scheduled"
                error = None
                print(f"✅ Scheduled post {post_num} at {scheduled_time}")
            except Exception as e:
                status = "failed"
                error = str(e)
                failed_count += 1
                print(f"❌ Failed to schedule post {post_num}: {e}")

            preview_posts.append({
                "post": post_num,
                "image": os.path.basename(image_path) if image_path else None,
                "text": post_text,
                "category": category,
                "time": scheduled_time.strftime("%H:%M") if scheduled_time else "N/A",
                "status": status,
                "error": error
            })

        return JSONResponse({
            "status": f"Scheduled {scheduled_count} posts between {start_time} and {end_time}, {failed_count} failed",
            "posts": preview_posts,
            "scheduled": scheduled_count,
            "failed": failed_count,
            "total": len(all_post_nums),
            "time_slots": time_slots_for_frontend  # <== use the new labeled list
        })


    except Exception as e:
        print(f"Error in /api/auto-schedule: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error"})

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
