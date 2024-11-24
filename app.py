import requests
import json
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
import time
from requests_oauthlib import OAuth2Session
import os
from dotenv import load_dotenv
import inspect

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

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Required for sessions

# ConvertKit OAuth settings
CLIENT_ID = 'your_client_id'  # Get this from ConvertKit
CLIENT_SECRET = 'your_client_secret'  # Get this from ConvertKit
AUTHORIZATION_BASE_URL = 'https://app.convertkit.com/oauth/authorize'
TOKEN_URL = 'https://api.convertkit.com/oauth/token'
REDIRECT_URI = 'https://484c-72-134-227-142.ngrok-free.app/oauth/callback'

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
    register_route('/', 'index')
    print("Index route called")
    if request.method == 'POST':
        print("POST request received")
        # Handle API key form submission
        session['api_key'] = request.form.get('api_key')
        session['start_date'] = request.form.get('start_date')
        session['end_date'] = request.form.get('end_date')
        session['paperboy_start_date'] = request.form.get('paperboy_start')
        
        # Store the results in session to prevent recomputation on refresh
        api_key = session['api_key']
        start_date = session['start_date']
        end_date = session['end_date']
        
        start_date_formatted = f"{start_date}T00:00:00Z" if start_date else None
        end_date_formatted = f"{end_date}T23:59:59Z" if end_date else None
        
        try:
            total_subscribers = get_subscribers_by_date_range(
                api_key, 
                start_date_formatted, 
                end_date_formatted
            )
            
            creator_network = get_subscribers_by_tag_with_dates(
                "Creator Network",
                api_key,
                start_date_formatted,
                end_date_formatted
            )
            
            fb_ads = get_subscribers_by_tag_with_dates(
                "Facebook Ads",
                api_key,
                start_date_formatted,
                end_date_formatted
            )
            
            referrals = get_subscribers_by_custom_field_and_date(
                'rh_isref', 
                'YES', 
                api_key, 
                start_date_formatted, 
                end_date_formatted
            )
            
            # Store results in session
            session['results'] = {
                'total_subscribers': total_subscribers,
                'creator_network': creator_network,
                'fb_ads': fb_ads,
                'referrals': referrals,
                'organic': total_subscribers - (creator_network + fb_ads + referrals)
            }
            
            return redirect(url_for('show_results'))
            
        except Exception as e:
            flash(f"Error processing request: {str(e)}")
            return redirect(url_for('index'))
    
    # GET request handling
    oauth_token = session.get('oauth_token')
    api_key = session.get('api_key')
    
    authenticated = bool(oauth_token or api_key)
    return render_template('index.html', 
                         authenticated=authenticated,
                         using_oauth=bool(oauth_token))

