# app/services/calendar_store.py
"""
Calendar and Scheduled Posts Store.
Provides persistent storage, multi-source aggregation (Telegram queue, Google Sheets, WhatsApp DB, local schedules),
and date-range filtering for the Schedule Calendar in QPilot and TeleQueue.
"""

import os
import json
import sqlite3
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
import pytz

ist = pytz.timezone("Asia/Kolkata")
DB_DIR = "data"
DB_PATH = os.path.join(DB_DIR, "calendar_posts.db")

def get_db_connection():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_calendar_db():
    """Initializes the calendar SQLite database and tables."""
    conn = get_db_connection()
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS calendar_events (
                id TEXT PRIMARY KEY,
                post_number TEXT,
                channel TEXT NOT NULL,
                channel_name TEXT,
                channel_type TEXT DEFAULT 'telegram',
                title TEXT NOT NULL,
                text TEXT,
                category TEXT,
                scheduled_time TEXT NOT NULL,
                date_str TEXT NOT NULL,
                time_str TEXT NOT NULL,
                status TEXT DEFAULT 'scheduled',
                image_name TEXT,
                image_url TEXT,
                links TEXT,
                source TEXT DEFAULT 'auto_scheduler',
                views INTEGER DEFAULT 0,
                telegram_clicks INTEGER DEFAULT 0,
                whatsapp_clicks INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cal_date ON calendar_events(date_str)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cal_channel ON calendar_events(channel)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cal_status ON calendar_events(status)")
    conn.close()
    seed_initial_calendar_events_if_empty()

def seed_initial_calendar_events_if_empty():
    """
    Seeds initial scheduled posts across channels so the calendar has rich,
    interactive data immediately rather than being blank.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM calendar_events")
    count = cursor.fetchone()[0]
    if count > 0:
        conn.close()
        return

    now_ist = datetime.now(ist)
    # Generate seed events for today, tomorrow, and surrounding days
    seeds = [
        {
            "id": "post_seed_cal_1",
            "post_number": "1",
            "channel": "amazonindiaassociates",
            "channel_name": "Amazon India Associates",
            "channel_type": "telegram",
            "title": "⏰ 8PM DEALS 📣 Limited Time Electronics",
            "text": "⏰ 8PM DEALS 📣 LIMITED PERIOD ONLY\n\n🔥 Unmissable deals on Top Smart TVs & Audio from 8PM till midnight.\n\n👉🏻 amzaff.in/1ZQZf7G",
            "category": "Deals",
            "offset_days": 0,
            "hour": 14,
            "minute": 30,
            "status": "scheduled",
            "image_name": "@amazonindiaassociates_13756.jpg",
            "links": ["https://amzaff.in/1ZQZf7G"],
        },
        {
            "id": "post_seed_cal_2",
            "post_number": "2",
            "channel": "Amazon_Associates_FashionBeauty",
            "channel_name": "Fashion & Beauty",
            "channel_type": "telegram",
            "title": "✨ FASHION TRENDS - 60% OFF Top Footwear",
            "text": "✨ FASHION TRENDS OF THE WEEK\n\nGet up to 60% off on top branded footwear and accessories.\n\nShop here: amzaff.in/sd53Qad",
            "category": "Fashion",
            "offset_days": 0,
            "hour": 16,
            "minute": 0,
            "status": "scheduled",
            "image_name": "@amazonindiaassociates_13758.jpg",
            "links": ["https://amzaff.in/sd53Qad"],
        },
        {
            "id": "post_seed_cal_3",
            "post_number": "3",
            "channel": "Amazon_Associates_HomeKitchen",
            "channel_name": "Home & Kitchen",
            "channel_type": "telegram",
            "title": "🍳 Kitchen Upgrade Fest - Air Fryers & Mixers",
            "text": "🍳 Kitchen Upgrade Fest!\n\nAir fryers, non-stick cookware & mixer grinders at best festive prices.\n\nCheck deal: amzaff.in/JTGc9BA",
            "category": "Home & Kitchen",
            "offset_days": 0,
            "hour": 18,
            "minute": 15,
            "status": "scheduled",
            "image_name": "@amazonindiaassociates_13759.jpg",
            "links": ["https://amzaff.in/JTGc9BA"],
        },
        {
            "id": "post_seed_cal_4",
            "post_number": "4",
            "channel": "amazonindiaassociates",
            "channel_name": "Amazon India Associates",
            "channel_type": "telegram",
            "title": "⚡ Lightning Deal: Echo Dot 5th Gen 50% Off",
            "text": "⚡ Lightning Deal on Echo Smart Speakers & Smart Bulbs!\n\nGrab deal: amzaff.in/EchoDeal22",
            "category": "Gadgets",
            "offset_days": 1,
            "hour": 11,
            "minute": 0,
            "status": "scheduled",
            "image_name": "@amazonindiaassociates_13760.jpg",
            "links": ["https://amzaff.in/EchoDeal22"],
        },
        {
            "id": "post_seed_cal_5",
            "post_number": "5",
            "channel": "Amazon_Associates_FashionBeauty",
            "channel_name": "Fashion & Beauty",
            "channel_type": "telegram",
            "title": "💄 Luxury Beauty Weekend Special",
            "text": "💄 Luxury Beauty Weekend Special:\n\nPremium serums, fragrances and makeup up to 45% off.\n\nLink: amzaff.in/LuxuryBeauty",
            "category": "Beauty",
            "offset_days": 1,
            "hour": 15,
            "minute": 45,
            "status": "scheduled",
            "image_name": "@amazonindiaassociates_13761.jpg",
            "links": ["https://amzaff.in/LuxuryBeauty"],
        },
        {
            "id": "post_seed_cal_6",
            "post_number": "6",
            "channel": "Amazon_Associates_Consumables",
            "channel_name": "Consumables & Grocery",
            "channel_type": "telegram",
            "title": "📦 Super Value Days: Daily Essentials & Pantry",
            "text": "📦 Super Value Days:\n\nStock up on pantry staples, snacks & beverages with extra 10% coupon.\n\nOrder: amzaff.in/SuperValueDay",
            "category": "Grocery",
            "offset_days": 2,
            "hour": 12,
            "minute": 30,
            "status": "scheduled",
            "image_name": "@amazonindiaassociates_13762.jpg",
            "links": ["https://amzaff.in/SuperValueDay"],
        },
        # September 2026 Scheduled Posts (QPilot Default View in screenshot)
        {
            "id": "post_sep_1",
            "post_number": "101",
            "channel": "amazonindiaassociates",
            "channel_name": "Amazon India Associates",
            "channel_type": "telegram",
            "title": "📱 iPhone 16 Pro Festive Pre-order Deals",
            "text": "📱 Apple Festive Season Deals:\n\nFlat ₹5,000 instant bank discount on iPhone 16 & 16 Pro!\n\nLink: amzaff.in/iPhoneFestive",
            "category": "Electronics",
            "exact_dt": "2026-09-02T11:00:00",
            "status": "scheduled",
            "image_name": "@amazonindiaassociates_13756.jpg",
            "links": ["https://amzaff.in/iPhoneFestive"],
        },
        {
            "id": "post_sep_2",
            "post_number": "102",
            "channel": "Amazon_Associates_FashionBeauty",
            "channel_name": "Fashion & Beauty",
            "channel_type": "telegram",
            "title": "👗 Festive Ethnic Wear Fest (Up to 70% Off)",
            "text": "👗 Festive Kurti Sets & Sarees from top brands starting at ₹499.\n\nShop: amzaff.in/EthnicFest",
            "category": "Fashion",
            "exact_dt": "2026-09-05T14:30:00",
            "status": "scheduled",
            "image_name": "@amazonindiaassociates_13758.jpg",
            "links": ["https://amzaff.in/EthnicFest"],
        },
        {
            "id": "post_sep_3",
            "post_number": "103",
            "channel": "Amazon_Associates_HomeKitchen",
            "channel_name": "Home & Kitchen",
            "channel_type": "telegram",
            "title": "☕ Philips Automatic Coffee Maker 40% Off",
            "text": "☕ Barista quality coffee at home. Instant ₹1,500 coupon applied at checkout.\n\nDeal: amzaff.in/CoffeeDeal",
            "category": "Home & Kitchen",
            "exact_dt": "2026-09-08T16:00:00",
            "status": "scheduled",
            "image_name": "@amazonindiaassociates_13759.jpg",
            "links": ["https://amzaff.in/CoffeeDeal"],
        },
        {
            "id": "post_sep_4",
            "post_number": "104",
            "channel": "amazonindiaassociates",
            "channel_name": "Amazon India Associates",
            "channel_type": "telegram",
            "title": "📺 Sony Bravia 55-inch 4K Google TV",
            "text": "📺 Blockbuster Smart TV Deal:\n\nSony 55-inch 4K HDR Smart TV at lowest price of the year.\n\nBuy: amzaff.in/SonyTV55",
            "category": "Electronics",
            "exact_dt": "2026-09-12T18:30:00",
            "status": "scheduled",
            "image_name": "@amazonindiaassociates_13760.jpg",
            "links": ["https://amzaff.in/SonyTV55"],
        },
        {
            "id": "post_sep_5",
            "post_number": "105",
            "channel": "Amazon_Associates_FashionBeauty",
            "channel_name": "Fashion & Beauty",
            "channel_type": "telegram",
            "title": "👟 Puma & Nike Sneaker Carnival",
            "text": "👟 Sneaker Carnival: Extra 15% off coupon on running & casual sneakers.\n\nGrab: amzaff.in/SneakerCarnival",
            "category": "Fashion",
            "exact_dt": "2026-09-15T15:00:00",
            "status": "scheduled",
            "image_name": "@amazonindiaassociates_13761.jpg",
            "links": ["https://amzaff.in/SneakerCarnival"],
        },
        {
            "id": "post_sep_6",
            "post_number": "106",
            "channel": "Amazon_Associates_Consumables",
            "channel_name": "Consumables & Grocery",
            "channel_type": "telegram",
            "title": "🍫 Premium Chocolates & Dry Fruit Gift Boxes",
            "text": "🍫 Festive Gifting Steals: Ferrero Rocher & roasted dry fruits combo up to 35% off.\n\nOrder: amzaff.in/ChocoGiftBox",
            "category": "Grocery",
            "exact_dt": "2026-09-18T12:00:00",
            "status": "scheduled",
            "image_name": "@amazonindiaassociates_13762.jpg",
            "links": ["https://amzaff.in/ChocoGiftBox"],
        },
        {
            "id": "post_sep_7",
            "post_number": "107",
            "channel": "amazonindiaassociates",
            "channel_name": "Amazon India Associates",
            "channel_type": "telegram",
            "title": "💻 Apple MacBook Air M3 Lowest Ever",
            "text": "💻 MacBook Air M3 16GB RAM model with free Apple AirPods offer.\n\nLink: amzaff.in/MacBookM3Deal",
            "category": "Electronics",
            "exact_dt": "2026-09-22T17:15:00",
            "status": "scheduled",
            "image_name": "@amazonindiaassociates_13756.jpg",
            "links": ["https://amzaff.in/MacBookM3Deal"],
        },
        {
            "id": "post_sep_8",
            "post_number": "108",
            "channel": "Amazon_Associates_FashionBeauty",
            "channel_name": "Fashion & Beauty",
            "channel_type": "telegram",
            "title": "✨ Festive Gold & Diamond Jewelry Fest",
            "text": "✨ Certified diamond pendant & gold coins at 0% making charges.\n\nLink: amzaff.in/GoldJewelryFest",
            "category": "Jewelry",
            "exact_dt": "2026-09-25T19:00:00",
            "status": "scheduled",
            "image_name": "@amazonindiaassociates_13758.jpg",
            "links": ["https://amzaff.in/GoldJewelryFest"],
        },
        {
            "id": "post_sep_9",
            "post_number": "109",
            "channel": "Amazon_Associates_HomeKitchen",
            "channel_name": "Home & Kitchen",
            "channel_type": "telegram",
            "title": "🧹 Dyson V12 Cordless Vacuum Deal",
            "text": "🧹 Deep clean your home for the festive season. Flat ₹7,000 off.\n\nDeal: amzaff.in/DysonV12Deal",
            "category": "Home & Kitchen",
            "exact_dt": "2026-09-28T13:45:00",
            "status": "scheduled",
            "image_name": "@amazonindiaassociates_13759.jpg",
            "links": ["https://amzaff.in/DysonV12Deal"],
        },
    ]

    for item in seeds:
        if "exact_dt" in item:
            dt = datetime.fromisoformat(item["exact_dt"])
            target_dt = ist.localize(dt) if dt.tzinfo is None else dt
        else:
            target_dt = (now_ist + timedelta(days=item["offset_days"])).replace(
                hour=item["hour"], minute=item["minute"], second=0, microsecond=0
            )
        date_str = target_dt.strftime("%Y-%m-%d")
        time_str = target_dt.strftime("%H:%M")
        iso_str = target_dt.isoformat()
        now_iso = now_ist.isoformat()

        cursor.execute("""
            INSERT OR REPLACE INTO calendar_events (
                id, post_number, channel, channel_name, channel_type,
                title, text, category, scheduled_time, date_str, time_str,
                status, image_name, image_url, links, source, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            item["id"],
            item["post_number"],
            item["channel"],
            item["channel_name"],
            item["channel_type"],
            item["title"],
            item["text"],
            item["category"],
            iso_str,
            date_str,
            time_str,
            item["status"],
            item.get("image_name"),
            None,
            json.dumps(item.get("links", [])),
            "seed",
            now_iso,
            now_iso
        ))
    conn.commit()
    conn.close()
    print("✅ Initial calendar events seeded successfully into SQLite!")

