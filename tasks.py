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

@celery.task(bind=True, max_retries=3)
def count_subscribers(self, headers, date):
    """Count subscribers up to a given date"""
    print(f"Starting count for {date}")
    endpoint = "https://api.convertkit.com/v4/subscribers"
    
    # Fix headers format
    if isinstance(headers, dict) and 'Authorization' in headers:
        api_headers = headers
    else:
        api_headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {headers}" if isinstance(headers, str) else None
        }
    
    print(f"Using headers: {api_headers}")
    
    try:
        # Make initial request with just one result to get total count
        params = {
            'per_page': 1,
            'page': 1,
            'sort_order': 'desc'
        }
        
        # Add appropriate date filter
        if 'T00:00:00Z' in date:
            params['created_after'] = date
        else:
            params['created_before'] = date
            
        print(f"Making API request with params: {params}")
        
        # Add timeout to prevent hanging
        response = requests.get(
            endpoint, 
            headers=api_headers, 
            params=params,
            timeout=30  # 30 second timeout
        )
        response.raise_for_status()
        
        data = response.json()
        
        # Get total count from metadata
        if 'meta' in data and 'total_count' in data['meta']:
            total_count = data['meta']['total_count']
            print(f"Got total count from meta: {total_count}")
            return total_count
            
        raise ValueError("No meta.total_count in API response")
            
    except requests.exceptions.Timeout:
        print("Request timed out")
        # Retry with exponential backoff
        self.retry(countdown=2 ** self.request.retries)
        
    except requests.exceptions.RequestException as e:
        print(f"Error making request: {e}")
        if hasattr(e.response, 'text'):
            print(f"Response text: {e.response.text}")
        # Retry with exponential backoff
        self.retry(countdown=2 ** self.request.retries)
        
    except Exception as e:
        print(f"Unexpected error: {e}")
        return 0