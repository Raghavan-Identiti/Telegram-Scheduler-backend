# app/services/whatsapp_worker.py
import asyncio
from app.services.whatsapp_store import init_db

worker_task = None
is_running = False

async def worker_loop():
    global is_running
    while is_running:
        try:
            # Poll pending whatsapp posts
            await asyncio.sleep(15)
        except asyncio.CancelledError:
            break
        except Exception as e:
            await asyncio.sleep(5)

def start_worker():
    global worker_task, is_running
    init_db()
    if not is_running:
        is_running = True
        try:
            loop = asyncio.get_event_loop()
            worker_task = loop.create_task(worker_loop())
        except Exception:
            pass

async def stop_worker():
    global worker_task, is_running
    is_running = False
    if worker_task:
        worker_task.cancel()
