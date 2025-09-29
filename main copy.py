    from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.messages import GetScheduledHistoryRequest
import os

# Initialize FastAPI app
app = FastAPI(title="Post Statistics API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  # Add your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_id = os.getenv("TELEGRAM_API_ID")
api_hash = os.getenv("TELEGRAM_API_HASH") 
session_string = os.getenv("TELEGRAM_SESSION_STRING")

CHANNELS = {
    "1": {"username": "@amazonindiaassociates", "name": "Amazon India Associates"},
    "2": {"username": "@Amazon_Associates_FashionBeauty", "name": "Amazon Associates FashionBeauty"},
    "3": {"username": "@Amazon_Associates_HomeKitchen", "name": "Amazon Associates HomeKitchen"},
    "4": {"username": "@Amazon_Associates_Consumables", "name": "Amazon Associates Consumables"},
}

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "Post Statistics API is running", "status": "healthy"}

@app.get("/api/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "total_channels": len(CHANNELS),
        "api_configured": bool(api_id and api_hash and session_string)
    }

@app.get("/api/channels")
async def get_available_channels():
    """Get list of available channels for selection"""
    channels_list = []
    for channel_id, data in CHANNELS.items():
        channels_list.append({
            "id": channel_id,
            "username": data["username"],
            "name": data.get("name", data["username"].replace("@", "").title())
        })
    
    return {
        "status": "success",
        "channels": channels_list,
        "total": len(channels_list)
    }

@app.get("/api/posts-summary")
async def get_posts_summary(
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    channels: str = Query(None, description="Comma-separated channel IDs")
):
    """
    Get live and scheduled post counts for a specific date.
    Returns channel-wise breakdown with totals for that day only.
    
    Example: /api/posts-summary?date=2025-09-29&channels=1,2,3
    """

    if not all([api_id, api_hash, session_string]):
        raise HTTPException(
            status_code=500, 
            detail="Telegram API not properly configured. Check environment variables."
        )
    
    results = []
    
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d")
        start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
        end_of_day = target_date.replace(hour=23, minute=59, second=59, microsecond=999999, tzinfo=timezone.utc)
        
        print(f"📅 Fetching posts for date: {date}")
        print(f"   Start: {start_of_day}")
        print(f"   End: {end_of_day}")
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    # Filter channels if specified
    target_channels = CHANNELS
    if channels:
        channel_ids = [id.strip() for id in channels.split(",")]
        target_channels = {k: v for k, v in CHANNELS.items() if k in channel_ids}
        print(f"🎯 Filtering to channels: {list(target_channels.keys())}")
    
    try:
        async with TelegramClient(StringSession(session_string), api_id, api_hash) as client:
            print("🔗 Connected to Telegram")
            
            for channel_id, data in target_channels.items():
                username = data["username"]
                try:
                    print(f"📊 Processing channel: {username}")
                    entity = await client.get_entity(username)
                    
                    # Count LIVE posts for this specific date
                    live_count = 0
                    
                    # Get messages for the specific date
                    async for message in client.iter_messages(
                        entity,
                        limit=None,
                        reverse=False
                    ):
                        # Convert message date to UTC if needed
                        msg_date = message.date
                        if msg_date.tzinfo is None:
                            msg_date = msg_date.replace(tzinfo=timezone.utc)
                        elif msg_date.tzinfo != timezone.utc:
                            msg_date = msg_date.astimezone(timezone.utc)
                        
                        # Check if message is within target date range
                        if msg_date >= start_of_day and msg_date <= end_of_day:
                            live_count += 1
                        elif msg_date < start_of_day:
                            # We've gone past our target date
                            break
                    
                    # Count SCHEDULED posts for this specific date
                    scheduled_count = 0
                    try:
                        scheduled_result = await client(
                            GetScheduledHistoryRequest(peer=entity, hash=0)
                        )
                        
                        if hasattr(scheduled_result, 'messages'):
                            for msg in scheduled_result.messages:
                                sched_date = msg.date
                                if sched_date.tzinfo is None:
                                    sched_date = sched_date.replace(tzinfo=timezone.utc)
                                elif sched_date.tzinfo != timezone.utc:
                                    sched_date = sched_date.astimezone(timezone.utc)
                                
                                if sched_date >= start_of_day and sched_date <= end_of_day:
                                    scheduled_count += 1
                        
                    except Exception as sched_err:
                        print(f"⚠️ Could not fetch scheduled posts for {username}: {sched_err}")
                    
                    results.append({
                        "channel_id": channel_id,
                        "channel_username": username,
                        "live_posts": live_count,
                        "scheduled_posts": scheduled_count,
                    })
                    
                    print(f"✅ {username}: Live = {live_count}, Scheduled = {scheduled_count}")
                    
                except Exception as e:
                    print(f"⚠️ Failed to get data for {username}: {e}")
                    results.append({
                        "channel_id": channel_id,
                        "channel_username": username,
                        "live_posts": 0,
                        "scheduled_posts": 0,
                        "error": str(e)
                    })
    
    except Exception as client_err:
        print(f"❌ Telegram client error: {client_err}")
        raise HTTPException(status_code=500, detail=f"Failed to connect to Telegram: {str(client_err)}")
    
    # Calculate totals
    total_live = sum(ch.get("live_posts", 0) for ch in results)
    total_scheduled = sum(ch.get("scheduled_posts", 0) for ch in results)
    
    return {
        "status": "success",
        "date": date,
        "channels": results,
        "total_channels": len(results),
        "totals": {
            "live_posts": total_live,
            "scheduled_posts": total_scheduled,
            "total_posts": total_live + total_scheduled
        }
    }

