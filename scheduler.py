from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
from utils import send_telegram_message
from pytz import timezone

scheduler = AsyncIOScheduler()
if not scheduler.running:
    scheduler.start()

def schedule_message(image_path: str, text_paths: str, time_str: str, post_number: int = 1):
    run_time = timezone("Asia/Kolkata").localize(datetime.fromisoformat(time_str))

    scheduler.add_job(
        send_telegram_message,
        'date',
        run_date=run_time,
        args=[image_path, text_paths, post_number],
        kwargs={},  # optional
        misfire_grace_time=30  # optional grace period for late jobs
    )
 