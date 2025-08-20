#telegram_scheduler.py

import asyncio
from telethon import TelegramClient
from datetime import datetime, timezone
from zoneinfo import ZoneInfo  # Python 3.9+
import os
from dotenv import load_dotenv
import logging
from telethon.errors import SessionPasswordNeededError

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

    def create_schedule_datetime(self, date_str=None, time_str=None):
        """
        Returns a naive UTC datetime object for Telegram scheduling.
        Requires both `date_str` and `time_str` (in 24-hour format).
        """
        try:
            if not date_str or not time_str:
                raise ValueError("⚠️ Both date and time must be provided.")

            # Parse the date and time
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            time_obj = datetime.strptime(time_str, '%H:%M').time()

            # Combine and convert to UTC
            local_tz = ZoneInfo("Asia/Kolkata")
            local_dt = datetime.combine(date_obj, time_obj).replace(tzinfo=local_tz)
            utc_dt = local_dt.astimezone(timezone.utc)

            return utc_dt.replace(tzinfo=None)
        except Exception as e:
            logger.error(f"❌ Invalid datetime inputs: date_str={date_str}, time_str={time_str} — {e}")
            raise
