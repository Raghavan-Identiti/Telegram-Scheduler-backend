import asyncio
import os
from contextlib import suppress

from whatsapp_store import claim_due_posts, init_db, mark_failed, mark_sent
from whatsapp_utils import send_scheduled_post_async
_worker_task: asyncio.Task | None = None
POLL_SECONDS = int(os.getenv("WHATSAPP_SCHEDULER_POLL_SECONDS", "5"))


async def _send_one(post: dict):
    try:
        provider_message_id = await send_scheduled_post_async(post)
        mark_sent(post["id"], provider_message_id)
        print(f"WhatsApp post {post['id']} sent")
    except Exception as exc:
        mark_failed(post["id"], str(exc))
        print(f"WhatsApp post {post['id']} failed: {exc}")


async def worker_loop():
    init_db()
    while True:
        posts = claim_due_posts(limit=5)
        if posts:
            await asyncio.gather(*(_send_one(post) for post in posts))
        await asyncio.sleep(POLL_SECONDS)


def start_worker():
    global _worker_task
    if _worker_task and not _worker_task.done():
        return
    _worker_task = asyncio.create_task(worker_loop())
    print("WhatsApp scheduler worker started")


async def stop_worker():
    global _worker_task
    if not _worker_task:
        return
    _worker_task.cancel()
    with suppress(asyncio.CancelledError):
        await _worker_task
    _worker_task = None
