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
    page = 1
    
    try:
        # First request to check response format
        params = {
            "created_before": f"{date}T23:59:59Z",
            "per_page": 5000,
            "page": page,
            "sort_order": "desc"  # Get newest first
        }
            
        print(f"Making API request with params: {params}")
        response = requests.get(endpoint, headers=headers, params=params)
        response.raise_for_status()  # Raise exception for bad status codes
            
        data = response.json()
        
        # Check if we got the expected data structure
        if not isinstance(data, dict) or 'subscribers' not in data:
            print(f"Unexpected response format: {data}")
            return 0
            
        subscribers = data.get('subscribers', [])
        total_subscribers = len(subscribers)
        
        # If we got less than per_page results, we're done
        if len(subscribers) < 5000:
            print(f"Final count for {date}: {total_subscribers}")
            return total_subscribers
            
        # Otherwise, keep paginating
        while True:
            page += 1
            params['page'] = page
            
            print(f"Making API request with params: {params}")
            response = requests.get(endpoint, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            subscribers = data.get('subscribers', [])
            
            if not subscribers:  # No more results
                break
                
            total_subscribers += len(subscribers)
            print(f"Current count: {total_subscribers}")
            
            # Optional: Add a small delay to avoid rate limits
            time.sleep(0.2)
            
    except requests.exceptions.RequestException as e:
        print(f"Error making request: {e}")
        return 0
    except Exception as e:
        print(f"Unexpected error: {e}")
        return 0
        
    print(f"Final count for {date}: {total_subscribers}")
    return total_subscribers