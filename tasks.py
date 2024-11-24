from celery import Celery
import os
import requests

# Get Redis URL from Heroku config
redis_url = os.getenv('REDISCLOUD_URL', 'redis://localhost:6379/0')

# Setup Celery with Redis
celery = Celery('tasks', broker=redis_url, backend=redis_url)

@celery.task
def count_subscribers(api_key, date_str):
    """Background task to count all subscribers"""
    print(f"Starting count for {date_str}")
    total_subscribers = 0
    cursor = None
    BASE_URL = "https://api.convertkit.com/v3/"
    
    while True:
        params = {
            'from': date_str,
            'to': date_str,
            'per_page': 1000
        }
        if cursor:
            params['after'] = cursor
            
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        try:
            response = requests.get(
                f"{BASE_URL}subscribers",
                headers=headers,
                params=params
            )
            
            if response.status_code != 200:
                print(f"Error response: {response.text}")
                break
                
            data = response.json()
            subscribers = data.get('subscribers', [])
            total_subscribers += len(subscribers)
            
            # Update progress
            print(f"Current count for {date_str}: {total_subscribers}")
            
            pagination = data.get('pagination', {})
            if not pagination.get('has_next_page'):
                break
            cursor = pagination.get('end_cursor')
            
        except Exception as e:
            print(f"Error fetching subscribers: {str(e)}")
            break
    
    print(f"Final count for {date_str}: {total_subscribers}")
    return total_subscribers 