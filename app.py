import requests
import json
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
import time

# Load API key and base URL from config.json
with open("config.json", "r") as config_file:
    config = json.load(config_file)

API_KEY = config["api_key"]
BASE_URL = config["base_url"]
PER_PAGE_PARAM = 5000

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Add this for session management

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
def get_available_custom_fields():
    endpoint = f"{BASE_URL}custom_fields"
    
    headers = {
        "Accept": "application/json",
        "X-Kit-Api-Key": API_KEY
    }
    
    response = requests.get(endpoint, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        return [field['key'] for field in data['custom_fields']]
    else:
        print(f"Failed to fetch custom fields. Status Code: {response.status_code}")
        return []

# Flask route to display form for selecting start/end dates, tags, and custom fields
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        session['api_key'] = request.form['api_key']
        session['start_date'] = request.form['start_date']
        session['end_date'] = request.form['end_date']
        
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
    
    return render_template('index.html')

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
    
    # Get total subscribers
    total_recent_subscribers = get_subscribers_by_date_range(
        api_key,
        start_date_formatted,
        end_date_formatted
    )
    
    # Get subscribers by tags
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
    
    # Create tag_counts dictionary
    tag_counts = {
        "Creator Network": creator_network_count,
        "Facebook Ads": fb_ads_count,
        "Sparkloop": sparkloop_count
    }
    
    # Calculate organic
    tagged_subscribers = sum(tag_counts.values())
    organic_subscribers = total_recent_subscribers - tagged_subscribers
    
    print(f"Rendering template with: {tag_counts}")  # Debug print
    
    return render_template('results.html',
                        start_date=start_date,
                        end_date=end_date,
                        total_recent_subscribers=total_recent_subscribers,
                        tag_counts=tag_counts,
                        organic_subscribers=organic_subscribers)

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

@app.route('/validate_api_key', methods=['POST'])
def validate_api_key():
    data = request.get_json()
    api_key = data.get('api_key')
    
    try:
        # Get tags and print them for debugging
        tags = get_available_tags(api_key)
        print("Available tags:", tags)  # Debug print
        
        # Get custom fields and print them
        custom_fields = get_available_custom_fields(api_key)
        print("Available custom fields:", custom_fields)  # Debug print
        
        response_data = {
            'valid': True,
            'tags': tags,
            'custom_fields': custom_fields
        }
        print("Sending response:", response_data)  # Debug print
        return jsonify(response_data)
        
    except Exception as e:
        print(f"Error in validate_api_key: {str(e)}")  # Debug print
        return jsonify({
            'valid': False,
            'error': str(e)
        })

# Update your existing functions to accept api_key parameter
def get_available_tags(api_key):
    headers = {
        "Accept": "application/json",
        "X-Kit-Api-Key": api_key
    }
    response = requests.get(f"{BASE_URL}tags", headers=headers)
    if response.status_code == 200:
        return [tag['name'] for tag in response.json()['tags']]
    return []

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
        raise Exception(f"Failed to fetch custom fields. Status Code: {response.status_code}")

def get_subscribers_by_tag_with_dates(tag_name, api_key, start_date=None, end_date=None):
    tag_id = get_tag_id(tag_name, api_key)
    
    if tag_id is None:
        print(f"Tag '{tag_name}' not found.")
        return 0
    
    total_subscribers = 0
    current_cursor = None
    page_size = 500  # API enforces 500 per page
    
    print(f"Fetching subscribers for tag '{tag_name}' (ID: {tag_id}) between {start_date} and {end_date}")
    
    while True:
        # Updated to use created_after/created_before instead of subscribed_after/subscribed_before
        params = {"page_size": page_size}
        if start_date:
            params["created_after"] = start_date
        if end_date:
            params["created_before"] = end_date
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
        subscribers = data.get('subscribers', [])
        
        # Only count subscribers within our date range
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

def get_subscribers_by_date_range(api_key, start_date=None, end_date=None):
    total_subscribers = 0
    current_cursor = None
    page_size = 500
    
    print(f"Fetching all subscribers between {start_date} and {end_date}")
    
    while True:
        params = {"page_size": page_size}
        if start_date:
            params["created_after"] = start_date
        if end_date:
            params["created_before"] = end_date
        if current_cursor:
            params["after"] = current_cursor
            
        print(f"Making request with params: {params}")
        
        response = requests.get(
            f"{BASE_URL}subscribers",
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
        subscribers = data.get('subscribers', [])
        current_batch = len(subscribers)
        total_subscribers += current_batch
        
        print(f"Fetched batch of {current_batch} subscribers. Total so far: {total_subscribers}")
        
        pagination = data.get('pagination', {})
        has_next_page = pagination.get('has_next_page', False)
        if not has_next_page:
            break
            
        current_cursor = pagination.get('end_cursor')
        if not current_cursor:
            break
            
        time.sleep(0.5)
    
    print(f"Total subscribers in date range: {total_subscribers}")
    return total_subscribers

def get_subscribers_by_custom_field_and_date(field_name, field_value, api_key, start_date=None, end_date=None):
    print(f"\nFetching subscribers with {field_name}={field_value}")
    total_subscribers = 0
    current_cursor = None
    
    while True:
        params = {
            'page_size': 500,
            f'fields[{field_name}]': field_value  # This is the key change
        }
        if start_date:
            params['created_after'] = start_date
        if end_date:
            params['created_before'] = end_date
        if current_cursor:
            params['after'] = current_cursor
            
        print(f"Making request with params: {params}")
        response = requests.get(f"{BASE_URL}/subscribers", 
                              headers={"Authorization": f"Bearer {api_key}"},
                              params=params)
        
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

if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True, port=5002)