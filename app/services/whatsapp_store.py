# app/services/whatsapp_store.py
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from typing import Any, Optional, List

DB_DIR = "data"
DB_PATH = os.path.join(DB_DIR, "whatsapp_scheduler.db")
MAX_ATTEMPTS = 5

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

def to_utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()

def row_to_dict(row: Optional[sqlite3.Row]) -> Optional[dict]:
    return dict(row) if row else None

@contextmanager
def get_conn():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db():
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS whatsapp_recipients (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                phone TEXT,
                subscribers TEXT,
                avatar TEXT,
                color TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS whatsapp_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipient_id TEXT NOT NULL,
                recipient_name TEXT NOT NULL,
                recipient_phone TEXT,
                message TEXT,
                image_path TEXT,
                scheduled_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                attempts INTEGER NOT NULL DEFAULT 0,
                next_attempt_at TEXT,
                locked_at TEXT,
                sent_at TEXT,
                provider_message_id TEXT,
                last_error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (recipient_id) REFERENCES whatsapp_recipients(id)
            )
            """
        )
        _seed_recipients(conn)

def _seed_recipients(conn: sqlite3.Connection):
    count = conn.execute("SELECT COUNT(*) FROM whatsapp_recipients").fetchone()[0]
    if count > 0:
        return
    defaults = [
        {"id": "amazonindiaassociates", "name": "Amazon India Associates", "phone": "120363408723243626@newsletter", "subscribers": "@amazonindiaassociates", "avatar": "A", "color": "bg-orange-500"},
        {"id": "fashion_beauty", "name": "Fashion & Beauty", "phone": "120363400693925981@newsletter", "subscribers": "@amazon_fashion", "avatar": "F", "color": "bg-pink-500"},
        {"id": "whatsapp_deals_testing", "name": "WhatsApp Deals Testing", "phone": "120363408723243626@newsletter", "subscribers": "Test Group", "avatar": "W", "color": "bg-emerald-500"},
        {"id": "bhajan_marg", "name": "Bhajan Marg", "phone": "120363178482495644@newsletter", "subscribers": "Community", "avatar": "B", "color": "bg-orange-500"},
        {"id": "jayam_sk_gopi", "name": "Jayam SK Gopi", "phone": "120363311931035694@newsletter", "subscribers": "Spiritual Channel", "avatar": "J", "color": "bg-red-500"},
        {"id": "manguni_gamer", "name": "Manguni Gamer", "phone": "120363163312669944@newsletter", "subscribers": "Gaming Network", "avatar": "M", "color": "bg-purple-500"},
        {"id": "thinkcraft_academy", "name": "Thinkcraft Academy", "phone": "120363420592093827@newsletter", "subscribers": "Education Guild", "avatar": "T", "color": "bg-blue-500"},
        {"id": "art_of_living", "name": "Art of Living Meditation Challenge", "phone": "120363162744866869@newsletter", "subscribers": "Meditation", "avatar": "O", "color": "bg-teal-500"},
    ]
    now_str = to_utc_iso(utc_now())
    for r in defaults:
        conn.execute(
            "INSERT INTO whatsapp_recipients (id, name, phone, subscribers, avatar, color, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (r["id"], r["name"], r["phone"], r["subscribers"], r["avatar"], r["color"], now_str)
        )

def list_recipients() -> List[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM whatsapp_recipients ORDER BY name ASC").fetchall()
        return [dict(r) for r in rows]

def update_recipient_phone(recipient_id: str, phone: str) -> Optional[dict]:
    with get_conn() as conn:
        conn.execute("UPDATE whatsapp_recipients SET phone = ? WHERE id = ?", (phone.strip(), recipient_id))
        row = conn.execute("SELECT * FROM whatsapp_recipients WHERE id = ?", (recipient_id,)).fetchone()
        return dict(row) if row else None

def reset_recipient_targets() -> List[dict]:
    with get_conn() as conn:
        conn.execute("DELETE FROM whatsapp_recipients")
        _seed_recipients(conn)
        return list_recipients()

def list_posts(recipient_id: Optional[str] = None) -> List[dict]:
    with get_conn() as conn:
        if recipient_id:
            rows = conn.execute("SELECT * FROM whatsapp_posts WHERE recipient_id = ? ORDER BY scheduled_at DESC", (recipient_id,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM whatsapp_posts ORDER BY scheduled_at DESC").fetchall()
        return [dict(r) for r in rows]

def get_post(post_id: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM whatsapp_posts WHERE id = ?", (post_id,)).fetchone()
        return dict(row) if row else None

def create_post(recipient_id: str, message: Optional[str], image_path: Optional[str], scheduled_at: datetime) -> dict:
    with get_conn() as conn:
        rec = conn.execute("SELECT * FROM whatsapp_recipients WHERE id = ?", (recipient_id,)).fetchone()
        if not rec:
            raise ValueError("Recipient not found")
        now_str = to_utc_iso(utc_now())
        sched_str = to_utc_iso(scheduled_at)
        cur = conn.execute(
            """
            INSERT INTO whatsapp_posts
            (recipient_id, recipient_name, recipient_phone, message, image_path, scheduled_at, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)
            """,
            (rec["id"], rec["name"], rec["phone"], message, image_path, sched_str, now_str, now_str)
        )
        post_id = cur.lastrowid
        row = conn.execute("SELECT * FROM whatsapp_posts WHERE id = ?", (post_id,)).fetchone()
        return dict(row)

def cancel_post(post_id: int) -> Optional[dict]:
    with get_conn() as conn:
        conn.execute("UPDATE whatsapp_posts SET status = 'cancelled', updated_at = ? WHERE id = ?", (to_utc_iso(utc_now()), post_id))
        row = conn.execute("SELECT * FROM whatsapp_posts WHERE id = ?", (post_id,)).fetchone()
        return dict(row) if row else None

def update_post(post_id: int, message: Optional[str] = None, image_path: Optional[str] = None, scheduled_at: Optional[datetime] = None, replace_image: bool = False, remove_image: bool = False) -> Optional[dict]:
    with get_conn() as conn:
        post = conn.execute("SELECT * FROM whatsapp_posts WHERE id = ?", (post_id,)).fetchone()
        if not post:
            return None
        new_msg = message if message is not None else post["message"]
        new_sched = to_utc_iso(scheduled_at) if scheduled_at is not None else post["scheduled_at"]
        new_img = post["image_path"]
        if remove_image:
            new_img = None
        elif replace_image and image_path:
            new_img = image_path

        conn.execute(
            """
            UPDATE whatsapp_posts SET message = ?, image_path = ?, scheduled_at = ?, updated_at = ? WHERE id = ?
            """,
            (new_msg, new_img, new_sched, to_utc_iso(utc_now()), post_id)
        )
        row = conn.execute("SELECT * FROM whatsapp_posts WHERE id = ?", (post_id,)).fetchone()
        return dict(row)
