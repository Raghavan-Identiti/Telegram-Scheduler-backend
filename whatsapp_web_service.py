import asyncio
import os
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from whatsapp_web_automation import WhatsAppWebError, sender


DB_DIR = Path("data")
DB_PATH = DB_DIR / "whatsapp_web_scheduler.db"
POLL_SECONDS = int(os.getenv("WHATSAPP_WEB_POLL_SECONDS", "15"))
MAX_ATTEMPTS = int(os.getenv("WHATSAPP_WEB_MAX_ATTEMPTS", "5"))


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def parse_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid run_at datetime") from exc
    if parsed.tzinfo is None:
        parsed = parsed.astimezone()
    return parsed.astimezone(timezone.utc)


def connect() -> sqlite3.Connection:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS whatsapp_web_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target TEXT NOT NULL,
                message TEXT,
                image_path TEXT,
                run_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                attempts INTEGER NOT NULL DEFAULT 0,
                next_attempt_at TEXT,
                sent_at TEXT,
                last_error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def create_job(target: str, message: str | None, image_path: str | None, run_at: datetime) -> dict[str, Any]:
    if not target.strip():
        raise HTTPException(status_code=400, detail="target is required")
    if not (message or image_path):
        raise HTTPException(status_code=400, detail="message or image_path is required")
    if image_path and not Path(image_path).exists():
        raise HTTPException(status_code=400, detail=f"image_path does not exist: {image_path}")

    now = to_utc_iso(utc_now())
    run_at_iso = to_utc_iso(run_at)
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO whatsapp_web_jobs (
                target, message, image_path, run_at, status, next_attempt_at, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, 'pending', ?, ?, ?)
            """,
            (target.strip(), message or "", image_path, run_at_iso, run_at_iso, now, now),
        )
        job_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM whatsapp_web_jobs WHERE id = ?", (job_id,)).fetchone()
    return row_to_dict(row)


def list_jobs(status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    query = "SELECT * FROM whatsapp_web_jobs"
    params: list[Any] = []
    if status:
        query += " WHERE status = ?"
        params.append(status)
    query += " ORDER BY run_at DESC LIMIT ?"
    params.append(limit)
    with connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [row_to_dict(row) for row in rows]


def claim_due_jobs(limit: int = 3) -> list[dict[str, Any]]:
    now = to_utc_iso(utc_now())
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        rows = conn.execute(
            """
            SELECT * FROM whatsapp_web_jobs
            WHERE status IN ('pending', 'retrying')
              AND run_at <= ?
              AND COALESCE(next_attempt_at, run_at) <= ?
              AND attempts < ?
            ORDER BY run_at ASC
            LIMIT ?
            """,
            (now, now, MAX_ATTEMPTS, limit),
        ).fetchall()
        ids = [row["id"] for row in rows]
        if ids:
            placeholders = ",".join("?" for _ in ids)
            conn.execute(
                f"""
                UPDATE whatsapp_web_jobs
                SET status = 'sending',
                    attempts = attempts + 1,
                    updated_at = ?
                WHERE id IN ({placeholders})
                """,
                [now, *ids],
            )
            rows = conn.execute(
                f"SELECT * FROM whatsapp_web_jobs WHERE id IN ({placeholders})",
                ids,
            ).fetchall()
    return [row_to_dict(row) for row in rows]


def mark_sent(job_id: int):
    now = to_utc_iso(utc_now())
    with connect() as conn:
        conn.execute(
            """
            UPDATE whatsapp_web_jobs
            SET status = 'sent', sent_at = ?, last_error = NULL, updated_at = ?
            WHERE id = ?
            """,
            (now, now, job_id),
        )


def mark_failed(job_id: int, error: str):
    with connect() as conn:
        row = conn.execute(
            "SELECT attempts FROM whatsapp_web_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
        attempts = int(row["attempts"] or 0) if row else MAX_ATTEMPTS
        status = "failed" if attempts >= MAX_ATTEMPTS else "retrying"
        delay_minutes = min(60, 2 ** max(0, attempts - 1))
        now = to_utc_iso(utc_now())
        next_attempt_at = to_utc_iso(utc_now() + timedelta(minutes=delay_minutes))
        conn.execute(
            """
            UPDATE whatsapp_web_jobs
            SET status = ?,
                next_attempt_at = ?,
                last_error = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (status, next_attempt_at, error[:1000], now, job_id),
        )


def cancel_job(job_id: int) -> dict[str, Any] | None:
    now = to_utc_iso(utc_now())
    with connect() as conn:
        conn.execute(
            """
            UPDATE whatsapp_web_jobs
            SET status = 'cancelled', updated_at = ?
            WHERE id = ? AND status IN ('pending', 'retrying', 'failed')
            """,
            (now, job_id),
        )
        row = conn.execute("SELECT * FROM whatsapp_web_jobs WHERE id = ?", (job_id,)).fetchone()
    return row_to_dict(row) if row else None


async def send_job(job: dict[str, Any]):
    try:
        await sender.send_message(
            target=job["target"],
            message=job.get("message") or "",
            image_path=job.get("image_path"),
        )
        mark_sent(job["id"])
    except Exception as exc:
        mark_failed(job["id"], str(exc))


async def scheduler_loop():
    while True:
        jobs = claim_due_jobs()
        for job in jobs:
            await send_job(job)
        await asyncio.sleep(POLL_SECONDS)


class SendNowRequest(BaseModel):
    target: str
    message: str = ""
    image_path: str | None = None


class ScheduleRequest(BaseModel):
    target: str
    run_at: str
    message: str = ""
    image_path: str | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    task = asyncio.create_task(scheduler_loop())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        await sender.stop()


app = FastAPI(title="QPilot WhatsApp Web Automation", lifespan=lifespan)


@app.get("/health")
async def health():
    try:
        login = await sender.login_status()
    except Exception as exc:
        login = {
            "logged_in": False,
            "message": f"WhatsApp Web service needs attention: {type(exc).__name__}: {exc}",
        }
    return {
        "status": "ok",
        "provider": "whatsapp_web",
        "headless": os.getenv("WHATSAPP_WEB_HEADLESS", "false"),
        **login,
    }


@app.post("/send-now")
async def send_now(req: SendNowRequest):
    try:
        result = await sender.send_message(req.target, req.message, req.image_path)
        return result
    except WhatsAppWebError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}") from exc


@app.post("/schedule")
async def schedule(req: ScheduleRequest):
    job = create_job(
        target=req.target,
        message=req.message,
        image_path=req.image_path,
        run_at=parse_datetime(req.run_at),
    )
    return {"job": job}


@app.get("/jobs")
async def jobs(status: str | None = None, limit: int = 100):
    return {"jobs": list_jobs(status=status, limit=limit)}


@app.post("/jobs/{job_id}/cancel")
async def cancel(job_id: int):
    job = cancel_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job": job}
