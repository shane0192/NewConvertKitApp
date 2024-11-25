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
    
    # Make a single request with a large page size and get total from metadata
    params = {
        "created_before": f"{date}T23:59:59Z",
        "per_page": 1  # We only need the metadata
    }
    
    print(f"Making initial API request for metadata")
    response = requests.get(endpoint, headers=headers, params=params)
    
    if not response.ok:
        print(f"Error response: {response.text}")
        return 0
        
    data = response.json()
    total_count = data.get('meta', {}).get('total_count', 0)
    print(f"Total count from metadata: {total_count}")
    
    return total_count 