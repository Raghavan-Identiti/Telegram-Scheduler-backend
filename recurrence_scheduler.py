# recurrence_scheduler.py
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime, timedelta
from enum import Enum
import pytz
import os
import re
import json
from telegram_utils import send_telegram_message, CHANNELS, get_blocked_times_from_sheet

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
    """Round time to the nearest 5-minute mark"""
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

    if days_ahead < 0 or (days_ahead == 0 and (base_date.hour > time_slot.hour or
                      (base_date.hour == time_slot.hour and base_date.minute >= time_slot.minute))):
        days_ahead += 7

    next_date = base_date + timedelta(days=days_ahead)
    return next_date.replace(hour=time_slot.hour, minute=time_slot.minute, second=0, microsecond=0)

def generate_schedule_dates(
    recurrence_type: RecurrenceType,
    daily_recurrence: Optional[DailyRecurrence],
    weekly_recurrence: Optional[WeeklyRecurrence],
    max_occurrences: Optional[int] = None
) -> List[datetime]:
    """
    Generate schedule dates with optional max occurrences limit
    """
    schedule_times: List[datetime] = []

    if recurrence_type == RecurrenceType.DAILY:
        if not daily_recurrence:
            return []
        start_date = datetime.strptime(daily_recurrence.start_date, "%Y-%m-%d")
        start_date = ist.localize(start_date)

        if daily_recurrence.end_date:
            end_date = datetime.strptime(daily_recurrence.end_date, "%Y-%m-%d")
            end_date = ist.localize(end_date).replace(hour=23, minute=59)
        else:
            # Default: 90 days if no end date
            end_date = start_date + timedelta(days=90)

        current_date = start_date
        occurrence_count = 0
        
        while current_date <= end_date:
            for time_slot in daily_recurrence.times:
                if max_occurrences and occurrence_count >= max_occurrences:
                    return sorted(schedule_times)
                
                schedule_time = current_date.replace(
                    hour=time_slot.hour,
                    minute=time_slot.minute,
                    second=0,
                    microsecond=0
                )
                if schedule_time > datetime.now(ist):
                    schedule_times.append(schedule_time)
                    occurrence_count += 1
            
            current_date += timedelta(days=1)

    elif recurrence_type == RecurrenceType.WEEKLY:
        if not weekly_recurrence:
            return []

        if weekly_recurrence.start_date:
            start_date = datetime.strptime(weekly_recurrence.start_date, "%Y-%m-%d")
            start_date = ist.localize(start_date)
        else:
            start_date = datetime.now(ist)

        if weekly_recurrence.end_date:
            end_date = datetime.strptime(weekly_recurrence.end_date, "%Y-%m-%d")
            end_date = ist.localize(end_date).replace(hour=23, minute=59)
        else:
            end_date = start_date + timedelta(days=90)

        occurrence_count = 0
        
        for day in weekly_recurrence.days:
            day_times = weekly_recurrence.time_per_day.get(day.value, [])
            target_weekday = day_to_number(day)

            for time_slot_dict in day_times:
                if isinstance(time_slot_dict, dict):
                    time_slot = TimeSlot(**time_slot_dict)
                else:
                    time_slot = time_slot_dict

                current_date = get_next_occurrence(start_date, target_weekday, time_slot)
                
                while current_date <= end_date:
                    if max_occurrences and occurrence_count >= max_occurrences:
                        return sorted(schedule_times)
                    
                    if current_date > datetime.now(ist):
                        schedule_times.append(current_date)
                        occurrence_count += 1
                    
                    current_date += timedelta(weeks=1)

    return sorted(schedule_times)

def to_utc_naive(dt: datetime) -> datetime:
    return dt.astimezone(pytz.UTC).replace(tzinfo=None)

