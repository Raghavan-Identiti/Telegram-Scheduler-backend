import mimetypes
import os
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

WHATSAPP_API_VERSION = os.getenv("WHATSAPP_API_VERSION", "v20.0")
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_PROVIDER = os.getenv("WHATSAPP_PROVIDER", "web").lower()
WHATSAPP_SERVICE_URL = os.getenv("WHATSAPP_SERVICE_URL", "http://localhost:3001")
GRAPH_BASE_URL = f"https://graph.facebook.com/{WHATSAPP_API_VERSION}"


class WhatsAppConfigError(Exception):
    pass


class WhatsAppSendError(Exception):
    pass


def is_configured() -> bool:
    return bool(WHATSAPP_ACCESS_TOKEN and WHATSAPP_PHONE_NUMBER_ID)


async def get_provider_status() -> dict[str, Any]:
    if WHATSAPP_PROVIDER == "web":
        try:
            resp = requests.get(f"{WHATSAPP_SERVICE_URL}/status", timeout=5)
            if resp.ok:
                return resp.json()
            return {
                "logged_in": False,
                "message": f"Baileys microservice error: {resp.status_code}",
            }
        except requests.RequestException as exc:
            return {
                "logged_in": False,
                "message": f"Baileys microservice not running on port 3001: {exc}",
            }
    return {
        "logged_in": is_configured(),
        "message": "WhatsApp Cloud API configured"
        if is_configured()
        else "Add WHATSAPP_ACCESS_TOKEN and WHATSAPP_PHONE_NUMBER_ID to backend .env",
    }


def _headers() -> dict[str, str]:
    if not is_configured():
        raise WhatsAppConfigError(
            "Missing WHATSAPP_ACCESS_TOKEN or WHATSAPP_PHONE_NUMBER_ID"
        )
    return {"Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}"}


def _messages_url() -> str:
    return f"{GRAPH_BASE_URL}/{WHATSAPP_PHONE_NUMBER_ID}/messages"


def _media_url() -> str:
    return f"{GRAPH_BASE_URL}/{WHATSAPP_PHONE_NUMBER_ID}/media"


def _raise_for_whatsapp_error(response: requests.Response):
    if response.ok:
        return
    try:
        payload = response.json()
    except ValueError:
        payload = {"error": response.text}
    raise WhatsAppSendError(f"WhatsApp API error {response.status_code}: {payload}")


def upload_media(image_path: str) -> str:
    mime_type, _ = mimetypes.guess_type(image_path)
    mime_type = mime_type or "image/jpeg"
    with open(image_path, "rb") as file:
        response = requests.post(
            _media_url(),
            headers=_headers(),
            data={
                "messaging_product": "whatsapp",
                "type": mime_type,
            },
            files={"file": (os.path.basename(image_path), file, mime_type)},
            timeout=60,
        )
    _raise_for_whatsapp_error(response)
    media_id = response.json().get("id")
    if not media_id:
        raise WhatsAppSendError("WhatsApp media upload did not return a media id")
    return media_id


def send_text(to: str, message: str) -> dict[str, Any]:
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {
            "preview_url": True,
            "body": message,
        },
    }
    response = requests.post(
        _messages_url(),
        headers={**_headers(), "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    _raise_for_whatsapp_error(response)
    return response.json()


def send_image(to: str, media_id: str, caption: str | None = None) -> dict[str, Any]:
    image: dict[str, str] = {"id": media_id}
    if caption:
        image["caption"] = caption
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "image",
        "image": image,
    }
    response = requests.post(
        _messages_url(),
        headers={**_headers(), "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    _raise_for_whatsapp_error(response)
    return response.json()


def extract_message_id(payload: dict[str, Any]) -> str | None:
    messages = payload.get("messages") or []
    if not messages:
        return None
    return messages[0].get("id")


def send_scheduled_post(post: dict[str, Any]) -> str | None:
    phone = (post.get("recipient_phone") or "").strip()
    if not phone:
        raise WhatsAppSendError("Recipient phone number is not configured")

    message = (post.get("message") or "").strip()
    image_path = post.get("image_path")
    if image_path and os.path.exists(image_path):
        media_id = upload_media(image_path)
        payload = send_image(phone, media_id, message or None)
        return extract_message_id(payload)
    if message:
        payload = send_text(phone, message)
        return extract_message_id(payload)
    raise WhatsAppSendError("Post has no message or image")


async def send_scheduled_post_async(post: dict[str, Any]) -> str | None:
    if WHATSAPP_PROVIDER == "web":
        import asyncio
        return await asyncio.to_thread(send_via_baileys, post)
    return send_scheduled_post(post)


def send_via_baileys(post: dict[str, Any]) -> str | None:
    from app.services.whatsapp_store import get_recipient
    rec = get_recipient(post.get("recipient_id"))
    
    if rec:
        target = (rec.get("phone") or "").strip()
    else:
        target = (post.get("recipient_phone") or "").strip()
        
    if not target or (not any(x in target for x in ["http", "channel", "@"]) and not target.replace("+", "").isdigit()):
        raise WhatsAppSendError(f"WhatsApp destination link is not configured for '{post.get('recipient_name')}' yet. Please click the orange warning icon in the left channel list to save its invite link.")

    try:
        url = f"{WHATSAPP_SERVICE_URL}/send"
        data = {
            "target": target,
            "target_name": (post.get("recipient_name") or "").strip(),
            "message": (post.get("message") or "").strip()
        }
        
        image_path = post.get("image_path")
        if image_path and os.path.exists(image_path):
            import mimetypes
            mime_type, _ = mimetypes.guess_type(image_path)
            if not mime_type:
                # Fallback based on extension or default to image/jpeg
                ext = os.path.splitext(image_path)[1].lower()
                if ext in ['.gif']:
                    mime_type = 'image/gif'
                elif ext in ['.mp4']:
                    mime_type = 'video/mp4'
                else:
                    mime_type = 'image/jpeg'
                    
            with open(image_path, "rb") as f:
                files = {"image": (os.path.basename(image_path), f, mime_type)}
                resp = requests.post(url, data=data, files=files, timeout=60)
        else:
            resp = requests.post(url, data=data, timeout=30)
            
        if not resp.ok:
            err = resp.text
            try:
                err = resp.json().get("error", err)
            except ValueError:
                pass
            raise WhatsAppSendError(f"Baileys send failed ({resp.status_code}): {err}")
            
        result = resp.json()
        if result.get("success"):
            return f"baileys:{result.get('messageId')}"
        raise WhatsAppSendError(f"Baileys unexpected response: {result}")
    except Exception as exc:
        raise WhatsAppSendError(f"WhatsApp Baileys send failed: {exc}") from exc
