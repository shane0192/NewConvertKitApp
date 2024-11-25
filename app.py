import requests
import json
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
import time
from requests_oauthlib import OAuth2Session
import os
from dotenv import load_dotenv
import inspect
from tasks import count_subscribers

print("=== Starting Flask App Setup ===")
registered_routes = set()

def register_route(route, function_name):
    if route in registered_routes:
        print(f"WARNING: Duplicate route detected! {route} -> {function_name}")
    registered_routes.add(route)
    print(f"Registered route: {route} -> {function_name}")

load_dotenv()  # Load environment variables

BASE_URL = "https://api.convertkit.com/v4/"
PER_PAGE_PARAM = 5000
PAPERBOY_START_DATE = "2024-10-29T00:00:00Z"  # Your start date with Paperboy
REDIRECT_URI = 'https://convertkit-analytics-941b0603483f.herokuapp.com/oauth/callback'

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key')

# ConvertKit OAuth settings
CLIENT_ID = os.getenv('CONVERTKIT_CLIENT_ID')
CLIENT_SECRET = os.getenv('CONVERTKIT_CLIENT_SECRET')
AUTHORIZATION_BASE_URL = 'https://app.convertkit.com/oauth/authorize'
TOKEN_URL = 'https://api.convertkit.com/oauth/token'
REDIRECT_URI = 'https://convertkit-analytics-941b0603483f.herokuapp.com/oauth/callback'

# Required for local development with HTTPS
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Add this after app = Flask(__name__) but before any routes
@app.context_processor
def utility_processor():
    def calculate_percentage(part, whole):
        return round((part / whole) * 100, 1) if whole > 0 else 0
    return dict(calculate_percentage=calculate_percentage)

# Register the calculate_percentage function as a template filter
@app.template_filter('calculate_percentage')
def calculate_percentage_filter(part, whole):
    return round((part / whole) * 100, 1) if whole > 0 else 0

# Function to get total subscribers added in a custom date range
def get_subscribers_last_x_days(start_date, end_date, api_key):
    endpoint = f"{BASE_URL}subscribers"
    total_subscribers = 0
    next_cursor = None
    per_page = 5000  # ConvertKit max
    
    while True:
        params = {
            "created_after": start_date,
            "created_before": end_date,
            "per_page": per_page
        }
        if next_cursor:
            params["cursor"] = next_cursor
            
        response = requests.get(endpoint, headers={"Accept": "application/json", "X-Kit-Api-Key": api_key}, params=params)
        if response.status_code != 200:
            break
            
        data = response.json()
        subscribers = data.get('subscribers', [])
        total_subscribers += len(subscribers)
        
        next_cursor = data.get('meta', {}).get('next_cursor')
        if not next_cursor:
            break
    
    return total_subscribers

# Function to get subscribers with a specific tag
def get_subscribers_by_tag(tag_name, api_key):
    tag_id = get_tag_id(tag_name, api_key)
    if tag_id is None:
        return 0
        
    total_subscribers = 0
    next_cursor = None
    per_page = 5000
    
    while True:
        params = {"per_page": per_page}
        if next_cursor:
            params["cursor"] = next_cursor
            
        response = requests.get(
            f"{BASE_URL}tags/{tag_id}/subscribers",
            headers={"Accept": "application/json", "X-Kit-Api-Key": api_key},
            params=params
        )
        
        if response.status_code != 200:
            break
            
        data = response.json()
        subscribers = data.get('subscribers', [])
        total_subscribers += len(subscribers)
        
        next_cursor = data.get('meta', {}).get('next_cursor')
        if not next_cursor:
            break
    
    return total_subscribers

