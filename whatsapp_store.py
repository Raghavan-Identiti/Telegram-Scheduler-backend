import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from typing import Any


DB_DIR = "data"
DB_PATH = os.path.join(DB_DIR, "whatsapp_scheduler.db")
MAX_ATTEMPTS = 5


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
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
    configured = os.getenv("WHATSAPP_RECIPIENTS")
    recipients = []
    if configured:
        try:
            recipients = json.loads(configured)
        except json.JSONDecodeError:
            recipients = []

    if not recipients:
        recipients = [
            {
                "id": "amazonindiaassociates",
                "name": "Amazon India Associates",
                "phone": os.getenv("WHATSAPP_TEST_RECIPIENT", ""),
                "subscribers": "@amazonindiaassociates",
                "avatar": "A",
                "color": "bg-orange-500",
            },
            {
                "id": "Amazon_Associates_FashionBeauty",
                "name": "Fashion & Beauty",
                "phone": "",
                "subscribers": "@Amazon_Associates_FashionBeauty",
                "avatar": "F",
                "color": "bg-pink-500",
            },
            {
                "id": "Amazon_Associates_HomeKitchen",
                "name": "Home & Kitchen",
                "phone": "",
                "subscribers": "@Amazon_Associates_HomeKitchen",
                "avatar": "H",
                "color": "bg-blue-500",
            },
            {
                "id": "Amazon_Associates_Consumables",
                "name": "Consumables",
                "phone": "",
                "subscribers": "@Amazon_Associates_Consumables",
                "avatar": "C",
                "color": "bg-green-500",
            },
        ]

    now = utc_now()
    for i, item in enumerate(recipients):
        item_created_at = to_utc_iso(now + timedelta(seconds=i))
        conn.execute(
            """
            INSERT INTO whatsapp_recipients (id, name, phone, subscribers, avatar, color, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                phone = COALESCE(NULLIF(excluded.phone, ''), whatsapp_recipients.phone),
                subscribers = excluded.subscribers,
                avatar = excluded.avatar,
                color = excluded.color
            """,
            (
                item["id"],
                item["name"],
                item.get("phone", ""),
                item.get("subscribers", ""),
                item.get("avatar", item["name"][:1].upper()),
                item.get("color", "bg-slate-500"),
                item_created_at,
            ),
        )

    current_ids = {item["id"] for item in recipients}
    obsolete_default_ids = {
        "amazon-associates",
        "fashion-beauty",
        "home-kitchen",
        "consumables",
        "tech-gadgets",
    } - current_ids
    for old_id in obsolete_default_ids:
        conn.execute(
            """
            DELETE FROM whatsapp_recipients
            WHERE id = ?
              AND NOT EXISTS (
                SELECT 1 FROM whatsapp_posts WHERE whatsapp_posts.recipient_id = whatsapp_recipients.id
              )
            """,
            (old_id,),
        )


def list_recipients() -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                r.*,
                COUNT(CASE WHEN p.status IN ('pending', 'retrying', 'sending') THEN 1 END) AS pending_count,
                MAX(p.created_at) AS last_post_at
            FROM whatsapp_recipients r
            LEFT JOIN whatsapp_posts p ON p.recipient_id = r.id
            GROUP BY r.id
            ORDER BY r.created_at ASC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def get_recipient(recipient_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM whatsapp_recipients WHERE id = ?",
            (recipient_id,),
        ).fetchone()
    return row_to_dict(row)


def update_recipient_phone(recipient_id: str, phone: str) -> dict[str, Any] | None:
    cleaned = phone.strip()
    with get_conn() as conn:
        conn.execute(
            "UPDATE whatsapp_recipients SET phone = ? WHERE id = ?",
            (cleaned, recipient_id),
        )
        conn.execute(
            "UPDATE whatsapp_posts SET recipient_phone = ? WHERE recipient_id = ? AND status IN ('pending', 'retrying')",
            (cleaned, recipient_id),
        )
        row = conn.execute(
            "SELECT * FROM whatsapp_recipients WHERE id = ?",
            (recipient_id,),
        ).fetchone()
    return row_to_dict(row)


def reset_recipient_targets() -> list[dict[str, Any]]:
    with get_conn() as conn:
        conn.execute("UPDATE whatsapp_recipients SET phone = ''")
        rows = conn.execute("SELECT * FROM whatsapp_recipients ORDER BY created_at ASC").fetchall()
    return [dict(row) for row in rows]


def create_post(
    recipient_id: str,
    message: str | None,
    image_path: str | None,
    scheduled_at: datetime,
) -> dict[str, Any]:
    recipient = get_recipient(recipient_id)
    if not recipient:
        raise ValueError("Unknown WhatsApp recipient")
    if not (message or image_path):
        raise ValueError("Message or image is required")

    now = to_utc_iso(utc_now())
    scheduled_at_iso = to_utc_iso(scheduled_at)
    with get_conn() as conn:
        cursor = conn.execute(
            """
            INSERT INTO whatsapp_posts (
                recipient_id, recipient_name, recipient_phone, message, image_path,
                scheduled_at, status, next_attempt_at, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)
            """,
            (
                recipient["id"],
                recipient["name"],
                recipient.get("phone", ""),
                message,
                image_path,
                scheduled_at_iso,
                scheduled_at_iso,
                now,
                now,
            ),
        )
        post_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM whatsapp_posts WHERE id = ?", (post_id,)).fetchone()
    return row_to_dict(row)


