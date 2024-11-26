import requests
import json
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
import time
import os
from requests_oauthlib import OAuth2Session
from functools import wraps
from dateutil import parser as parse
import traceback

# Load API key and base URL from config.json
with open("config.json", "r") as config_file:
    config = json.load(config_file)

API_KEY = config["api_key"]
BASE_URL = config["base_url"]
PER_PAGE_PARAM = 1000
REDIRECT_URI = 'https://127.0.0.1:5000/oauth/callback'  # Use HTTPS
TOKEN_URL = 'https://app.convertkit.com/oauth/token'
CLIENT_ID = os.getenv('CONVERTKIT_CLIENT_ID')
CLIENT_SECRET = os.getenv('CONVERTKIT_CLIENT_SECRET')
DEFAULT_FACEBOOK_TAG = 4155625
DEFAULT_CREATOR_TAG = 4090509
DEFAULT_SPARKLOOP_TAG = 5023500

# Update the client data structure to use names
CLIENT_DATA = {
    'Sieva Kozinsky': {  # Using name as identifier
        'paperboy_start_date': '2024-02-09',
        'initial_subscriber_count': 41000
    }
    # Other clients will be added here as they're onboarded
}

def get_client_data(email):
    """Get client data if it exists"""
    return CLIENT_DATA.get(email)

app = Flask(__name__)

# Set up session configuration
app.config.update(
    SECRET_KEY=os.environ.get('FLASK_SECRET_KEY', '2cea766fa92b5c9eac492053de73dc47'),
    SESSION_COOKIE_SECURE=True,  # Only send cookie over HTTPS
    SESSION_COOKIE_HTTPONLY=True,  # Prevent JavaScript access to session cookie
    SESSION_COOKIE_SAMESITE='Lax',  # Protect against CSRF
    PERMANENT_SESSION_LIFETIME=timedelta(hours=1)  # Session expires after 1 hour
)

# Cache configuration
CACHE_TIMEOUT = 3600  # 1 hour in seconds
CACHE_SIZE = 100     # Store up to 100 different queries

def check_environment():
    required_vars = ['CONVERTKIT_CLIENT_ID', 'CONVERTKIT_CLIENT_SECRET', 'FLASK_SECRET_KEY']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        raise EnvironmentError(f"Missing required environment variables: {', '.join(missing_vars)}")

# Token validation decorator
def token_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'api_key' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Rate limiting function
def rate_limited_request(url, headers, params=None):
    """Make a rate-limited request to the ConvertKit API"""
    MAX_RETRIES = 3
    RETRY_DELAY = 1  # seconds
    
    for attempt in range(MAX_RETRIES):
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code == 429:  # Too Many Requests
            time.sleep(RETRY_DELAY * (attempt + 1))
            continue
            
        return response
    
    return response  # Return last response if all retries failed

# Form validation
def validate_form_data(start_date, end_date):
    try:
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        
        if end < start:
            return False, "End date must be after start date"
            
        return True, None
    except ValueError:
        return False, "Invalid date format"

def get_subscribers(api_key, start_date, end_date):
    """Get all subscribers between two dates using cursor-based pagination"""
    url = f"{BASE_URL}/subscribers"
    headers = {'Authorization': f'Bearer {api_key}'}
    params = {
        'created_after': f"{start_date}T00:00:00Z",
        'created_before': f"{end_date}T23:59:59Z",
        'per_page': PER_PAGE_PARAM,
        'sort_order': 'desc'
    }
    
    print(f"\n=== Getting Subscribers for Date Range ===")
    print(f"Start Date: {start_date}")
    print(f"End Date: {end_date}")
    
    subscribers = []
    
    # Get first page
    response = rate_limited_request(url, headers=headers, params=params)
    if response.status_code == 200:
        data = response.json()
        current_subscribers = data.get('subscribers', [])
        subscribers.extend(current_subscribers)
        print(f"First page count: {len(current_subscribers)}")
        
        # Keep track of complete pages
        complete_pages = 0
        
        # Process subsequent pages
        while data.get('pagination', {}).get('has_next_page'):
            complete_pages += 1
            print(f"Found complete page {complete_pages}")
            
            # Get next page cursor
            params['after'] = data['pagination']['end_cursor']
            
            # Get next page
            response = rate_limited_request(url, headers=headers, params=params)
            if response.status_code == 200:
                data = response.json()
                current_subscribers = data.get('subscribers', [])
                subscribers.extend(current_subscribers)
                print(f"Page {complete_pages + 1} count: {len(current_subscribers)}")
            else:
                print(f"Error getting page: {response.text}")
                break
    
    total = len(subscribers)
    print(f"Total subscribers found: {total}")
    return subscribers

