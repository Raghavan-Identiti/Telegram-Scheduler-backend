# main.py
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from scheduler import schedule_message
from fastapi.staticfiles import StaticFiles
import os, re, json
from typing import List
from datetime import datetime, timezone
from logs_api import router as logs_router
from telegram_utils import extract_all_posts_from_texts, send_telegram_message
import uuid
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
            schedule_time = datetime.fromisoformat(time_str)
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

def to_utc_naive(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(tzinfo=None)

@app.post("/api/auto-schedule")
async def auto_schedule(
    background_tasks: BackgroundTasks,
    text_files: List[UploadFile] = File([]),
    image_files: List[UploadFile] = File([]),
    start_time: str = Form(...),
    end_time: str = Form(...),
    times: List[str] = Form(default=[]),
    send_image_only: bool = Form(default=False)
):
    # Clear upload directory
    for f in os.listdir(UPLOAD_DIR):
        os.remove(os.path.join(UPLOAD_DIR, f))

    image_map = {}  # {post_number: image_path}
    text_contents = []
    text_posts = {}  # {post_number: content}

    # Save and process text files
    for file in text_files:
        filepath = os.path.join(UPLOAD_DIR, file.filename)
        with open(filepath, "wb") as f:
            f.write(await file.read())

        with open(filepath, 'r', encoding='utf-8') as f:
            text = f.read()
            text_contents.append(text)

    # Extract posts from all text files
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

    # Calculate or override timings
    # Parse start and end date-times once
    start_dt = datetime.fromisoformat(start_time)
    end_dt = datetime.fromisoformat(end_time)

    post_times = {}

    if times:
        for entry in times:
            if '|' in entry:
                post_str, time_str = entry.split('|')
                try:
                    post_num = int(post_str.strip())
                    # Combine the user-edited time (e.g., "19:53") with start date
                    full_time = f"{start_dt.date()}T{time_str.strip()}"
                    post_times[post_num] = datetime.fromisoformat(full_time)
                except Exception as e:
                    print(f"Invalid time format: {entry} - {e}")
                    continue
    else:
        # Auto-generate timings if not provided
        total_posts = len(all_post_nums)
        if total_posts == 1:
            intervals = [start_dt]
        else:
            interval = (end_dt - start_dt) / (total_posts - 1)
            intervals = [start_dt + i * interval for i in range(total_posts)]
        for i, post_num in enumerate(all_post_nums):
            post_times[post_num] = intervals[i]

    # Create preview and schedule
    preview_posts = []
    for post_num in all_post_nums:
        time_str = post_times.get(post_num)
        image_path = image_map.get(post_num)
        post_data = text_posts.get(post_num, {})
        post_text = post_data.get('text') if isinstance(post_data, dict) else post_data
        category = post_data.get('category') if isinstance(post_data, dict) else None

        

        local_time = post_times.get(post_num)
        schedule_time = to_utc_naive(local_time) if local_time else None
        try:
            await send_telegram_message(
                image_path=image_map.get(post_num),
                post_text=post_text,
                post_number=post_num,
                category=category,
                schedule_time=schedule_time
            )
            status = "scheduled"
            error = None
        except Exception as e:
            print(f"❌ Failed to schedule post {post_num}: {e}")
            status = "failed"
            error = str(e)
        
        preview_post = {
            "post": post_num,
            "image": os.path.basename(image_path) if image_path else None,
            "text": post_text,
            "category": category,
            "time": time_str.strftime("%H:%M") if isinstance(time_str, datetime) else time_str,
            "status": status,
            "error": error
        }
        preview_posts.append(preview_post)
    scheduled_count = len([p for p in preview_posts if p["status"] == "scheduled"])
    failed_count = len([p for p in preview_posts if p["status"] == "failed"])
    return JSONResponse({
        "status": f"Scheduled {scheduled_count} posts between {start_time} and {end_time}, {failed_count} failed",
        "posts": preview_posts,
        "scheduled": scheduled_count,
        "failed": failed_count,
        "total": len(all_post_nums)
    })
