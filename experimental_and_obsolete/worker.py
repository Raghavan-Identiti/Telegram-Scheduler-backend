# worker.py
from scheduler import scheduler
import asyncio

if __name__ == "__main__":
    try:
        print("🚀 Scheduler Worker Running...")
        scheduler.start()
        asyncio.get_event_loop().run_forever()
    except (KeyboardInterrupt, SystemExit):
        print("🛑 Scheduler Worker Stopped")

# TELEGRAM_UTILS.PY :
# async def send_telegram_message(image_path: str, post_text: str, post_number: int = 1, category: str = None, target_channel: str = None,schedule_time: datetime = None):
#     if not client.is_connected():
#         await client.connect()

#     if not await client.is_user_authorized():
#         raise Exception("Telegram client not authorized")
#         await client.start(phone)
    
#     print("🧪 post_text type:", type(post_text))
#     print("🧪 post_text value:", post_text)
#     if isinstance(post_text, dict):
#         message = post_text.get("text", "").strip()
#     elif isinstance(post_text, str):
#         message = post_text.strip()
#     else:
#         message = ""

#     message = post_text.strip() if post_text else ""
#     message_parts = split_long_message(message) if message else []
#     status = ''

#     try:
#         entity = await client.get_entity(target_channel)
#         if image_path and message_parts:
#             caption = message_parts[0][:1024]
#             await client.send_file(entity, image_path, caption=caption, schedule=schedule_time)
#             for part in message_parts[1:]:
#                 await client.send_message(entity, part, schedule=schedule_time)
#             status = f'Scheduled Image + Text at {schedule_time}'

#         elif image_path and not message_parts:
#             await client.send_file(entity, image_path, schedule=schedule_time)
#             status = f'Scheduled Image only at {schedule_time}'

#         elif not image_path and message_parts:
#             for part in message_parts:
#                 await client.send_message(entity, part, schedule=schedule_time)
#             status = f'Scheduled Text only at {schedule_time}'

#         else:
#             status = f'Nothing to send for post {post_number}'

#     except Exception as e:
#         status = f'Failed: {str(e)}'

#     log_entry = pd.DataFrame([{
#         'filename': os.path.basename(image_path) if image_path else 'N/A',
#         'post_number': post_number,
#         'category': category if category else 'Uncategorized',
#         'message': message[:100] if message else '',
#         'status': status,
#         'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
#     }])

#     os.makedirs("logs", exist_ok=True)
#     logfile = "logs/messages.xlsx"

#     if os.path.exists(logfile):
#         existing = pd.read_excel(logfile)
#         combined = pd.concat([existing, log_entry], ignore_index=True)
#         combined.to_excel(logfile, index=False)
#     else:
#         log_entry.to_excel(logfile, index=False)

#     print(f"✅ {status}: Post {post_number}")
