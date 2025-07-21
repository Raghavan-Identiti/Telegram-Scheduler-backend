from fastapi import FastAPI, UploadFile, File, BackgroundTasks, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from scheduler import schedule_message
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from utils import extract_post_content
import os
from typing import List
import shutil
import re
from datetime import datetime, timedelta
import json

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # use ['https://your-render-url.onrender.com'] in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Static Files (logs, uploads)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

frontend_path = os.path.join(os.path.dirname(__file__), "out")
app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")

# Only one log mount
app.mount("/logs", StaticFiles(directory="logs"), name="logs")


@app.post("/bulk-schedule")
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
                if match:
                    post_num = int(match.group(1))
                    image_files[post_num] = file_path

        if not text_paths:
            return JSONResponse(status_code=400, content={"error": "No .txt files provided"})

        if not image_files:
            return JSONResponse(status_code=400, content={"error": "No image files matched 'postX'"})

        # Collect all unique post numbers from both images and .txt files
        all_post_nums = set(image_files.keys())
        txt_content = ""
        for path in text_paths:
            with open(path, 'r', encoding='utf-8') as f:
                txt_content += f.read()

        matches = re.findall(r'POST\s*(\d+)\s*CONTENT.*?END OF POST\s*\1', txt_content, flags=re.IGNORECASE | re.DOTALL)
        all_post_nums.update(int(n) for n in matches)

        # Schedule each post with the full context of txt files
        # base_time = datetime.fromisoformat(scheduled_time) if scheduled_time else datetime.now()

        for post_num in sorted(all_post_nums):
            time_str = post_time_map.get(f"post{post_num}.jpg")  # Fix: key format match
            if not time_str:
                continue  # Skip if no schedule provided

            background_tasks.add_task(
                schedule_message,
                image_files.get(post_num),
                text_paths,
                time_str,
                post_num
            )


        return JSONResponse({"status": f"{len(all_post_nums)} posts scheduled successfully"})

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    
app.mount("/logs", StaticFiles(directory="logs"), name="logs")


