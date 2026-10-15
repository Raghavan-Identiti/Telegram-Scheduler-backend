import asyncio
from typing import Any, Dict, List, Optional
import requests
import httpx

API_URL = "https://quic.ly/api/v1/analytics/cross-account-clicks"
API_KEY = "f073c95a0227414d8e053fdfa19ece0dbe29ea9a8b3fb08e2c8186fabce64bb4"

HEADERS = {
    "X-API-KEY": API_KEY,
    "Content-Type": "application/json"
}

_clicks_cache: Dict[str, Any] = {}

def get_clicks(shortened_url: str, date: str) -> Any:
    """Synchronous get_clicks for backwards compatibility"""
    cache_key = f"{shortened_url}::{date}"
    if cache_key in _clicks_cache:
        return _clicks_cache[cache_key]

    payload = {"shortened_url": shortened_url, "date": date}
    try:
        response = requests.post(API_URL, json=payload, headers=HEADERS, timeout=8)
        if response.status_code == 200:
            data = response.json()
            _clicks_cache[cache_key] = data
            return data
        return None
    except Exception as e:
        print(f"Error fetching clicks for {shortened_url}: {e}")
        return None

async def get_clicks_async(client: httpx.AsyncClient, shortened_url: str, date: str) -> Optional[List[Dict[str, Any]]]:
    """Asynchronous single URL click fetcher with cache"""
    cache_key = f"{shortened_url}::{date}"
    if cache_key in _clicks_cache:
        return _clicks_cache[cache_key]

    payload = {"shortened_url": shortened_url, "date": date}
    try:
        response = await client.post(API_URL, json=payload, headers=HEADERS, timeout=8.0)
        if response.status_code == 200:
            data = response.json()
            _clicks_cache[cache_key] = data
            return data
        return None
    except Exception:
        return None

async def get_batch_clicks_data(
    urls: List[str],
    date_str: str,
    max_concurrency: int = 15
) -> Dict[str, Dict[str, int]]:
    """Parallel batch clicks fetcher across all unique URLs"""
    unique_urls = list(set([u.strip() for u in urls if u and u.strip()]))
    if not unique_urls:
        return {}

    semaphore = asyncio.Semaphore(max_concurrency)
    results_map: Dict[str, Dict[str, int]] = {}

    limits = httpx.Limits(max_keepalive_connections=20, max_connections=30)
    async with httpx.AsyncClient(limits=limits, timeout=10.0) as client:
        async def fetch_one(url: str):
            async with semaphore:
                click_data = await get_clicks_async(client, url, date_str)
                tg_clicks = 0
                wa_clicks = 0
                if click_data and isinstance(click_data, list):
                    for entry in click_data:
                        account = str(entry.get("account", "")).lower()
                        count = int(entry.get("clicks", 0) or 0)
                        if "telegram" in account or "tg" in account:
                            tg_clicks += count
                        elif "whatsapp" in account or "wa" in account:
                            wa_clicks += count
                        else:
                            tg_clicks += count
                results_map[url] = {
                    "telegram_clicks": tg_clicks,
                    "whatsapp_clicks": wa_clicks
                }

        await asyncio.gather(*[fetch_one(url) for url in unique_urls], return_exceptions=True)

    return results_map
