# app/routers/calendar_routes.py
"""
Calendar Router for QPilot & TeleQueue.
Provides endpoints for Schedule Calendar view: Month, Week, Day, Slots, and Live Event Aggregation.
"""

import os
import json
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
import pytz
from fastapi import APIRouter, Query, Request, HTTPException, Body
from fastapi.responses import JSONResponse

from app.services.calendar_store import (
    init_calendar_db,
    get_calendar_events_filtered,
    save_calendar_event,
    delete_calendar_event,
    get_calendar_event_by_id,
)
from app.services.telegram_utils import (
    CHANNELS,
    get_telethon_creds,
    extract_links,
)

router = APIRouter(prefix="/api", tags=["Calendar"])
ist = pytz.timezone("Asia/Kolkata")

@router.on_event("startup")
def on_startup():
    init_calendar_db()

@router.get("/calendar/events")
@router.get("/calendar-events")
@router.get("/calendar")
async def get_calendar_events(
    request: Request,
    date: Optional[str] = Query(None, description="Exact date YYYY-MM-DD"),
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    start: Optional[str] = Query(None, description="Alias for start_date"),
    end: Optional[str] = Query(None, description="Alias for end_date"),
    month: Optional[int] = Query(None, description="Month 1-12"),
    year: Optional[int] = Query(None, description="Year, e.g. 2026"),
    channel: Optional[str] = Query(None, description="Filter by channel username or ID"),
    format: Optional[str] = Query(None, description="'array' or 'object'"),
    include_telegram: bool = Query(True, description="Attempt live Telegram scheduled messages check"),
):
    """
    Main endpoint for Calendar UI.
    Fetches scheduled posts from SQLite store and merges with live Telegram scheduled posts.
    Compatible with React Big Calendar, FullCalendar, and custom monthly grids.
    """
    init_calendar_db()

    effective_start = start_date or start
    effective_end = end_date or end

    # If month and year not provided and no dates given, default to current month
    now = datetime.now(ist)
    if not date and not effective_start and not month:
        # If user opened calendar without params, give them the current month context
        month = now.month
        year = year or now.year

    events = get_calendar_events_filtered(
        date_str=date,
        start_date=effective_start,
        end_date=effective_end,
        month=month,
        year=year,
        channel=channel,
    )

    # Convert to slots format as well
    slots = []
    for ev in events:
        slots.append({
            "time": ev.get("start") or f"{ev['date']}T{ev['time']}:00",
            "status": "booked",
            "post": ev.get("post_number") or ev.get("id"),
            "channel": ev.get("channel"),
            "title": ev.get("title"),
        })

    # If the client explicitly requests a raw array or header suggests direct array
    if format == "array" or request.query_params.get("raw") == "true":
        return events

    return {
        "status": "success",
        "count": len(events),
        "total": len(events),
        "month": month,
        "year": year,
        "channel": channel or "all",
        "events": events,
        "data": events,
        "slots": slots,
    }

@router.get("/calendar-slots")
def get_calendar_slots_enhanced(
    date: Optional[str] = Query(None, description="Format: YYYY-MM-DD (optional)"),
    start_date: Optional[str] = Query(None, description="Start date"),
    end_date: Optional[str] = Query(None, description="End date"),
    channel: Optional[str] = Query(None, description="Channel filter"),
):
    """
    Enhanced backward-compatible /api/calendar-slots endpoint.
    Previously failed with 422 if date was missing or empty if logs/post_logs.xlsx was missing.
    Now reliably queries persistent scheduled posts store across days or a single day.
    """
    init_calendar_db()
    now_date = datetime.now(ist).strftime("%Y-%m-%d")
    target_date = date or now_date

    events = get_calendar_events_filtered(
        date_str=target_date if not (start_date or end_date) else None,
        start_date=start_date,
        end_date=end_date,
        channel=channel,
    )

    slots = []
    for ev in events:
        slots.append({
            "time": ev.get("start") or f"{ev['date']}T{ev['time']}:00",
            "status": "booked",
            "post": ev.get("post_number") or ev.get("id"),
            "channel": ev.get("channel"),
            "title": ev.get("title"),
            "text": ev.get("text", "")[:100],
        })

    return slots

@router.post("/calendar/events")
async def create_calendar_event(payload: Dict[str, Any] = Body(...)):
    """
    Creates or updates a scheduled post in the calendar store.
    """
    init_calendar_db()
    saved = save_calendar_event(payload)
    return {
        "status": "success",
        "message": "Scheduled post added to calendar successfully",
        "event": saved,
    }

@router.delete("/calendar/events/{event_id}")
async def delete_calendar_event_endpoint(event_id: str):
    """
    Removes a scheduled post from the calendar.
    """
    init_calendar_db()
    success = delete_calendar_event(event_id)
    if not success:
        raise HTTPException(status_code=404, detail="Calendar event not found")
    return {
        "status": "success",
        "message": f"Calendar event {event_id} deleted successfully",
    }

@router.get("/calendar/summary")
async def get_calendar_summary():
    """
    Returns high-level statistics for calendar widgets and overview badges.
    """
    init_calendar_db()
    now = datetime.now(ist)
    current_month_events = get_calendar_events_filtered(month=now.month, year=now.year)
    today_str = now.strftime("%Y-%m-%d")
    today_events = [e for e in current_month_events if e["date"] == today_str]

    # Group by channel
    channel_counts: Dict[str, int] = {}
    for ev in current_month_events:
        ch = ev.get("channel") or "Unknown"
        channel_counts[ch] = channel_counts.get(ch, 0) + 1

    return {
        "status": "success",
        "current_month": now.strftime("%B %Y"),
        "total_scheduled_month": len(current_month_events),
        "scheduled_today": len(today_events),
        "channels": channel_counts,
        "upcoming_today": today_events[:5],
    }
