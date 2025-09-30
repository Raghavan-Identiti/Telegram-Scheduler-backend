import requests
from typing import Any, List

API_URL = "https://quic.ly/api/v1/analytics/cross-account-clicks"
API_KEY = "f073c95a0227414d8e053fdfa19ece0dbe29ea9a8b3fb08e2c8186fabce64bb4"

def get_clicks(shortened_url: str, date: str) -> Any:
    """
    Fetch clicks data from Quic.ly API for a given URL and date.
    """
    headers = {
        "X-API-KEY": API_KEY, 
        "Content-Type": "application/json"
    }

    payload = {
        "shortened_url": shortened_url,
        "date": date
    }

    try:
        response = requests.post(API_URL, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching clicks for {shortened_url}: {e}")
        if e.response is not None:
            print("Response content:", e.response.text)
        return None

# if __name__ == "__main__":
#     urls: List[str] = [
#         "http://amzaff.in/mFKkfcZ",
#     ]
#     date = "2025-09-29"  

#     for url in urls:
#         clicks_data = get_clicks(url, date)
#         print(f"\nResults for {url}:")
#         if clicks_data:
#             for entry in clicks_data:
#                 account = entry.get("account")
#                 clicks_count = entry.get("clicks")
#                 shortened = entry.get("shortened_url")
#                 date = entry.get("date")
#                 print(f"Date :{date}")
#                 print(f"{account}: {clicks_count} clicks ({shortened})")
#         else:
#             print("No clicks data received.")
