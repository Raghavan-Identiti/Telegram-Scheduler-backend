# app/routers/recurrence_scheduler.py
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime, timedelta
from enum import Enum
import pytz
import os
import re
import json
from app.services.telegram_utils import send_telegram_message, CHANNELS, get_blocked_times_from_sheet
from app.services.calendar_store import save_calendar_event

router = APIRouter()
ist = pytz.timezone("Asia/Kolkata")
UPLOAD_DIR = "uploads"

class RecurrenceType(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"

class DayOfWeek(str, Enum):
    MONDAY = "M"
    TUESDAY = "T"
    WEDNESDAY = "W"
    THURSDAY = "TH"
    FRIDAY = "F"
    SATURDAY = "S"
    SUNDAY = "SU"

class TimeSlot(BaseModel):
    hour: int = Field(..., ge=0, le=23)
    minute: int = Field(..., ge=0, le=59)

class DailyRecurrence(BaseModel):
    start_date: str
    end_date: Optional[str] = None
    times: List[TimeSlot]

class WeeklyRecurrence(BaseModel):
    days: List[DayOfWeek]
    time_per_day: Dict[str, List[TimeSlot]]
    start_date: Optional[str] = None
    end_date: Optional[str] = None

class RecurringScheduleResponse(BaseModel):
    schedule_id: str
    message: str
    total_scheduled: int
    total_failed: int
    total_skipped: int
    next_executions: List[Dict[str, str]]
    channels: List[str]
    blocked_times_skipped: int

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

def day_to_number(day: DayOfWeek) -> int:
    mapping = {
        DayOfWeek.MONDAY: 0,
        DayOfWeek.TUESDAY: 1,
        DayOfWeek.WEDNESDAY: 2,
        DayOfWeek.THURSDAY: 3,
        DayOfWeek.FRIDAY: 4,
        DayOfWeek.SATURDAY: 5,
        DayOfWeek.SUNDAY: 6
    }
    return mapping[day]

def get_next_occurrence(base_date: datetime, target_day: int, time_slot: TimeSlot) -> datetime:
    current_weekday = base_date.weekday()
    days_ahead = target_day - current_weekday
    if days_ahead < 0 or (days_ahead == 0 and (base_date.hour > time_slot.hour or (base_date.hour == time_slot.hour and base_date.minute >= time_slot.minute))):
        days_ahead += 7
    next_date = base_date + timedelta(days=days_ahead)
    return next_date.replace(hour=time_slot.hour, minute=time_slot.minute, second=0, microsecond=0)

def generate_schedule_dates(
    recurrence_type: RecurrenceType,
    daily_recurrence: Optional[DailyRecurrence],
    weekly_recurrence: Optional[WeeklyRecurrence],
    max_occurrences: Optional[int] = None
) -> List[datetime]:
    schedule_times: List[datetime] = []
    if recurrence_type == RecurrenceType.DAILY:
        if not daily_recurrence:
            return []
        start_date = ist.localize(datetime.strptime(daily_recurrence.start_date, "%Y-%m-%d"))
        if daily_recurrence.end_date:
            end_date = ist.localize(datetime.strptime(daily_recurrence.end_date, "%Y-%m-%d")).replace(hour=23, minute=59)
        else:
            end_date = start_date + timedelta(days=90)

        current_date = start_date
        occurrence_count = 0
        while current_date <= end_date:
            for time_slot in daily_recurrence.times:
                if max_occurrences and occurrence_count >= max_occurrences:
                    return sorted(schedule_times)
                schedule_time = current_date.replace(hour=time_slot.hour, minute=time_slot.minute, second=0, microsecond=0)
                if schedule_time > datetime.now(ist):
                    schedule_times.append(schedule_time)
                    occurrence_count += 1
            current_date += timedelta(days=1)

    elif recurrence_type == RecurrenceType.WEEKLY:
        if not weekly_recurrence:
            return []
        start_date = ist.localize(datetime.strptime(weekly_recurrence.start_date, "%Y-%m-%d")) if weekly_recurrence.start_date else datetime.now(ist)
        end_date = ist.localize(datetime.strptime(weekly_recurrence.end_date, "%Y-%m-%d")).replace(hour=23, minute=59) if weekly_recurrence.end_date else start_date + timedelta(days=90)
        occurrence_count = 0
        for day in weekly_recurrence.days:
            day_times = weekly_recurrence.time_per_day.get(day.value, [])
            target_weekday = day_to_number(day)
            for time_slot_dict in day_times:
                time_slot = TimeSlot(**time_slot_dict) if isinstance(time_slot_dict, dict) else time_slot_dict
                current_date = get_next_occurrence(start_date, target_weekday, time_slot)
                while current_date <= end_date:
                    if max_occurrences and occurrence_count >= max_occurrences:
                        return sorted(schedule_times)
                    if current_date > datetime.now(ist):
                        schedule_times.append(current_date)
                        occurrence_count += 1
                    current_date += timedelta(weeks=1)

    return sorted(schedule_times)

@router.post("/recurring-schedule", response_model=RecurringScheduleResponse)
async def create_recurring_schedule_from_files(
    text_files: List[UploadFile] = File([]),
    image_files: List[UploadFile] = File([]),
    recurrence_type: str = Form(...),
    channels: str = Form(...),
    category: Optional[str] = Form(None),
    daily_times: Optional[str] = Form(None),
    weekly_config: Optional[str] = Form(None),
    start_date: str = Form(...),
    end_date: Optional[str] = Form(None),
    max_occurrences: Optional[int] = Form(None),
    skip_blocked_times: bool = Form(True)
):
    selected_channels = json.loads(channels) if channels else []
    if not selected_channels:
        raise HTTPException(status_code=400, detail="Please select at least one channel")
    valid_channels = [ch for ch in selected_channels if ch in CHANNELS]
    if not valid_channels:
        raise HTTPException(status_code=400, detail="No valid channels selected")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    text_contents = []
    for file in text_files:
        filepath = os.path.join(UPLOAD_DIR, file.filename)
        with open(filepath, "wb") as f:
            f.write(await file.read())
        with open(filepath, 'r', encoding='utf-8') as f:
            text_contents.append(f.read())

    from app.services.telegram_utils import extract_all_posts_from_texts
    text_posts = extract_all_posts_from_texts(text_contents)

    image_map = {}
    for file in image_files:
        fname = file.filename.lower()
        filepath = os.path.join(UPLOAD_DIR, file.filename)
        with open(filepath, "wb") as f:
            f.write(await file.read())
        match = re.search(r'(?:\*{0,2})\s*post\s*[-_\s]*(\d+)', fname, re.IGNORECASE)
        if match:
            image_map[int(match.group(1))] = filepath

    all_post_nums = sorted(set(text_posts.keys()) | set(image_map.keys()))
    if not all_post_nums:
        raise HTTPException(status_code=400, detail="No valid posts detected")

    template_text = ""
    template_image = None
    template_category = category
    for post_num in all_post_nums:
        if post_num in text_posts:
            post_data = text_posts[post_num]
            template_text = post_data.get('text', '') if isinstance(post_data, dict) else post_data
            if not template_category and isinstance(post_data, dict):
                template_category = post_data.get('category')
            if template_text:
                template_image = image_map.get(post_num)
                break

    if not template_text:
        raise HTTPException(status_code=400, detail="At least one post must have text content")

    daily_obj = DailyRecurrence(start_date=start_date, end_date=end_date, times=[TimeSlot(**t) for t in json.loads(daily_times)]) if recurrence_type == "daily" and daily_times else None
    weekly_obj = WeeklyRecurrence(days=[DayOfWeek(d) for d in json.loads(weekly_config)['days']], time_per_day=json.loads(weekly_config)['time_per_day'], start_date=start_date, end_date=end_date) if recurrence_type == "weekly" and weekly_config else None

    schedule_times = generate_schedule_dates(RecurrenceType(recurrence_type), daily_obj, weekly_obj, max_occurrences=max_occurrences)
    schedule_id = f"recurring_{int(datetime.now().timestamp())}"
    total_scheduled = 0
    next_executions = []

    for channel_id in valid_channels:
        channel_username = CHANNELS[channel_id]['username']
        for idx, st in enumerate(schedule_times):
            schedule_time_utc = st.astimezone(pytz.UTC).replace(tzinfo=None)
            try:
                await send_telegram_message(
                    image_path=template_image,
                    post_text=template_text,
                    post_number=f"{schedule_id}_{idx}",
                    category=template_category or "Recurring",
                    schedule_time=schedule_time_utc,
                    channel_username=channel_username,
                    channel_id=channel_id
                )
                total_scheduled += 1
                try:
                    save_calendar_event({
                        "id": f"post_rec_{schedule_id}_{channel_username}_{idx}",
                        "post_number": f"{idx + 1}",
                        "channel": channel_username,
                        "channel_name": CHANNELS.get(channel_id, {}).get("sheet_name", channel_username),
                        "channel_type": "telegram",
                        "title": f"Recurring #{idx + 1} (@{channel_username})",
                        "text": template_text or "",
                        "category": template_category or "Recurring",
                        "scheduled_time": st.isoformat(),
                        "date": st.strftime("%Y-%m-%d"),
                        "time": st.strftime("%H:%M"),
                        "status": "scheduled",
                        "image_name": os.path.basename(template_image) if template_image else None,
                        "source": "recurring_scheduler"
                    })
                except Exception as e_cal:
                    print(f"⚠️ Recurring calendar save error: {e_cal}")

                if len(next_executions) < 10:
                    next_executions.append({
                        "channel": f"@{channel_username}",
                        "time": st.strftime("%Y-%m-%d %H:%M:%S"),
                        "type": recurrence_type.capitalize(),
                        "schedule": f"Post #{idx + 1}"
                    })
            except Exception as e:
                print(f"Error scheduling recurring post: {e}")

    return RecurringScheduleResponse(
        schedule_id=schedule_id,
        message=f"✅ Scheduled {total_scheduled} recurring posts",
        total_scheduled=total_scheduled,
        total_failed=0,
        total_skipped=0,
        next_executions=next_executions,
        channels=[f"@{CHANNELS[ch]['username']}" for ch in valid_channels],
        blocked_times_skipped=0
    )
