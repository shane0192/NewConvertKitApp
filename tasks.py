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
    
    # Fix headers format to match the rest of the application
    if isinstance(headers, dict) and 'Authorization' in headers:
        api_headers = headers
    else:
        api_headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {headers}" if isinstance(headers, str) else None
        }
    
    print(f"Using headers: {api_headers}")
    total_subscribers = 0
    page = 1
    
    try:
        # For end date, we want all subscribers before that date
        # For start date, we want all subscribers after that date
        is_start_date = 'T00:00:00Z' in date
        
        params = {
            'per_page': 1000,  # API seems to limit to 1000
            'page': page,
            'sort_order': 'desc'  # Get newest first
        }
        
        if is_start_date:
            params['created_after'] = f"{date}"
        else:
            params['created_before'] = f"{date}"
            
        print(f"Making API request with params: {params}")
        response = requests.get(endpoint, headers=api_headers, params=params)
        response.raise_for_status()
        
        data = response.json()
        print(f"Response data: {data}")  # Debug print
        
        # Check if we got the expected data structure
        if not isinstance(data, dict):
            print(f"Unexpected response format: {data}")
            return 0
            
        # Get total from meta if available
        if 'meta' in data and 'total_count' in data['meta']:
            total_count = data['meta']['total_count']
            print(f"Got total count from meta: {total_count}")
            return total_count
            
        # Otherwise count manually
        subscribers = data.get('subscribers', [])
        if not subscribers:
            print("No subscribers found in response")
            return 0
            
        total_subscribers = len(subscribers)
        
        # Keep paginating while we get full pages
        while len(subscribers) == params['per_page']:
            page += 1
            params['page'] = page
            
            print(f"Making API request with params: {params}")
            response = requests.get(endpoint, headers=api_headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            subscribers = data.get('subscribers', [])
            total_subscribers += len(subscribers)
            print(f"Current count: {total_subscribers}")
            
            # Add a small delay to avoid rate limits
            time.sleep(0.1)
            
    except requests.exceptions.RequestException as e:
        print(f"Error making request: {e}")
        if hasattr(e.response, 'text'):
            print(f"Response text: {e.response.text}")
        return 0
    except Exception as e:
        print(f"Unexpected error: {e}")
        return 0
        
    print(f"Final count for {date}: {total_subscribers}")
    return total_subscribers