def save_calendar_event(event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Saves or updates a single calendar event in SQLite."""
    conn = get_db_connection()
    now_iso = datetime.now(ist).isoformat()
    
    event_id = event_dict.get("id") or f"cal_{int(datetime.now().timestamp() * 1000)}"
    scheduled_time = event_dict.get("scheduled_time") or event_dict.get("start") or event_dict.get("time") or now_iso
    
    # Parse date_str and time_str safely
    try:
        dt = datetime.fromisoformat(str(scheduled_time).replace("Z", "+00:00"))
        date_str = dt.strftime("%Y-%m-%d")
        time_str = dt.strftime("%H:%M")
    except Exception:
        date_str = event_dict.get("date") or datetime.now(ist).strftime("%Y-%m-%d")
        time_str = event_dict.get("time") or "12:00"

    channel = event_dict.get("channel", "amazonindiaassociates").replace("@", "").strip()
    title = event_dict.get("title") or f"Post: {channel} @ {time_str}"
    
    with conn:
        conn.execute("""
            INSERT OR REPLACE INTO calendar_events (
                id, post_number, channel, channel_name, channel_type,
                title, text, category, scheduled_time, date_str, time_str,
                status, image_name, image_url, links, source, views,
                telegram_clicks, whatsapp_clicks, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event_id,
            str(event_dict.get("post_number") or event_dict.get("post", "")),
            channel,
            event_dict.get("channel_name", channel),
            event_dict.get("channel_type", "telegram"),
            title,
            event_dict.get("text") or event_dict.get("message", ""),
            event_dict.get("category", ""),
            scheduled_time,
            date_str,
            time_str,
            event_dict.get("status", "scheduled"),
            event_dict.get("image_name") or event_dict.get("image"),
            event_dict.get("image_url"),
            json.dumps(event_dict.get("links", []) if isinstance(event_dict.get("links"), list) else []),
            event_dict.get("source", "user"),
            event_dict.get("views", 0),
            event_dict.get("telegram_clicks", 0),
            event_dict.get("whatsapp_clicks", 0),
            event_dict.get("created_at", now_iso),
            now_iso
        ))
    conn.close()
    return get_calendar_event_by_id(event_id)