@router.post("/recurring-schedule", response_model=RecurringScheduleResponse)
async def create_recurring_schedule_from_files(
    text_files: List[UploadFile] = File([]),
    image_files: List[UploadFile] = File([]),
    recurrence_type: str = Form(...),
    channels: str = Form(...),
    category: str = Form(None),
    daily_times: str = Form(None),
    weekly_config: str = Form(None),
    start_date: str = Form(...),
    end_date: str = Form(None),
    max_occurrences: int = Form(None),
    skip_blocked_times: bool = Form(True)
):
    """
    Create recurring schedule from uploaded files.
    Uses Telegram's native scheduler.
    Supports "after X occurrences" limit.
    """
    try:
        # Parse channels
        selected_channels = json.loads(channels) if channels else []
        if not selected_channels:
            raise HTTPException(status_code=400, detail="Please select at least one channel")
        
        valid_channels = [ch for ch in selected_channels if ch in CHANNELS]
        if not valid_channels:
            raise HTTPException(status_code=400, detail="No valid channels selected")
        
        # Setup upload directory
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        for f in os.listdir(UPLOAD_DIR):
            os.remove(os.path.join(UPLOAD_DIR, f))
        
        # Process text files
        text_contents = []
        for file in text_files:
            filepath = os.path.join(UPLOAD_DIR, file.filename)
            with open(filepath, "wb") as f:
                f.write(await file.read())
            with open(filepath, 'r', encoding='utf-8') as f:
                text_contents.append(f.read())
        
        # Extract posts from text
        from telegram_utils import extract_all_posts_from_texts
        text_posts = extract_all_posts_from_texts(text_contents)
        
        # Process images and save to disk
        image_map = {}
        for file in image_files:
            fname = file.filename.lower()
            filepath = os.path.join(UPLOAD_DIR, file.filename)
            with open(filepath, "wb") as f:
                f.write(await file.read())
            
            match = re.search(r'(?:\*{0,2})\s*post\s*[-_\s]*(\d+)', fname, re.IGNORECASE)
            if match:
                post_num = int(match.group(1))
                image_map[post_num] = filepath
                print(f"🎯 Mapped image {file.filename} to post {post_num}: {filepath}")
        
        # Get template post
        all_post_nums = sorted(set(text_posts.keys()) | set(image_map.keys()))
        if not all_post_nums:
            raise HTTPException(status_code=400, detail="No valid posts detected")
        
        template_post_num = None
        template_text = ""
        template_category = category
        template_image = None
        
        for post_num in all_post_nums:
            if post_num in text_posts:
                post_data = text_posts[post_num]
                if isinstance(post_data, dict):
                    template_text = post_data.get('text', '')
                    if not template_category:
                        template_category = post_data.get('category')
                else:
                    template_text = post_data
                
                if template_text:
                    template_post_num = post_num
                    template_image = image_map.get(post_num)
                    break
        
        if not template_text:
            raise HTTPException(status_code=400, detail="At least one post must have text content")
        
        print(f"📝 Template: Post {template_post_num}")
        print(f"🖼️ Template Image: {template_image}")
        print(f"📄 Template Text Length: {len(template_text)}")
        
        # Parse recurrence settings
        daily_recurrence_obj = None
        weekly_recurrence_obj = None
        
        if recurrence_type == "daily":
            if not daily_times:
                raise HTTPException(status_code=400, detail="Daily times required")
            
            times_data = json.loads(daily_times)
            daily_recurrence_obj = DailyRecurrence(
                start_date=start_date,
                end_date=end_date,
                times=[TimeSlot(**t) for t in times_data]
            )
        
        elif recurrence_type == "weekly":
            if not weekly_config:
                raise HTTPException(status_code=400, detail="Weekly configuration required")
            
            weekly_data = json.loads(weekly_config)
            weekly_recurrence_obj = WeeklyRecurrence(
                days=[DayOfWeek(d) for d in weekly_data['days']],
                time_per_day=weekly_data['time_per_day'],
                start_date=start_date,
                end_date=end_date
            )
        
        # Generate schedule times with max occurrences limit
        schedule_times = generate_schedule_dates(
            RecurrenceType(recurrence_type),
            daily_recurrence_obj,
            weekly_recurrence_obj,
            max_occurrences=max_occurrences
        )
        
        if not schedule_times:
            raise HTTPException(status_code=400, detail="No valid schedule times generated")
        
        print(f"📅 Generated {len(schedule_times)} schedule times")
        
        # Get blocked times
        blocked_times_ist = set()
        if skip_blocked_times:
            try:
                sheet_blocked_times_naive = get_blocked_times_from_sheet(valid_channels)
                for naive_dt in sheet_blocked_times_naive:
                    if naive_dt.tzinfo is None:
                        ist_dt = ist.localize(naive_dt)
                    else:
                        ist_dt = naive_dt.astimezone(ist)
                    blocked_times_ist.add(round_to_nearest_5(ist_dt))
                print(f"🚫 Found {len(blocked_times_ist)} blocked time slots")
            except Exception as e:
                print(f"⚠️ Could not fetch blocked times: {e}")
        
        # Schedule posts
        total_scheduled = 0
        total_failed = 0
        total_skipped = 0
        blocked_count = 0
        next_executions = []
        
        schedule_id = f"recurring_{int(datetime.now().timestamp())}"
        
        for channel_id in valid_channels:
            channel_info = CHANNELS[channel_id]
            channel_username = channel_info['username']
            
            for idx, schedule_time in enumerate(schedule_times):
                # Check if blocked
                if skip_blocked_times and round_to_nearest_5(schedule_time) in blocked_times_ist:
                    print(f"⏭️ Skipping blocked time: {schedule_time}")
                    total_skipped += 1
                    blocked_count += 1
                    continue
                
                schedule_time_utc = to_utc_naive(schedule_time)
                
                try:
                    # Send to Telegram with image
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
                    
                    if len(next_executions) < 10:
                        next_executions.append({
                            "channel": f"@{channel_username}",
                            "time": schedule_time.strftime("%Y-%m-%d %H:%M:%S"),
                            "type": recurrence_type.capitalize(),
                            "schedule": f"Post #{idx + 1}"
                        })
                    
                    print(f"✅ Scheduled post #{idx} to @{channel_username} at {schedule_time}")
                
                except Exception as e:
                    print(f"❌ Failed to schedule to @{channel_username} at {schedule_time}: {e}")
                    total_failed += 1
        
        return RecurringScheduleResponse(
            schedule_id=schedule_id,
            message=f"✅ Scheduled {total_scheduled} posts across {len(valid_channels)} channels",
            total_scheduled=total_scheduled,
            total_failed=total_failed,
            total_skipped=total_skipped,
            next_executions=next_executions,
            channels=[f"@{CHANNELS[ch]['username']}" for ch in valid_channels],
            blocked_times_skipped=blocked_count
        )
        
    except Exception as e:
        print(f"❌ Error creating recurring schedule: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))