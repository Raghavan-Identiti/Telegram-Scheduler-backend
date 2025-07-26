# ✅ scheduler.py — Updated to fetch specific post text from file paths
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from datetime import datetime
import asyncio
import os
import re

scheduler = AsyncIOScheduler()
scheduler.start()

def schedule_message(image_path: str | None, text: str | None, time_str: str, post_number: int, category: str | None = None ):
    from telegram_utils import send_telegram_message
    
    if isinstance(time_str, datetime):
        run_time = time_str
    else:
        run_time = datetime.fromisoformat(time_str)

    print(f"📆 Scheduling Post {post_number} at {run_time}")
    print(f"    Image: {image_path}")
    print(f"    Text: {text}")
    print(f"    Category: {category}")

    scheduler.add_job(
        send_telegram_message,
        trigger=DateTrigger(run_date=run_time),
        args=[image_path, text, post_number, category],
        id=f"post_{post_number}_{run_time.timestamp()}"
    )