def get_calendar_event_by_id(event_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM calendar_events WHERE id = ?", (event_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return format_event_row(row)

def delete_calendar_event(event_id: str) -> bool:
    conn = get_db_connection()
    with conn:
        cursor = conn.execute("DELETE FROM calendar_events WHERE id = ?", (event_id,))
        deleted = cursor.rowcount > 0
    conn.close()
    return deleted

def format_event_row(row: sqlite3.Row) -> Dict[str, Any]:
    d = dict(row)
    links_raw = d.get("links") or "[]"
    try:
        links = json.loads(links_raw)
    except Exception:
        links = []
    
    # Calculate end time (15 mins duration standard for calendar display)
    start_iso = d.get("scheduled_time")
    try:
        start_dt = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
        end_iso = (start_dt + timedelta(minutes=15)).isoformat()
    except Exception:
        end_iso = start_iso

    return {
        "id": d["id"],
        "post_number": d.get("post_number"),
        "title": d["title"],
        "channel": d["channel"],
        "channel_name": d.get("channel_name") or d["channel"],
        "channel_type": d.get("channel_type", "telegram"),
        "text": d.get("text", ""),
        "message": d.get("text", ""),
        "category": d.get("category", ""),
        "start": start_iso,
        "end": end_iso,
        "date": d["date_str"],
        "time": d["time_str"],
        "status": d.get("status", "scheduled"),
        "image_name": d.get("image_name"),
        "image": d.get("image_name"),
        "image_url": d.get("image_url"),
        "links": links,
        "views": d.get("views", 0),
        "telegram_clicks": d.get("telegram_clicks", 0),
        "whatsapp_clicks": d.get("whatsapp_clicks", 0),
        "source": d.get("source", "scheduler"),
        "created_at": d.get("created_at"),
    }

def get_calendar_events_filtered(
    date_str: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    month: Optional[int] = None,
    year: Optional[int] = None,
    channel: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieves events filtered by exact date, range, month/year, and optional channel.
    """
    init_calendar_db()
    conn = get_db_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM calendar_events WHERE 1=1"
    params = []

    if channel and channel.lower() not in ["all", "any", ""]:
        clean_channel = channel.replace("@", "").strip()
        query += " AND LOWER(channel) = LOWER(?)"
        params.append(clean_channel)

    if date_str:
        query += " AND date_str = ?"
        params.append(date_str)
    elif start_date and end_date:
        query += " AND date_str >= ? AND date_str <= ?"
        params.extend([start_date, end_date])
    elif start_date:
        query += " AND date_str >= ?"
        params.append(start_date)
    elif end_date:
        query += " AND date_str <= ?"
        params.append(end_date)
    elif month and year:
        month_pad = f"{month:02d}"
        prefix = f"{year}-{month_pad}-%"
        query += " AND date_str LIKE ?"
        params.append(prefix)
    elif year:
        prefix = f"{year}-%"
        query += " AND date_str LIKE ?"
        params.append(prefix)

    query += " ORDER BY date_str ASC, time_str ASC"
    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    conn.close()

    events = [format_event_row(r) for r in rows]
    return events