@app.get("/api/posts-range")
async def get_posts_range(
    start_date: str = Query(..., description="Start date in YYYY-MM-DD format"),
    end_date: str = Query(..., description="End date in YYYY-MM-DD format"),
    channels: str = Query(None, description="Comma-separated channel IDs")
):
    """
    Get posts for a date range with optional channel filtering.
    
    Example: /api/posts-range?start_date=2025-09-01&end_date=2025-09-30&channels=1,2
    """
    
    if not all([api_id, api_hash, session_string]):
        raise HTTPException(
            status_code=500, 
            detail="Telegram API not properly configured"
        )
    
    results = []
    
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        end = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
        
        if start > end:
            raise HTTPException(status_code=400, detail="start_date must be before end_date")
            
        # Safety check for large date ranges
        date_diff = (end - start).days
        if date_diff > 31:
            raise HTTPException(status_code=400, detail="Date range cannot exceed 31 days")
            
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    # Filter channels if specified
    target_channels = CHANNELS
    if channels:
        channel_ids = [id.strip() for id in channels.split(",")]
        target_channels = {k: v for k, v in CHANNELS.items() if k in channel_ids}
    
    try:
        async with TelegramClient(StringSession(session_string), api_id, api_hash) as client:
            for channel_id, data in target_channels.items():
                username = data["username"]
                try:
                    entity = await client.get_entity(username)
                    
                    # Count live posts in range
                    live_count = 0
                    async for message in client.iter_messages(entity, limit=None, reverse=False):
                        msg_date = message.date
                        if msg_date.tzinfo is None:
                            msg_date = msg_date.replace(tzinfo=timezone.utc)
                        elif msg_date.tzinfo != timezone.utc:
                            msg_date = msg_date.astimezone(timezone.utc)
                        
                        if msg_date >= start and msg_date <= end:
                            live_count += 1
                        elif msg_date < start:
                            break
                    
                    # Count scheduled posts in range
                    scheduled_count = 0
                    try:
                        scheduled_result = await client(
                            GetScheduledHistoryRequest(peer=entity, hash=0)
                        )
                        
                        if hasattr(scheduled_result, 'messages'):
                            for msg in scheduled_result.messages:
                                sched_date = msg.date
                                if sched_date.tzinfo is None:
                                    sched_date = sched_date.replace(tzinfo=timezone.utc)
                                elif sched_date.tzinfo != timezone.utc:
                                    sched_date = sched_date.astimezone(timezone.utc)
                                
                                if sched_date >= start and sched_date <= end:
                                    scheduled_count += 1
                                    
                    except Exception as sched_err:
                        print(f"⚠️ Could not fetch scheduled posts for {username}: {sched_err}")
                    
                    results.append({
                        "channel_id": channel_id,
                        "channel_username": username,
                        "live_posts": live_count,
                        "scheduled_posts": scheduled_count,
                    })
                    
                except Exception as e:
                    print(f"⚠️ Failed to get data for {username}: {e}")
                    results.append({
                        "channel_id": channel_id,
                        "channel_username": username,
                        "live_posts": 0,
                        "scheduled_posts": 0,
                        "error": str(e)
                    })
    
    except Exception as client_err:
        raise HTTPException(status_code=500, detail=f"Failed to connect to Telegram: {str(client_err)}")
    
    # Calculate totals
    total_live = sum(ch.get("live_posts", 0) for ch in results)
    total_scheduled = sum(ch.get("scheduled_posts", 0) for ch in results)
    
    return {
        "status": "success",
        "start_date": start_date,
        "end_date": end_date,
        "channels": results,
        "total_channels": len(results),
        "date_range_days": date_diff + 1,
        "totals": {
            "live_posts": total_live,
            "scheduled_posts": total_scheduled,
            "total_posts": total_live + total_scheduled
        }
    }

# Run with: uvicorn main:app --reload --host 0.0.0.0 --port 8000
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)