def get_tagged_subscribers(api_key, tag_id, start_date, end_date):
    """Get tagged subscriber count using optimized pagination"""
    if not tag_id:
        return []
        
    url = f"{BASE_URL}/tags/{tag_id}/subscribers"
    headers = {'Authorization': f'Bearer {api_key}'}
    params = {
        'created_after': f"{start_date}T00:00:00Z",
        'created_before': f"{end_date}T23:59:59Z",
        'per_page': PER_PAGE_PARAM,
        'sort_order': 'desc'
    }
    
    total = 0
    tagged_subscribers = []  # Still need to collect for filtering
    
    # Get first page
    response = rate_limited_request(url, headers=headers, params=params)
    if response.status_code == 200:
        data = response.json()
        tagged_subscribers.extend(data.get('subscribers', []))
        total = len(tagged_subscribers)
        print(f"First page count for tag {tag_id}: {total}")
        
        # Keep track of complete pages
        complete_pages = 0
        
        # Process subsequent pages
        while data.get('pagination', {}).get('has_next_page'):
            complete_pages += 1
            print(f"Found complete page {complete_pages} for tag {tag_id}")
            
            # Get next page cursor
            params['after'] = data['pagination']['end_cursor']
            
            # Get next page
            response = rate_limited_request(url, headers=headers, params=params)
            if response.status_code == 200:
                data = response.json()
                current_subscribers = data.get('subscribers', [])
                tagged_subscribers.extend(current_subscribers)
                if not data.get('pagination', {}).get('has_next_page'):
                    # Last page - count actual subscribers
                    total += len(current_subscribers)
                    print(f"Last page count for tag {tag_id}: {len(current_subscribers)}")
                else:
                    # Complete page - add 1000
                    total += PER_PAGE_PARAM
            else:
                print(f"Error getting page: {response.text}")
                break
                
        print(f"Total tagged subscribers: {total} (from {complete_pages} complete pages + last page)")
    
    return tagged_subscribers  # Return full list for filtering

def get_tags(api_key):
    """Get all tags from ConvertKit"""
    try:
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        
        response = rate_limited_request(
            'https://api.convertkit.com/v4/tags',
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"=== Tags Retrieved ===")
            print(f"Number of tags: {len(data.get('tags', []))}")
            print(f"First few tags: {data.get('tags', [])[:3]}")
            return data.get('tags', [])
        else:
            print(f"Error fetching tags: {response.text}")
            return []
            
    except Exception as e:
        print(f"Exception in get_tags: {str(e)}")
        return []

@app.route('/', methods=['GET', 'POST'])
@token_required
def index():
    # Always set default dates relative to today
    default_end_date = datetime.now().strftime('%Y-%m-%d')
    default_start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    
    selected_client = session.get('selected_client')
    client_data = get_client_data(selected_client)

    # If we don't have client data yet, show the setup form
    if selected_client and not client_data:
        return render_template('index.html',
                             selected_client=selected_client,
                             show_setup=True,
                             default_start_date=default_start_date,
                             default_end_date=default_end_date)

    if request.method == 'POST':
        try:
            # Handle first-time setup
            if 'paperboy_start_date' in request.form:
                new_client_data = {
                    'paperboy_start_date': request.form.get('paperboy_start_date'),
                    'initial_subscriber_count': int(request.form.get('initial_subscriber_count'))
                }
                CLIENT_DATA[selected_client] = new_client_data
                save_client_data()
                client_data = new_client_data
                flash('Client setup completed successfully!', 'success')
                return redirect(url_for('index'))

            # Only process analytics if we have client data
            if client_data:
                start_date = request.form.get('start_date', default_start_date)
                end_date = request.form.get('end_date', default_end_date)
                current_total = int(request.form.get('current_total', 0))
                
                # Get tag selections
                facebook_tag = request.form.get('facebook_tag')
                creator_tag = request.form.get('creator_tag')
                sparkloop_tag = request.form.get('sparkloop_tag')
                
                # Get subscribers and calculate metrics
                recent_subscribers = get_subscribers(session['api_key'], start_date, end_date)
                
                # Only calculate growth rate if we have the necessary data
                growth_rate = 0
                if client_data and 'initial_subscriber_count' in client_data:
                    growth_rate = ((current_total - client_data['initial_subscriber_count']) / 
                                 client_data['initial_subscriber_count'] * 100)
                
                # Calculate total growth since Paperboy start
                paperboy_start = datetime.strptime(client_data['paperboy_start_date'], '%Y-%m-%d')
                total_growth = current_total - client_data['initial_subscriber_count']
                
                # Get subscribers for 60 days before Paperboy
                before_start = paperboy_start - timedelta(days=60)
                before_subscribers = get_subscribers(session['api_key'], 
                                                  before_start.strftime('%Y-%m-%d'),
                                                  client_data['paperboy_start_date'])
                
                # Get subscribers for 60 days after Paperboy
                after_end = paperboy_start + timedelta(days=60)
                after_subscribers = get_subscribers(session['api_key'],
                                                 client_data['paperboy_start_date'],
                                                 after_end.strftime('%Y-%m-%d'))
                
                # Calculate daily averages
                daily_average_before = len(before_subscribers) / 60
                daily_average_after = len(after_subscribers) / 60
                
                results = {
                    'start_date': start_date,
                    'end_date': end_date,
                    'total_subscribers': len(recent_subscribers),
                    'facebook_subscribers': len(get_tagged_subscribers(session['api_key'], facebook_tag, start_date, end_date)) if facebook_tag else 0,
                    'creator_subscribers': len(get_tagged_subscribers(session['api_key'], creator_tag, start_date, end_date)) if creator_tag else 0,
                    'sparkloop_subscribers': len(get_tagged_subscribers(session['api_key'], sparkloop_tag, start_date, end_date)) if sparkloop_tag else 0,
                    'growth_rate': growth_rate,
                    'total_growth': total_growth,
                    'daily_average_before': round(daily_average_before, 1),
                    'daily_average_after': round(daily_average_after, 1),
                    'paperboy_start_date': client_data['paperboy_start_date'],
                    'before_period': f"{before_start.strftime('%Y-%m-%d')} to {client_data['paperboy_start_date']}",
                    'after_period': f"{client_data['paperboy_start_date']} to {after_end.strftime('%Y-%m-%d')}"
                }
                
                return render_template('index.html',
                                   results=results,
                                   client_data=client_data,
                                   selected_client=selected_client,
                                   tags=get_tags(session['api_key']),
                                   facebook_tag_id=int(facebook_tag) if facebook_tag else DEFAULT_FACEBOOK_TAG,
                                   creator_tag_id=int(creator_tag) if creator_tag else DEFAULT_CREATOR_TAG,
                                   sparkloop_tag_id=int(sparkloop_tag) if sparkloop_tag else DEFAULT_SPARKLOOP_TAG,
                                   default_start_date=default_start_date,
                                   default_end_date=default_end_date)
            
        except Exception as e:
            print(f"Error processing data: {str(e)}")
            print(traceback.format_exc())
            flash('Error processing data', 'error')
    
    # Default GET render
    return render_template('index.html',
                         client_data=client_data,
                         selected_client=selected_client,
                         tags=get_tags(session['api_key']) if 'api_key' in session else None,
                         facebook_tag_id=DEFAULT_FACEBOOK_TAG,
                         creator_tag_id=DEFAULT_CREATOR_TAG,
                         sparkloop_tag_id=DEFAULT_SPARKLOOP_TAG,
                         default_start_date=default_start_date,
                         default_end_date=default_end_date)

