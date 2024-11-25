from celery import Celery
import requests

# Your existing Celery setup
celery = Celery('tasks')
celery.conf.broker_url = 'your_redis_url'
celery.conf.result_backend = 'your_redis_url'

@celery.task
def count_subscribers(headers, date):
    """Count subscribers up to a given date"""
    print(f"Starting count for {date}")
    endpoint = "https://api.convertkit.com/v4/subscribers"
    total_subscribers = 0
    next_cursor = None
    
    while True:
        params = {
            "created_before": f"{date}T23:59:59Z",
            "per_page": 5000
        }
        if next_cursor:
            params["cursor"] = next_cursor
            
        print(f"Making API request with params: {params}")
        response = requests.get(endpoint, headers=headers, params=params)
        
        if response.status_code != 200:
            print(f"Error response: {response.text}")
            break
            
        data = response.json()
        subscribers = data.get('subscribers', [])
        total_subscribers += len(subscribers)
        
        print(f"Current count: {total_subscribers}")
        
        next_cursor = data.get('meta', {}).get('next_cursor')
        if not next_cursor:
            break
    
    print(f"Final count for {date}: {total_subscribers}")
    return total_subscribers 