# Function to get subscribers based on custom field 'rh_isref'
def get_subscribers_by_custom_field(field_name, field_value, api_key):
    print(f"\nFetching subscribers with {field_name}={field_value}")
    endpoint = f"{BASE_URL}subscribers"
    total_subscribers = 0
    next_cursor = None
    per_page = 5000  # ConvertKit maximum
    
    while True:
        # Build params dict with cursor if available
        params = {
            f"fields[{field_name}]": field_value,
            "per_page": per_page
        }
        if next_cursor:
            params["cursor"] = next_cursor
            
        print(f"Making request with params: {params}")  # Debug log
        
        response = requests.get(
            endpoint,
            headers={
                "Accept": "application/json",
                "X-Kit-Api-Key": api_key
            },
            params=params
        )
        
        if response.status_code != 200:
            print(f"Error fetching subscribers: {response.status_code}")
            break
            
        data = response.json()
        subscribers = data.get('subscribers', [])
        
        # Count subscribers that match our field value
        matching_subscribers = [
            s for s in subscribers 
            if s.get('fields', {}).get(field_name) == field_value
        ]
        current_batch = len(matching_subscribers)
        total_subscribers += current_batch
        
        # Get next cursor from meta data
        next_cursor = data.get('meta', {}).get('next_cursor')
        print(f"Fetched batch of {current_batch} matching subscribers. Total so far: {total_subscribers}")
        print(f"Next cursor: {next_cursor}")
        
        # If no next cursor, we've reached the end
        if not next_cursor:
            break
    
    print(f"Total subscribers with {field_name}={field_value}: {total_subscribers}")
    return total_subscribers

