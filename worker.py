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