def list_posts(recipient_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    query = "SELECT * FROM whatsapp_posts"
    params: list[Any] = []
    if recipient_id:
        query += " WHERE recipient_id = ?"
        params.append(recipient_id)
    query += " ORDER BY scheduled_at DESC LIMIT ?"
    params.append(limit)
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def get_post(post_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM whatsapp_posts WHERE id = ?", (post_id,)).fetchone()
    return row_to_dict(row)


def update_post(
    post_id: int,
    message: str | None = None,
    image_path: str | None = None,
    scheduled_at: datetime | None = None,
    replace_image: bool = False,
    remove_image: bool = False,
) -> dict[str, Any] | None:
    existing = get_post(post_id)
    if not existing:
        return None
    if existing["status"] not in ("pending", "retrying", "failed", "cancelled"):
        raise ValueError("Only unsent posts can be edited")

    next_message = existing.get("message")
    if message is not None:
        next_message = message.strip() or None

    next_image_path = existing.get("image_path")
    if remove_image:
        next_image_path = None
    elif replace_image:
        next_image_path = image_path

    if not (next_message or next_image_path):
        raise ValueError("Message or image is required")

    next_scheduled_at = existing["scheduled_at"]
    if scheduled_at is not None:
        next_scheduled_at = to_utc_iso(scheduled_at)

    now = to_utc_iso(utc_now())
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE whatsapp_posts
            SET message = ?,
                image_path = ?,
                scheduled_at = ?,
                status = 'pending',
                attempts = 0,
                next_attempt_at = ?,
                locked_at = NULL,
                sent_at = NULL,
                provider_message_id = NULL,
                last_error = NULL,
                updated_at = ?
            WHERE id = ?
            """,
            (next_message, next_image_path, next_scheduled_at, next_scheduled_at, now, post_id),
        )
        row = conn.execute("SELECT * FROM whatsapp_posts WHERE id = ?", (post_id,)).fetchone()
    return row_to_dict(row)


def claim_due_posts(limit: int = 5) -> list[dict[str, Any]]:
    now = to_utc_iso(utc_now())
    stale_cutoff = to_utc_iso(utc_now() - timedelta(minutes=15))
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """
            UPDATE whatsapp_posts
            SET status = 'retrying', locked_at = NULL, updated_at = ?
            WHERE status = 'sending' AND locked_at < ?
            """,
            (now, stale_cutoff),
        )
        rows = conn.execute(
            """
            SELECT * FROM whatsapp_posts
            WHERE status IN ('pending', 'retrying')
              AND scheduled_at <= ?
              AND COALESCE(next_attempt_at, scheduled_at) <= ?
              AND attempts < ?
            ORDER BY scheduled_at ASC
            LIMIT ?
            """,
            (now, now, MAX_ATTEMPTS, limit),
        ).fetchall()
        post_ids = [row["id"] for row in rows]
        if post_ids:
            placeholders = ",".join("?" for _ in post_ids)
            conn.execute(
                f"""
                UPDATE whatsapp_posts
                SET status = 'sending',
                    attempts = attempts + 1,
                    locked_at = ?,
                    updated_at = ?
                WHERE id IN ({placeholders})
                """,
                [now, now, *post_ids],
            )
            rows = conn.execute(
                f"SELECT * FROM whatsapp_posts WHERE id IN ({placeholders})",
                post_ids,
            ).fetchall()
    return [dict(row) for row in rows]


def mark_sent(post_id: int, provider_message_id: str | None):
    now = to_utc_iso(utc_now())
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE whatsapp_posts
            SET status = 'sent',
                sent_at = ?,
                provider_message_id = ?,
                locked_at = NULL,
                last_error = NULL,
                updated_at = ?
            WHERE id = ?
            """,
            (now, provider_message_id, now, post_id),
        )


def mark_failed(post_id: int, error: str):
    post = get_post(post_id)
    if not post:
        return
    attempts = int(post["attempts"] or 0)
    status = "failed" if attempts >= MAX_ATTEMPTS else "retrying"
    delay_minutes = min(60, 2**max(0, attempts - 1))
    next_attempt_at = to_utc_iso(utc_now() + timedelta(minutes=delay_minutes))
    now = to_utc_iso(utc_now())
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE whatsapp_posts
            SET status = ?,
                next_attempt_at = ?,
                locked_at = NULL,
                last_error = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (status, next_attempt_at, error[:1000], now, post_id),
        )


def cancel_post(post_id: int) -> dict[str, Any] | None:
    now = to_utc_iso(utc_now())
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE whatsapp_posts
            SET status = 'cancelled', updated_at = ?
            WHERE id = ? AND status IN ('pending', 'retrying', 'failed')
            """,
            (now, post_id),
        )
        row = conn.execute("SELECT * FROM whatsapp_posts WHERE id = ?", (post_id,)).fetchone()
    return row_to_dict(row)
