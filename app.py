import requests
import json
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify
import time

# Load API key and base URL from config.json
with open("config.json", "r") as config_file:
    config = json.load(config_file)

API_KEY = config["api_key"]
BASE_URL = config["base_url"]
PER_PAGE_PARAM = 1000

app = Flask(__name__)

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
    
    headers = {
        "Accept": "application/json",
        "X-Kit-Api-Key": api_key
    }
    
    params = {
        "created_after": start_date,
        "created_before": end_date,
        "page": 1,
        "per_page": PER_PAGE_PARAM
    }
    
    total_subscribers = 0
    
    # First request to get total pages
    response = requests.get(endpoint, headers=headers, params=params)
    if response.status_code == 200:
        data = response.json()
        total_pages = data.get('total_pages', 1)
        print(f"Total pages: {total_pages}")
        
        # Loop through all pages
        for page in range(1, total_pages + 1):
            params['page'] = page
            print(f"Fetching page {page} of {total_pages}...")
            
            response = requests.get(endpoint, headers=headers, params=params)
            if response.status_code == 200:
                data = response.json()
                subscribers_this_page = len(data['subscribers'])
                total_subscribers += subscribers_this_page
                print(f"Found {subscribers_this_page} subscribers on page {page}")
            else:
                print(f"Failed to get page {page}. Status Code: {response.status_code}")
                break
    
    print(f"Total subscribers found: {total_subscribers}")
    return total_subscribers

# Function to get subscribers with a specific tag
def get_subscribers_by_tag(tag_name, api_key):
    tag_id = get_tag_id(tag_name, api_key)
    
    if tag_id is None:
        return 0
    
    endpoint = f"{BASE_URL}tags/{tag_id}/subscribers"
    
    headers = {
        "Accept": "application/json",
        "X-Kit-Api-Key": api_key
    }
    
    params = {
        "page": 1,
        "per_page": PER_PAGE_PARAM
    }
    
    total_subscribers = 0
    
    # First request to get total pages
    response = requests.get(endpoint, headers=headers, params=params)
    if response.status_code == 200:
        data = response.json()
        total_pages = data.get('total_pages', 1)
        print(f"Total pages for {tag_name}: {total_pages}")
        
        # Loop through all pages
        for page in range(1, total_pages + 1):
            params['page'] = page
            print(f"Fetching {tag_name} page {page} of {total_pages}...")
            
            response = requests.get(endpoint, headers=headers, params=params)
            if response.status_code == 200:
                data = response.json()
                subscribers_this_page = len(data['subscribers'])
                total_subscribers += subscribers_this_page
                print(f"Found {subscribers_this_page} {tag_name} subscribers on page {page}")
            else:
                print(f"Failed to get page {page}. Status Code: {response.status_code}")
                break
    
    print(f"Total {tag_name} subscribers found: {total_subscribers}")
    return total_subscribers

