from celery import Celery
import requests 
import os
from dotenv import load_dotenv
import time

load_dotenv()

# Get Redis URL from environment variable - use REDISCLOUD_URL
REDIS_URL = os.environ.get('REDISCLOUD_URL', 'redis://localhost:6379/0')

# Print for debugging
print(f"Using Redis URL: {REDIS_URL}")

# Configure Celery
celery = Celery('tasks')
celery.conf.update(
    broker_url=REDIS_URL,
    result_backend=REDIS_URL,
    broker_connection_retry_on_startup=True
)

@celery.task
def count_subscribers(headers, date):
    """Count subscribers up to a given date"""
    print(f"Starting count for {date}")
    endpoint = "https://api.convertkit.com/v4/subscribers"
    total_subscribers = 0
    cursor = None
    
    while True:
        params = {
            "created_before": f"{date}T23:59:59Z",
            "per_page": 5000
        }
        
        # Add cursor to params if we have one
        if cursor:
            params["cursor"] = cursor
            
        print(f"Making API request with params: {params}")
        response = requests.get(endpoint, headers=headers, params=params)
        
        if not response.ok:
            print(f"Error response: {response.text}")
            break
            
        data = response.json()
        subscribers = data.get('subscribers', [])
        total_subscribers += len(subscribers)
        
        print(f"Current count: {total_subscribers}")
        
        # Get the next cursor from the meta data
        cursor = data.get('meta', {}).get('next_cursor')
        if not cursor:
            break
            
        # Optional: Add a small delay to avoid rate limits
        time.sleep(0.5)
    
    print(f"Final count for {date}: {total_subscribers}")
    return total_subscribers 