# Function to get the tag ID by name
def get_tag_id(tag_name, api_key):
    endpoint = f"{BASE_URL}tags"
    
    headers = {
        "Accept": "application/json",
        "X-Kit-Api-Key": api_key
    }
    
    response = requests.get(endpoint, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        for tag in data['tags']:
            if tag['name'] == tag_name:
                return tag['id']
        print(f"Tag '{tag_name}' not found.")
        return None
    else:
        print(f"Failed to get tags. Status Code: {response.status_code}")
        return None

# Add this new function to fetch available custom fields
def get_available_custom_fields(api_key):
    endpoint = f"{BASE_URL}custom_fields"
    
    headers = {
        "Accept": "application/json",
        "X-Kit-Api-Key": api_key
    }
    
    response = requests.get(endpoint, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        return [field['key'] for field in data['custom_fields']]
    else:
        print(f"Failed to fetch custom fields. Status Code: {response.status_code}")
        return []

print("\n=== Registering first index route ===")
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        try:
            # Get form data
            start_date = request.form['start_date']
            end_date = request.form['end_date']
            paperboy_date = request.form['paperboy_date']
            selected_tag = request.form.get('tag')
            
            # Add debug logging
            print(f"Form data: start={start_date}, end={end_date}, tag={selected_tag}")
            
            api_key = session.get('access_token')
            if not api_key:
                flash('Please authenticate first', 'error')
                return redirect(url_for('index'))

            # Set up parameters
            headers = {
                "Accept": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            
            # Use Celery for the long-running task
            task = count_subscribers.delay(api_key, start_date, end_date, paperboy_date, selected_tag)
            results = task.get(timeout=25)  # Wait up to 25 seconds for results
            
            return render_template('index.html', 
                                results=results,
                                authenticated=True,
                                tags=get_available_tags(api_key))
                                
        except Exception as e:
            print(f"Error in index route: {str(e)}")
            flash(f'An error occurred: {str(e)}', 'error')
            return redirect(url_for('index'))

def get_subscriber_counts(headers, total_params, tag_params, paperboy_params):
    """Get all subscriber counts with pagination"""
    base_url = "https://api.convertkit.com/v4/subscribers"
    results = {'total_subscribers': 0, 'tagged_subscribers': 0, 'paperboy_subscribers': 0}
    
    try:
        # Process each parameter set
        for params in [total_params, tag_params, paperboy_params]:
            count = 0
            page = 1
            
            while True:
                current_params = {**params, 'page': page, 'per_page': 1000}
                print(f"Fetching page {page} with params: {current_params}")  # Debug log
                
                response = requests.get(
                    base_url, 
                    headers=headers, 
                    params=current_params,
                    timeout=10
                )
                response.raise_for_status()
                data = response.json()
                
                if not data.get('subscribers'):
                    break
                    
                count += len(data['subscribers'])
                print(f"Current count: {count}")  # Debug log
                
                if len(data['subscribers']) < 1000:
                    break
                    
                page += 1
            
            # Assign count to appropriate result
            if params == total_params:
                results['total_subscribers'] = count
            elif params == tag_params and tag_params.get('filter[tags]'):
                results['tagged_subscribers'] = count
            elif params == paperboy_params:
                results['paperboy_subscribers'] = count
                
        print(f"Final results: {results}")  # Debug log
        return results
        
    except requests.exceptions.RequestException as e:
        print(f"API Error: {str(e)}")
        if hasattr(e, 'response'):
            print(f"Response: {e.response.text}")
        raise Exception("Error fetching subscriber data")

def get_available_tags(api_key):
    """Fetch all available tags"""
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    try:
        # Debug logging
        print("Fetching tags...")
        response = requests.get(
            "https://api.convertkit.com/v4/tags",
            headers=headers,
            params={'page': 1, 'per_page': 100}  # Start with first page
        )
        response.raise_for_status()
        data = response.json()
        print(f"Tags response: {data}")  # Debug logging
        
        if 'tags' in data:
            return data['tags']
        return []
        
    except Exception as e:
        print(f"Error fetching tags: {str(e)}")
        if hasattr(e, 'response'):
            print(f"Response: {e.response.text}")
        return []

def get_custom_field_id(field_key, api_key):
    endpoint = f"{BASE_URL}custom_fields"
    
    headers = {
        "Accept": "application/json",
        "X-Kit-Api-Key": api_key
    }
    
    response = requests.get(endpoint, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        for field in data['custom_fields']:
            if field['key'] == field_key:
                return field['id']
        print(f"Custom field with key '{field_key}' not found")
        return None
    else:
        print(f"Failed to get custom fields. Status Code: {response.status_code}")
        return None

def get_all_time_subscribers_by_tag(tag_name, api_key):
    tag_id = get_tag_id(tag_name, api_key)
    
    if tag_id is None:
        print(f"Tag '{tag_name}' not found.")
        return 0
    
    total_subscribers = 0
    current_cursor = None
    page_size = 500  # API enforces 500 per page
    
    print(f"Fetching all subscribers for tag '{tag_name}' (ID: {tag_id})...")
    
    while True:
        # Build params dict
        params = {"page_size": page_size}
        if current_cursor:
            params["after"] = current_cursor
            
        print(f"Making request with params: {params}")
        
        response = requests.get(
            f"{BASE_URL}tags/{tag_id}/subscribers",
            headers={
                "Accept": "application/json",
                "X-Kit-Api-Key": api_key
            },
            params=params
        )
        
        if response.status_code != 200:
            print(f"Error fetching subscribers: {response.status_code}")
            print(f"Response: {response.text}")
            break
            
        data = response.json()
        pagination = data.get('pagination', {})
        print(f"Pagination data: {pagination}")
        
        subscribers = data.get('subscribers', [])
        current_batch = len(subscribers)
        total_subscribers += current_batch
        
        print(f"Fetched batch of {current_batch} subscribers. Total so far: {total_subscribers}")
        
        # Check if there are more pages
        has_next_page = pagination.get('has_next_page', False)
        if not has_next_page:
            print("No more pages available")
            break
            
        # Get the end_cursor for the next request
        current_cursor = pagination.get('end_cursor')
        if not current_cursor:
            print("No cursor for next page")
            break
            
        print(f"Moving to next page with cursor: {current_cursor}")
        
        # Add a small delay to avoid rate limits
        time.sleep(0.5)
    
    print(f"Total subscribers for tag '{tag_name}': {total_subscribers}")
    return total_subscribers

def get_all_time_subscribers_by_custom_field(field_name, field_value, api_key):
    endpoint = f"{BASE_URL}subscribers"
    
    headers = {
        "Accept": "application/json",
        "X-Kit-Api-Key": api_key
    }
    
    params = {
        f"fields[{field_name}]": field_value
    }
    
    print(f"Querying all-time subscribers with params: {params}")
    response = requests.get(endpoint, headers=headers, params=params)
    
    if response.status_code == 200:
        data = response.json()
        subscriber_count = len([
            s for s in data['subscribers'] 
            if s.get('fields', {}).get(field_name) == field_value
        ])
        print(f"Found {subscriber_count} all-time subscribers with {field_name}={field_value}")
        return subscriber_count
    else:
        print(f"Failed to get all-time subscribers for custom field. Status Code: {response.status_code}")
        return 0

def get_total_paperboy_subscribers_all_time(api_key):
    total = 0
    next_cursor = None
    per_page = 1000
    
    while True:
        # Prepare params with cursor if available
        params = {
            "per_page": per_page
        }
        if next_cursor:
            params["cursor"] = next_cursor
            
        response = requests.get(
            f"{BASE_URL}subscribers",
            headers={
                "Accept": "application/json",
                "X-Kit-Api-Key": api_key
            },
            params=params
        )
        
        if response.status_code != 200:
            break
            
        data = response.json()
        subscribers = data.get('subscribers', [])
        total += len(subscribers)
        
        # Get next cursor from response
        next_cursor = data.get('meta', {}).get('next_cursor')
        print(f"Fetched {len(subscribers)} total subscribers, next cursor: {next_cursor}")
        
        # If no next cursor, we've reached the end
        if not next_cursor:
            break
    
    print(f"Total subscribers: {total}")
    return total

def get_api_params(api_key, additional_params=None):
    """Base params for all API requests - API key must be included as a param"""
    params = {'api_key': api_key}
    if additional_params:
        params.update(additional_params)
    return params

@app.route('/validate_api_key', methods=['POST'])
def validate_api_key():
    print("\n=== API Key Validation Debug ===")
    print(f"Form data received: {request.form}")
    
    api_key = request.form.get('api_key')
    if not api_key:
        print("No API key received in form data")
        return jsonify({
            'valid': False,
            'error': 'No API key provided'
        })
    
    print(f"Received API key: {api_key[:10]}..." if api_key else "No API key received")
    print(f"Key length: {len(api_key)}")
    print(f"Key starts with 'kit_': {api_key.startswith('kit_')}")
    
    # Try OAuth token format first if key starts with "kit_"
    if api_key.startswith('kit_'):
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        print("\nUsing OAuth Bearer Token format")
    else:
        # Try regular API key format
        headers = {
            "Accept": "application/json",
            "X-Kit-Api-Key": api_key
        }
        print("\nUsing X-Kit-Api-Key format")
    
    print("\nRequest Details:")
    print(f"URL: {BASE_URL}/subscribers")
    print(f"Headers: {headers}")
    print(f"Params: {{'page_size': 1}}")
    
    response = requests.get(
        f"{BASE_URL}/subscribers",
        headers=headers,
        params={'page_size': 1}
    )
    
    print("\nResponse Details:")
    print(f"Status Code: {response.status_code}")
    print(f"Response Headers: {dict(response.headers)}")
    print(f"Response Body: {response.text}")
    
    if response.status_code == 200:
        session['api_key'] = api_key
        session['api_type'] = 'oauth' if api_key.startswith('kit_') else 'api_key'
        print("\nValidation Successful!")
        return jsonify({
            'valid': True
        })
    else:
        print("\nValidation Failed!")
        return jsonify({
            'valid': False,
            'error': f'Invalid API key: {response.text}'
        })

# Update your existing functions to accept api_key parameter
def get_available_tags(api_key):
    response = requests.get(
        f"{BASE_URL}tags",
        headers=get_api_headers(api_key)
    )
    if response.status_code == 200:
        return [tag['name'] for tag in response.json()['tags']]
    return []

def get_available_custom_fields(api_key):
    response = requests.get(
        f"{BASE_URL}custom_fields",
        headers=get_api_headers(api_key)
    )
    if response.status_code == 200:
        return [field['key'] for field in response.json()['custom_fields']]
    else:
        raise Exception(f"Failed to fetch custom fields. Status Code: {response.status_code}")

def get_subscribers_by_tag_with_dates(tag_name, api_key, start_date=None, end_date=None):
    """Get tag-based metrics using API key"""
    tag_id = get_tag_id(tag_name, api_key)
    if not tag_id:
        return 0
    
    params = {
        'page_size': 500
    }
    if start_date:
        params['created_after'] = start_date
    if end_date:
        params['created_before'] = end_date
    
    response = requests.get(
        f"{BASE_URL}tags/{tag_id}/subscribers",
        headers=get_api_headers(api_key),
        params=params
    )
    # Rest of function remains the same

def get_subscribers_by_date_range(api_key, start_date=None, end_date=None):
    total_subscribers = 0
    current_cursor = None
    page_size = 500
    
    print(f"\nFetching subscribers between {start_date} and {end_date}")
    print(f"Using API key: {api_key[:10]}...")  # Debug info
    
    while True:
        params = {"page_size": page_size}
        if start_date:
            params["created_after"] = start_date
        if end_date:
            params["created_before"] = end_date
        if current_cursor:
            params["after"] = current_cursor
            
        response = requests.get(
            f"{BASE_URL}subscribers",
            headers=get_api_headers(api_key),
            params=params
        )
        
        print(f"Response status: {response.status_code}")  # Debug info
        if response.status_code != 200:
            print(f"Error response: {response.text}")
            break
            
        data = response.json()
        subscribers = data.get('subscribers', [])
        current_batch = len(subscribers)
        total_subscribers += current_batch
        
        pagination = data.get('pagination', {})
        has_next_page = pagination.get('has_next_page', False)
        if not has_next_page:
            break
            
        current_cursor = pagination.get('end_cursor')
        if not current_cursor:
            break
            
        time.sleep(0.5)
    
    return total_subscribers

def get_subscribers_by_custom_field_and_date(field_name, field_value, api_key, start_date=None, end_date=None):
    print(f"\nFetching subscribers with {field_name}={field_value}")
    total_subscribers = 0
    current_cursor = None
    
    while True:
        params = {
            'page_size': 500,
            f'fields[{field_name}]': field_value
        }
        if start_date:
            params['created_after'] = start_date
        if end_date:
            params['created_before'] = end_date
        if current_cursor:
            params['after'] = current_cursor
            
        response = requests.get(
            f"{BASE_URL}/subscribers", 
            headers=get_api_headers(api_key),
            params=params
        )
        
        if response.status_code != 200:
            print(f"Error response: {response.text}")
            return 0
            
        data = response.json()
        subscribers = data.get('subscribers', [])
        
        # Only count subscribers that have the custom field value matching
        matching_subscribers = [s for s in subscribers if s.get('fields', {}).get(field_name) == field_value]
        current_batch = len(matching_subscribers)
        total_subscribers += current_batch
        
        print(f"Fetched batch of {current_batch} matching subscribers. Total so far: {total_subscribers}")
        
        pagination = data.get('pagination', {})
        if not pagination.get('has_next_page', False):
            break
            
        current_cursor = pagination.get('next')
        if not current_cursor:
            break
            
        print(f"Next cursor: {current_cursor}")
        time.sleep(0.5)  # Rate limiting
    
    print(f"Total subscribers with {field_name}={field_value}: {total_subscribers}")
    return total_subscribers

def get_total_subscribers_at_date(api_key, date_str):
    """Get total subscribers at a specific date using concurrent requests"""
    print(f"\nFetching total subscribers at date: {date_str}")
    
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    try:
        # First, get the initial page to determine total pages
        params = {
            'from': date_str,
            'to': date_str,
            'per_page': 1000  # Increase page size
        }
        
        response = requests.get(
            f"{BASE_URL}subscribers",
            headers=headers,
            params=params
        )
        
        if response.status_code != 200:
            print(f"Error response: {response.text}")
            return None
            
        data = response.json()
        total_subscribers = len(data.get('subscribers', []))
        
        # Get pagination info
        pagination = data.get('pagination', {})
        has_next = pagination.get('has_next_page', False)
        
        if not has_next:
            return total_subscribers
            
        # If there are more pages, make one more request with a larger page size
        params['per_page'] = 5000  # Maximum page size
        response = requests.get(
            f"{BASE_URL}subscribers",
            headers=headers,
            params=params
        )
        
        if response.status_code == 200:
            data = response.json()
            total_subscribers = len(data.get('subscribers', []))
            print(f"Total subscribers found: {total_subscribers}")
            return total_subscribers
            
    except Exception as e:
        print(f"Error fetching subscribers: {str(e)}")
        return None
        
    return total_subscribers

def get_subscriber_headers(api_key):
    """Headers for subscriber-related endpoints (counts, subscriber data)"""
    return {
        "Accept": "application/json",
        "X-Kit-Api-Key": api_key
    }

def get_tag_headers(api_key):
    """Headers for tag and custom field related endpoints"""
    return {
        "Authorization": f"Bearer {api_key}"
    }

def get_api_headers(api_key):
    """Get appropriate headers based on API key format"""
    base_headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {api_key}"  # Always use Bearer auth for OAuth tokens
    }
    
    print(f"Using headers: {base_headers}")
    return base_headers

@app.route('/oauth/authorize')
def oauth_authorize():
    """Step 1: User Authorization"""
    print("Starting OAuth authorization")
    convertkit = OAuth2Session(CLIENT_ID, redirect_uri=REDIRECT_URI)
    authorization_url, state = convertkit.authorization_url(AUTHORIZATION_BASE_URL)
    
    # Store the state in the session
    session['oauth_state'] = state
    
    return redirect(authorization_url)

def exchange_code_for_token(code):
    """Exchange OAuth code for access token"""
    token_url = 'https://api.convertkit.com/oauth/token'
    client_id = CLIENT_ID  # Use the constant instead of env var
    client_secret = CLIENT_SECRET  # Use the constant instead of env var
    redirect_uri = REDIRECT_URI  # Use the constant instead of env var
    
    # Debug prints
    print(f"Using client_id: {client_id}")
    print(f"Using redirect_uri: {redirect_uri}")
    
    token_data = {
        'client_id': client_id,
        'client_secret': client_secret,
        'code': code,
        'grant_type': 'authorization_code',
        'redirect_uri': redirect_uri
    }
    
    print(f"Sending token request with data: {token_data}")
    
    response = requests.post(token_url, json=token_data)
    if response.status_code != 200:
        print(f"Error getting token: {response.text}")
        raise Exception("Failed to get access token")
        
    token_json = response.json()
    token_json['expires_at'] = time.time() + token_json['expires_in']
    return token_json

@app.route('/oauth/callback')
def oauth_callback():
    print("Received OAuth callback")
    
    # Get the authorization code
    code = request.args.get('code')
    state = request.args.get('state')
    
    try:
        # Exchange the code for an access token
        token_response = exchange_code_for_token(code)
        print(f"OAuth token received: {token_response}")
        
        # Store the access token in the session
        session['access_token'] = token_response['access_token']
        session['api_key'] = token_response['access_token']
        session.permanent = True
        
        print(f"Session after storing token: {session}")
        
        return redirect(url_for('index'))
    except Exception as e:
        print(f"Error in OAuth callback: {str(e)}")
        return redirect(url_for('index'))

def print_all_routes():
    print("\n=== All Route Definitions ===")
    for name, obj in inspect.getmembers(app):
        if inspect.ismethod(obj):
            if hasattr(obj, 'view_functions'):
                print(f"Route: {name}")
                print(f"Function: {obj.__name__}")
                print("---")

# Add this before app.run()
print_all_routes()

print("\n=== End of File Reached ===")
if __name__ == '__main__':
    print("Starting Flask app")
    app.run(port=5002, debug=True)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/check_progress')
def check_progress():
    """Check the progress of counting tasks"""
    if 'counting_tasks' not in session:
        return jsonify({'error': 'No counting in progress'})
        
    tasks = session['counting_tasks']
    try:
        task1 = count_subscribers.AsyncResult(tasks['start_date'])
        task2 = count_subscribers.AsyncResult(tasks['end_date'])
        
        # Check for failed tasks
        if task1.failed() or task2.failed():
            error_msg = str(task1.result) if task1.failed() else str(task2.result)
            return jsonify({
                'error': f'Task failed: {error_msg}',
                'complete': True
            })
        
        if task1.ready() and task2.ready():
            start_count = task1.result or 0
            end_count = task2.result or 0
            
            try:
                growth = ((end_count - start_count) / start_count * 100) if start_count > 0 else 0
            except Exception as e:
                print(f"Error calculating growth: {e}")
                growth = 0
                
            return jsonify({
                'complete': True,
                'start_count': start_count,
                'end_count': end_count,
                'growth': round(growth, 2)
            })
        
        return jsonify({
            'complete': False,
            'status': {
                'start_date': task1.status,
                'end_date': task2.status
            }
        })
        
    except Exception as e:
        print(f"Error checking progress: {e}")
        return jsonify({
            'error': f'Error checking progress: {str(e)}',
            'complete': True
        })