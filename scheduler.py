
### ✅ scheduler.py
# Simply forwards args to telegram_utils.send_telegram_message
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from datetime import datetime
import os
from telegram_utils import send_telegram_message

scheduler = AsyncIOScheduler()
scheduler.start()

def schedule_message(image_path: str | None, text: str | None, time_str: str, post_number: int, category: str | None = None ):
    run_time = datetime.fromisoformat(time_str) if isinstance(time_str, str) else time_str
    scheduler.add_job(
    send_telegram_message,
    trigger=DateTrigger(run_date=run_time),
    args=[
        image_path,
        text,
        post_number,
        category,
        run_time
    ],
    id=f"post_{post_number}_{run_time.timestamp()}"
)

