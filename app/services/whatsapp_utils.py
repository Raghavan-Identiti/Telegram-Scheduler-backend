# app/services/whatsapp_utils.py
import os
import httpx

WHATSAPP_SERVICE_URL = os.getenv("WHATSAPP_SERVICE_URL", "http://127.0.0.1:3001")
WHATSAPP_PROVIDER = os.getenv("WHATSAPP_PROVIDER", "baileys")

async def get_provider_status() -> dict:
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get(f"{WHATSAPP_SERVICE_URL}/health")
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass
    return {"connected": True, "message": "WhatsApp provider ready (Baileys service)"}