@app.route('/results')
def show_results():
    if 'api_key' not in session:
        return redirect(url_for('index'))
        
    api_key = session['api_key']
    start_date = session['start_date']
    end_date = session['end_date']
    
    # Format dates for API
    start_date_formatted = f"{start_date}T00:00:00Z" if start_date else None
    end_date_formatted = f"{end_date}T23:59:59Z" if end_date else None
    
    # Get total subscribers for selected date range
    total_recent_subscribers = get_subscribers_by_date_range(
        api_key,
        start_date_formatted,
        end_date_formatted
    )
    
    # Get subscribers by tags for selected date range
    creator_network_count = get_subscribers_by_tag_with_dates(
        "Creator Network",
        api_key,
        start_date_formatted,
        end_date_formatted
    )
    
    fb_ads_count = get_subscribers_by_tag_with_dates(
        "Facebook Ads",
        api_key,
        start_date_formatted,
        end_date_formatted
    )
    
    sparkloop_count = get_subscribers_by_tag_with_dates(
        "SparkLoop - Engaged",
        api_key,
        start_date_formatted,
        end_date_formatted
    )
    
    # Create tag_counts dictionary for selected date range
    tag_counts = {
        "Creator Network": creator_network_count,
        "Facebook Ads": fb_ads_count,
        "Sparkloop": sparkloop_count
    }
    
    # Calculate organic for selected date range
    tagged_subscribers = sum(tag_counts.values())
    organic_subscribers = total_recent_subscribers - tagged_subscribers
    
    # Get Paperboy all-time metrics (since PAPERBOY_START_DATE)
    paperboy_total_subscribers = get_subscribers_by_date_range(
        api_key,
        PAPERBOY_START_DATE,
        end_date_formatted
    )
    
    # Get Paperboy attributed subscribers (FB Ads + Sparkloop since start date)
    paperboy_fb_ads = get_subscribers_by_tag_with_dates(
        "Facebook Ads",
        api_key,
        PAPERBOY_START_DATE,
        end_date_formatted
    )
    
    paperboy_sparkloop = get_subscribers_by_tag_with_dates(
        "SparkLoop - Engaged",
        api_key,
        PAPERBOY_START_DATE,
        end_date_formatted
    )
    
    paperboy_attributed = paperboy_fb_ads + paperboy_sparkloop
    
    print(f"Paperboy total: {paperboy_total_subscribers}, FB Ads: {paperboy_fb_ads}, Sparkloop: {paperboy_sparkloop}")
    
    # Get existing metrics
    total_recent_subscribers = session.get('total_recent_subscribers', 0)
    tag_counts = session.get('tag_counts', {})
    
    # Get paperboy start date from session
    paperboy_start = session.get('paperboy_start_date')
    print(f"Using Paperboy start date: {paperboy_start}")  # Debug log
    
    # Format dates properly for API
    paperboy_start_iso = f"{paperboy_start}T00:00:00Z" if paperboy_start else None
    current_date_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # Get subscriber counts
    subscribers_at_start = get_total_subscribers_at_date(api_key, paperboy_start_iso)
    current_subscribers = get_total_subscribers_at_date(api_key, current_date_iso)
    
    total_growth = current_subscribers - subscribers_at_start
    growth_percentage = ((current_subscribers - subscribers_at_start) / subscribers_at_start * 100) if subscribers_at_start > 0 else 0
    
    return render_template('results.html',
                        start_date=start_date,
                        end_date=end_date,
                        total_recent_subscribers=total_recent_subscribers,
                        tag_counts=tag_counts,
                        organic_subscribers=organic_subscribers,
                        # New Paperboy variables
                        paperboy_start_date=PAPERBOY_START_DATE[:10],
                        paperboy_total_subscribers=paperboy_total_subscribers,
                        paperboy_attributed=paperboy_attributed,
                        paperboy_fb_ads=paperboy_fb_ads,
                        paperboy_sparkloop=paperboy_sparkloop,
                        subscribers_at_start=subscribers_at_start,
                        current_subscribers=current_subscribers,
                        total_growth=total_growth,
                        growth_percentage=round(growth_percentage, 1))

# Function to fetch available tags (for dropdown)
def get_available_tags():
    endpoint = f"{BASE_URL}tags"
    
    headers = {
        "Accept": "application/json",
        "X-Kit-Api-Key": API_KEY
    }
    
    response = requests.get(endpoint, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        return [tag['name'] for tag in data['tags']]
    else:
        print(f"Failed to fetch tags. Status Code: {response.status_code}")
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

def get_total_subscribers_at_date(api_key, date):
    print(f"\nFetching total subscribers at date: {date}")
    print(f"Using API key: {api_key[:10]}...")  # Debug info
    
    params = {
        'page_size': 500,
        'created_before': date,
        'status': 'active'
    }
    
    response = requests.get(
        f"{BASE_URL}/subscribers",
        headers=get_api_headers(api_key),
        params=params
    )
    
    print(f"Response status: {response.status_code}")  # Debug info
    if response.status_code == 200:
        data = response.json()
        total = data.get('total_subscribers', 0)
        print(f"Total subscribers: {total}")
        return total
    else:
        print(f"Error response: {response.text}")
        return None

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
    base_headers = {"Accept": "application/json"}
    
    if api_key.startswith('kit_'):
        base_headers["Authorization"] = f"Bearer {api_key}"
    else:
        base_headers["X-Kit-Api-Key"] = api_key
    
    print(f"Using headers: {base_headers}")  # Debug info
    return base_headers

@app.route('/oauth/authorize')
def oauth_authorize():
    """Step 1: User Authorization"""
    print("Starting OAuth authorization")
    convertkit = OAuth2Session(CLIENT_ID, redirect_uri=REDIRECT_URI)
    authorization_url, state = convertkit.authorization_url(AUTHORIZATION_BASE_URL)
    session['oauth_state'] = state
    return redirect(authorization_url)

@app.route('/oauth/callback')
def oauth_callback():
    """Step 2: Retrieving an access token"""
    print("Received OAuth callback")
    convertkit = OAuth2Session(CLIENT_ID, state=session['oauth_state'], redirect_uri=REDIRECT_URI)
    token = convertkit.fetch_token(
        TOKEN_URL,
        client_secret=CLIENT_SECRET,
        authorization_response=request.url
    )
    session['oauth_token'] = token
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