# Function to get subscribers based on custom field 'rh_isref'
def get_subscribers_by_custom_field(field_name, field_value, api_key):
    endpoint = f"{BASE_URL}subscribers"
    
    headers = {
        "Accept": "application/json",
        "X-Kit-Api-Key": api_key
    }
    
    params = {
        f"fields[{field_name}]": field_value,
        "page": 1,
        "per_page": PER_PAGE_PARAM
    }
    
    total_subscribers = 0
    
    # First request to get total pages
    response = requests.get(endpoint, headers=headers, params=params)
    if response.status_code == 200:
        data = response.json()
        total_pages = data.get('total_pages', 1)
        print(f"Total pages for {field_name}: {total_pages}")
        
        # Loop through all pages
        for page in range(1, total_pages + 1):
            params['page'] = page
            print(f"Fetching {field_name} page {page} of {total_pages}...")
            
            response = requests.get(endpoint, headers=headers, params=params)
            if response.status_code == 200:
                data = response.json()
                subscribers_this_page = len([
                    s for s in data['subscribers'] 
                    if s.get('fields', {}).get(field_name) == field_value
                ])
                total_subscribers += subscribers_this_page
                print(f"Found {subscribers_this_page} subscribers with {field_name}={field_value} on page {page}")
            else:
                print(f"Failed to get page {page}. Status Code: {response.status_code}")
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
        # Get form data including the API key
        api_key = request.form['api_key']
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        paperboy_start_date = request.form['paperboy_start_date']
        
        # Convert dates to required format
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
        paperboy_start_date_obj = datetime.strptime(paperboy_start_date, "%Y-%m-%d")
        
        # Format dates for API
        start_date_str = start_date_obj.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_date_str = end_date_obj.strftime("%Y-%m-%dT%H:%M:%SZ")
        paperboy_start_date_str = paperboy_start_date_obj.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Update all your API calls to use the submitted api_key
        def get_headers():
            return {
                "Accept": "application/json",
                "X-Kit-Api-Key": api_key
            }

        # Update each function call to use the new API key
        total_subscribers = get_subscribers_last_x_days(start_date_str, end_date_str, api_key)
        
        # Get tag counts with new API key
        tag_counts = {}
        for tag in ["Facebook Ads", "Creator Network"]:
            count = get_subscribers_by_tag(tag, api_key)
            if count > 0:
                tag_counts[tag] = count

        # Get RH_ISREF count with new API key
        rh_isref_count = get_subscribers_by_custom_field('rh_isref', 'YES', api_key)
        
        # Calculate organic subscribers
        tagged_subscribers = sum(tag_counts.values()) + rh_isref_count
        organic_subscribers = total_subscribers - tagged_subscribers
        
        # Calculate organic percentage
        organic_percentage = calculate_percentage_filter(organic_subscribers, total_subscribers)
        
        # Get total subscribers since Paperboy start date
        total_since_start = get_subscribers_last_x_days(paperboy_start_date_str, datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"), api_key)
        
        # Get total Paperboy subscribers all time
        total_paperboy_all_time = get_total_paperboy_subscribers_all_time(api_key)
        
        # Calculate days and averages
        earliest_date = "2023-01-01T00:00:00Z"  # Or your preferred start date
        subscribers_before_paperboy = get_subscribers_last_x_days(earliest_date, paperboy_start_date_str, api_key)
        subscribers_since_paperboy = get_subscribers_last_x_days(paperboy_start_date_str, datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"), api_key)
        
        days_before_start = (paperboy_start_date_obj - datetime.strptime(earliest_date, "%Y-%m-%dT%H:%M:%SZ")).days
        days_since_start = (datetime.now() - paperboy_start_date_obj).days
        
        avg_subs_before_start = subscribers_before_paperboy / days_before_start if days_before_start > 0 else 0
        avg_subs_since_start = subscribers_since_paperboy / days_since_start if days_since_start > 0 else 0
        
        avg_subs_before_percentage = calculate_percentage_filter(avg_subs_before_start, subscribers_before_paperboy)
        avg_subs_since_percentage = calculate_percentage_filter(avg_subs_since_start, subscribers_since_paperboy)

        return render_template('results.html',
                             total_subscribers=total_subscribers,
                             tag_counts=tag_counts,
                             organic_subscribers=organic_subscribers,
                             rh_isref_count=rh_isref_count,
                             total_since_start=total_since_start,
                             total_paperboy_all_time=total_paperboy_all_time,
                             avg_subs_before_start=avg_subs_before_start,
                             avg_subs_since_start=avg_subs_since_start,
                             avg_subs_before_percentage=avg_subs_before_percentage,
                             avg_subs_since_percentage=avg_subs_since_percentage,
                             organic_percentage=organic_percentage,
                             start_date=start_date,
                             end_date=end_date)
    
    # GET request - return initial form
    return render_template('index.html', tags=None, custom_fields=None)


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
    
    # Use the correct endpoint for tagged subscribers
    endpoint = f"{BASE_URL}subscribers"
    
    headers = {
        "Accept": "application/json",
        "X-Kit-Api-Key": api_key
    }
    
    params = {
        "per_page": PER_PAGE_PARAM,
        "filter[tag_id]": tag_id  # Add filter for specific tag
    }
    
    total_subscribers = 0
    more_pages = True
    seen_subscriber_ids = set()
    
    while more_pages:
        print(f"Fetching subscribers with tag '{tag_name}' (page {params['page']})...")
        response = requests.get(endpoint, headers=headers, params=params)
        
        if response.status_code == 200:
            data = response.json()
            subscribers_this_page = data.get('subscribers', [])
            pagination_info = data.get('pagination', {})
            
            # Count only subscribers that have our tag
            new_subscribers = 0
            for subscriber in subscribers_this_page:
                subscriber_id = subscriber.get('id')
                if subscriber_id and subscriber_id not in seen_subscriber_ids:
                    seen_subscriber_ids.add(subscriber_id)
                    new_subscribers += 1
            
            if new_subscribers == 0:
                print("No new subscribers found")
                more_pages = False
            else:
                total_subscribers = len(seen_subscriber_ids)
                print(f"Found {new_subscribers} new tagged subscribers on page {params['page']}")
                print(f"Running total of subscribers with tag: {total_subscribers}")
                
                if pagination_info.get('has_next_page'):
                    # Get the next page by reading the pagination key and end cursor
                    params['after'] = pagination_info['end_cursor']
                    time.sleep(0.5)  # Rate limiting
                else:
                    print("Last page reached")
                    more_pages = False
        else:
            print(f"Failed to get subscribers. Status Code: {response.status_code}")
            print(f"Response: {response.text}")
            more_pages = False
    
    print(f"Final count of subscribers with tag '{tag_name}': {total_subscribers}")
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
    # Get all-time subscribers with RH_ISREF=YES
    rh_isref_count = get_all_time_subscribers_by_custom_field('rh_isref', 'YES', api_key)
    print(f"All-time RH_ISREF count: {rh_isref_count}")
    
    # Get all-time subscribers with Facebook Ads tag
    fb_ads_count = get_all_time_subscribers_by_tag('Facebook Ads', api_key)
    print(f"All-time Facebook Ads tag count: {fb_ads_count}")
    
    # Total is the sum of both
    total_count = rh_isref_count + fb_ads_count
    print(f"Total Paperboy subscribers all-time: {total_count}")
    
    return total_count

@app.route('/validate_api_key', methods=['POST'])
def validate_api_key():
    data = request.get_json()
    api_key = data.get('api_key')
    
    try:
        headers = {
            "Accept": "application/json",
            "X-Kit-Api-Key": api_key
        }
        
        # Just validate by fetching tags
        tags_response = requests.get(f"{BASE_URL}tags", headers=headers)
        if tags_response.status_code != 200:
            return jsonify({
                'valid': False,
                'error': 'Invalid API key'
            })
            
        tags = [tag['name'] for tag in tags_response.json()['tags']]
        
        # Get custom fields
        custom_fields_response = requests.get(f"{BASE_URL}custom_fields", headers=headers)
        custom_fields = [field['key'] for field in custom_fields_response.json()['custom_fields']]
        
        return jsonify({
            'valid': True,
            'tags': tags,
            'custom_fields': custom_fields
        })
            
    except Exception as e:
        return jsonify({
            'valid': False,
            'error': str(e)
        })

# Update your existing functions to accept api_key parameter
def get_available_tags(api_key):
    endpoint = f"{BASE_URL}tags"
    
    headers = {
        "Accept": "application/json",
        "X-Kit-Api-Key": api_key
    }
    
    response = requests.get(endpoint, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        return [tag['name'] for tag in data['tags']]
    else:
        raise Exception(f"Failed to fetch tags. Status Code: {response.status_code}")

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

if __name__ == "__main__":
    app.run(debug=True)