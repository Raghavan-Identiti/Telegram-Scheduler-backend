import asyncio
from telethon import TelegramClient
from datetime import datetime, timezone, timedelta
import os
from dotenv import load_dotenv
import logging
from telethon.errors import FloodWaitError, SessionPasswordNeededError

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Validate critical environment vars
api_id = os.getenv('TELEGRAM_API_ID')
api_hash = os.getenv('TELEGRAM_API_HASH')
phone_number = os.getenv('TELEGRAM_PHONE_NUMBER')

if not all([api_id, api_hash, phone_number]):
    raise EnvironmentError("Missing TELEGRAM_API_ID, TELEGRAM_API_HASH, or TELEGRAM_PHONE_NUMBER in .env file.")

# Convert api_id to int if needed
api_id = int(api_id)

class TelegramScheduler:
    def __init__(self):
        self.client = TelegramClient('scheduler_session', api_id, api_hash)

    async def connect(self):
        try:
            await self.client.start(phone=phone_number)
            if not await self.client.is_user_authorized():
                logger.warning("Authorization required. Please check your Telegram credentials.")
                await self.client.send_code_request(phone_number)
                raise RuntimeError("Manual authorization step required.")
        except SessionPasswordNeededError:
            logger.error("Two-step verification is enabled on this account. Manual input required.")
            raise
        except Exception as e:
            logger.exception("Failed to connect to Telegram.")
            raise

    async def send_message_with_image(self, channel_username, message_text, image_path=None, schedule_date=None):
        try:
            await self.connect()

            channel = await self.client.get_entity(channel_username)

            if image_path and os.path.exists(image_path):
                await self.client.send_file(
                    entity=channel,
                    file=image_path,
                    caption=message_text,
                    schedule=schedule_date
                )
                msg_type = "scheduled" if schedule_date else "sent"
                logger.info(f"✅ Message with image {msg_type} to {channel_username} at {schedule_date}")
            else:
                await self.client.send_message(
                    entity=channel,
                    message=message_text,
                    schedule=schedule_date
                )
                msg_type = "scheduled" if schedule_date else "sent"
                logger.info(f"✅ Text message {msg_type} to {channel_username} at {schedule_date}")

        except FloodWaitError as e:
            logger.error(f"⏳ Flood wait error: wait for {e.seconds} seconds.")
        except Exception as e:
            logger.exception(f"❌ Error sending message: {e}")
        finally:
            await self.client.disconnect()

    async def schedule_message(self, channel_username, message_text, image_path=None, schedule_datetime=None):
        try:
            if schedule_datetime:
                await self.send_message_with_image(channel_username, message_text, image_path, schedule_datetime)
            else:
                await self.send_message_with_image(channel_username, message_text, image_path)
        except Exception as e:
            logger.error(f"❌ Failed to schedule message: {e}")

    def create_schedule_datetime(self, date_str=None, time_str=None):
        """
        Returns naive UTC datetime (Telegram expects this format for scheduling).
        """
        try:
            if date_str:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            else:
                date_obj = datetime.now().date()

            time_obj = datetime.strptime(time_str, '%H:%M').time()

            # Local time
            local_dt = datetime.combine(date_obj, time_obj)
            local_with_tz = local_dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
            utc_dt = local_with_tz.astimezone(timezone.utc)

            return utc_dt.replace(tzinfo=None)
        except Exception as e:
            logger.error(f"❌ Invalid datetime inputs: date_str={date_str}, time_str={time_str} — {e}")
            raise

# ----------------------------
# ✅ Example usage helpers
# ----------------------------

async def send_immediate_message(channel_username, text, image_path=None):
    scheduler = TelegramScheduler()
    await scheduler.send_message_with_image(channel_username, text, image_path)

async def schedule_message_for_time(channel_username, text, image_path=None, date_str=None, time_str=None):
    scheduler = TelegramScheduler()
    schedule_datetime = scheduler.create_schedule_datetime(date_str, time_str)
    await scheduler.schedule_message(channel_username, text, image_path, schedule_datetime)
    return scheduler

