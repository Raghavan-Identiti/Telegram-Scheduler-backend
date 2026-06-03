import os
from datetime import datetime, timezone
from typing import Optional

import pytz
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from whatsapp_store import (
    cancel_post,
    create_post,
    get_post,
    init_db,
    list_posts,
    list_recipients,
    reset_recipient_targets,
    update_post,
    update_recipient_phone,
)
from whatsapp_utils import get_provider_status


router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])
UPLOAD_DIR = os.path.join("uploads", "whatsapp")
IST = pytz.timezone("Asia/Kolkata")


class RecipientPhoneRequest(BaseModel):
    phone: str


def _parse_scheduled_at(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid scheduled_at datetime") from exc

    if parsed.tzinfo is None:
        parsed = IST.localize(parsed)
    return parsed.astimezone(timezone.utc)


def _serialize_post(post: dict) -> dict:
    image_path = post.get("image_path")
    image_url = None
    if image_path:
        image_url = "/" + image_path.replace("\\", "/")
    return {**post, "image_url": image_url}


@router.on_event("startup")
async def startup():
    init_db()


@router.get("/health")
async def health():
    provider = await get_provider_status()
    configured = bool(provider.get("logged_in"))
    return {
        "configured": configured,
        "provider": "baileys",
        "message": provider.get("message", "WhatsApp sender is ready"),
    }


@router.get("/chats")
async def chats():
    init_db()
    return {"chats": list_recipients()}


@router.patch("/chats/{chat_id}/phone")
async def set_chat_phone(chat_id: str, req: RecipientPhoneRequest):
    init_db()
    chat = update_recipient_phone(chat_id, req.phone)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    if not chat.get("phone"):
        raise HTTPException(status_code=400, detail="WhatsApp Web target name is required")
    return {"chat": chat}


@router.post("/chats/reset-targets")
async def reset_chat_targets():
    init_db()
    return {"chats": reset_recipient_targets()}


@router.get("/scheduled-posts")
async def scheduled_posts(chat_id: Optional[str] = None):
    init_db()
    return {"posts": [_serialize_post(post) for post in list_posts(chat_id)]}


@router.post("/schedule")
async def schedule_post(
    chat_id: str = Form(...),
    message: str = Form(""),
    scheduled_at: str = Form(...),
    image_file: UploadFile | None = File(None),
):
    init_db()
    image_path = None
    if image_file and image_file.filename:
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        safe_name = os.path.basename(image_file.filename)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        image_path = os.path.join(UPLOAD_DIR, f"{timestamp}_{safe_name}")
        with open(image_path, "wb") as file:
            file.write(await image_file.read())

    try:
        post = create_post(
            recipient_id=chat_id,
            message=message.strip() or None,
            image_path=image_path,
            scheduled_at=_parse_scheduled_at(scheduled_at),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"post": _serialize_post(post)}


@router.post("/posts/{post_id}/cancel")
async def cancel_scheduled_post(post_id: int):
    post = cancel_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return {"post": _serialize_post(post)}


@router.patch("/posts/{post_id}")
async def edit_scheduled_post(
    post_id: int,
    message: str | None = Form(None),
    scheduled_at: str | None = Form(None),
    remove_image: bool = Form(False),
    image_file: UploadFile | None = File(None),
):
    image_path = None
    replace_image = bool(image_file and image_file.filename)
    if image_file and image_file.filename:
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        safe_name = os.path.basename(image_file.filename)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        image_path = os.path.join(UPLOAD_DIR, f"{timestamp}_{safe_name}")
        with open(image_path, "wb") as file:
            file.write(await image_file.read())

    parsed_time = _parse_scheduled_at(scheduled_at) if scheduled_at else None
    try:
        post = update_post(
            post_id=post_id,
            message=message,
            image_path=image_path,
            scheduled_at=parsed_time,
            replace_image=replace_image,
            remove_image=remove_image,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return {"post": _serialize_post(post)}


@router.get("/webhook", response_class=PlainTextResponse)
async def verify_webhook(request: Request):
    verify_token = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
    params = request.query_params
    if (
        params.get("hub.mode") == "subscribe"
        and verify_token
        and params.get("hub.verify_token") == verify_token
    ):
        return params.get("hub.challenge", "")
    raise HTTPException(status_code=403, detail="Invalid verify token")


@router.post("/webhook")
async def receive_webhook(request: Request):
    payload = await request.json()
    return {"received": True, "entry_count": len(payload.get("entry", []))}