@app.route('/oauth/authorize')
def oauth_authorize():
    print("=== OAuth Authorize Route ===")
    oauth = OAuth2Session(
        CLIENT_ID,
        redirect_uri=REDIRECT_URI,
        scope=['public']
    )
    authorization_url, state = oauth.authorization_url('https://app.convertkit.com/oauth/authorize')
    session['oauth_state'] = state
    print(f"Generated authorization URL: {authorization_url}")
    return redirect(authorization_url)

@app.route('/oauth/callback')
def oauth_callback():
    print("=== OAuth Callback Route ===")
    try:
        oauth = OAuth2Session(
            CLIENT_ID,
            redirect_uri=REDIRECT_URI,
            state=session.get('oauth_state')
        )
        
        token = oauth.fetch_token(
            TOKEN_URL,
            client_secret=CLIENT_SECRET,
            authorization_response=request.url
        )
        
        # Get the selected account info from ConvertKit
        headers = {'Authorization': f'Bearer {token["access_token"]}'}
        account_response = requests.get('https://api.convertkit.com/v4/account', headers=headers)
        
        if account_response.status_code == 200:
            account_data = account_response.json()
            print(f"Account data received: {account_data}")
            
            # Get name from the account data
            client_name = account_data.get('account', {}).get('name')
            session['selected_client'] = client_name
            print(f"Selected client: {client_name}")
            
            if client_name not in CLIENT_DATA:
                print(f"New client detected: {client_name}")
                CLIENT_DATA[client_name] = {}
                save_client_data()
        else:
            print(f"Error getting account data: {account_response.text}")
            
        session['api_key'] = token['access_token']
        session['token_expiry'] = time.time() + token.get('expires_in', 3600)
        flash('Successfully connected to ConvertKit!', 'success')
        return redirect(url_for('index'))
        
    except Exception as e:
        print(f"OAuth Error: {str(e)}")
        flash('Authentication failed. Please try again.', 'error')
        return redirect(url_for('index'))

@app.route('/logout')
def logout():
    print("=== Logout Route ===")
    session.clear()
    return redirect(url_for('index'))

@app.route('/validate_api_key', methods=['POST'])
def validate_api_key():
    data = request.get_json()
    api_key = data.get('api_key')
    
    try:
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        
        response = rate_limited_request(
            'https://api.convertkit.com/v4/tags',
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            tags = data.get('tags', [])
            return jsonify({
                'valid': True,
                'tags': [{'id': tag['id'], 'name': tag['name']} for tag in tags]
            })
        else:
            return jsonify({
                'valid': False,
                'error': 'Invalid API key'
            })
            
    except Exception as e:
        return jsonify({
            'valid': False,
            'error': str(e)
        })

# Add the login route back
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        api_key = request.form.get('api_key')
        if api_key:
            session['api_key'] = api_key
            return redirect(url_for('index'))
    return render_template('index.html')  # We'll use the same template for now

# Initialize the app
check_environment()

if __name__ == '__main__':
    app.run(ssl_context='adhoc')