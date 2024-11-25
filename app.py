import requests
import json
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
import time
from requests_oauthlib import OAuth2Session
import os
from dotenv import load_dotenv
import inspect
from flask_session import Session
import redis

print("=== Starting Flask App Setup ===")
registered_routes = set()

def register_route(route, function_name):
    if route in registered_routes:
        print(f"WARNING: Duplicate route detected! {route} -> {function_name}")
    registered_routes.add(route)
    print(f"Registered route: {route} -> {function_name}")

load_dotenv()  # Load environment variables

BASE_URL = "https://api.convertkit.com/v4/"
PER_PAGE_PARAM = 1000  # Reduced from 5000 to prevent timeouts
PAPERBOY_START_DATE = "2024-10-29T00:00:00Z"
REDIRECT_URI = 'https://convertkit-analytics-941b0603483f.herokuapp.com/oauth/callback'

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key')

# ConvertKit OAuth settings
CLIENT_ID = os.getenv('CONVERTKIT_CLIENT_ID')
CLIENT_SECRET = os.getenv('CONVERTKIT_CLIENT_SECRET')
AUTHORIZATION_BASE_URL = 'https://app.convertkit.com/oauth/authorize'
TOKEN_URL = 'https://api.convertkit.com/oauth/token'

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Configure Redis session
app.config['SESSION_TYPE'] = 'redis'
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
app.config['SESSION_REDIS'] = redis.from_url(redis_url)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key')
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # Session lifetime in seconds

Session(app)

@app.context_processor
def utility_processor():
    def calculate_percentage(part, whole):
        return round((part / whole) * 100, 1) if whole > 0 else 0
    return dict(calculate_percentage=calculate_percentage)

@app.template_filter('calculate_percentage')
def calculate_percentage_filter(part, whole):
    return round((part / whole) * 100, 1) if whole > 0 else 0

def get_subscribers_for_period(start_date, end_date, api_key, tag_id=None):
    all_subscribers = []
    page = 1
    per_page = 1000
    
    while True:  # Keep fetching until we get all subscribers
        params = {
            'from': start_date.isoformat() + 'Z',
            'to': end_date.isoformat() + 'Z',
            'page': page,
            'per_page': per_page
        }
        if tag_id:
            params['tag_id'] = tag_id
            
        print(f"Fetching page {page} with params: {params}")
        
        response = requests.get(
            f"{BASE_URL}subscribers",
            headers={"Authorization": f"Bearer {api_key}"},
            params=params
        )
        
        if response.status_code != 200:
            print(f"Error fetching subscribers: {response.text}")
            break
            
        data = response.json()
        subscribers = data.get('subscribers', [])
        
        if not subscribers:  # If no more subscribers, break
            break
            
        all_subscribers.extend(subscribers)
        page += 1
        
    return all_subscribers

def calculate_daily_counts(start_date, end_date, api_key, tag_id=None):
    """Calculate subscriber counts for each day in the range"""
    daily_counts = {}
    current_date = start_date
    
    while current_date <= end_date:
        next_date = current_date + timedelta(days=1)
        subscribers = get_subscribers_for_period(current_date, next_date, api_key, tag_id)
        
        daily_counts[current_date.strftime('%Y-%m-%d')] = len(subscribers)
        current_date = next_date
        
    return daily_counts

def get_available_tags(api_key):
    """Get available tags from ConvertKit API"""
    try:
        response = requests.get(
            'https://api.convertkit.com/v3/tags',
            headers={'Authorization': f'Bearer {api_key}'}
        )
        response.raise_for_status()
        data = response.json()
        return data.get('tags', [])
    except Exception as e:
        print(f"Error fetching tags: {str(e)}")
        return []

@app.route('/', methods=['GET', 'POST'])
def index():
    api_key = session.get('api_key')
    print(f"Index route - API key present: {api_key is not None}")
    print(f"Session contents: {dict(session)}")  # Debug log
    
    if not api_key:
        print("No API key found, redirecting to OAuth")  # Debug log
        return redirect(url_for('oauth_authorize'))
        
    try:
        tags = get_available_tags(api_key)
        return render_template('index.html', tags=tags)
    except Exception as e:
        print(f"Error in index route: {str(e)}")  # Debug log
        flash(str(e))
        return redirect(url_for('oauth_authorize'))

@app.route('/oauth/authorize')
def oauth_authorize():
    print("Starting OAuth authorization")
    convertkit = OAuth2Session(CLIENT_ID, redirect_uri=REDIRECT_URI)
    authorization_url, state = convertkit.authorization_url(AUTHORIZATION_BASE_URL)
    session['oauth_state'] = state
    return redirect(authorization_url)

def exchange_code_for_token(code):
    token_url = 'https://api.convertkit.com/oauth/token'
    
    token_data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'code': code,
        'grant_type': 'authorization_code',
        'redirect_uri': REDIRECT_URI
    }
    
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
    try:
        code = request.args.get('code')
        
        # Exchange code for access token
        token_response = requests.post(
            'https://api.convertkit.com/oauth/token',
            data={
                'grant_type': 'authorization_code',
                'code': code,
                'client_id': os.environ['CONVERTKIT_CLIENT_ID'],
                'client_secret': os.environ['CONVERTKIT_CLIENT_SECRET'],
                'redirect_uri': os.environ['OAUTH_REDIRECT_URI']
            }
        )
        
        token_data = token_response.json()
        print(f"Token response: {token_data}")  # Debug log
        
        # Store the access token in session
        session['api_key'] = token_data.get('access_token')
        print(f"Stored API key in session: {session.get('api_key')}")  # Debug log
        
        return redirect(url_for('index'))
        
    except Exception as e:
        print(f"Error in OAuth callback: {str(e)}")
        flash('Error during authentication')
        return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(port=5002, debug=True)