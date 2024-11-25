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

@app.context_processor
def utility_processor():
    def calculate_percentage(part, whole):
        return round((part / whole) * 100, 1) if whole > 0 else 0
    return dict(calculate_percentage=calculate_percentage)

@app.template_filter('calculate_percentage')
def calculate_percentage_filter(part, whole):
    return round((part / whole) * 100, 1) if whole > 0 else 0

def get_subscriber_counts(headers, total_params, tag_params, paperboy_params):
    """Get all subscriber counts with pagination - with timeout protection"""
    base_url = "https://api.convertkit.com/v4/subscribers"
    results = {'total_subscribers': 0, 'tagged_subscribers': 0, 'paperboy_subscribers': 0}
    
    try:
        MAX_PAGES = 5  # Limit pages to prevent timeout
        
        for params in [total_params, tag_params, paperboy_params]:
            count = 0
            page = 1
            
            while page <= MAX_PAGES:
                current_params = {**params, 'page': page, 'per_page': PER_PAGE_PARAM}
                print(f"Fetching page {page} with params: {current_params}")
                
                response = requests.get(
                    base_url,
                    headers=headers,
                    params=current_params,
                    timeout=5
                )
                response.raise_for_status()
                data = response.json()
                
                if not data.get('subscribers'):
                    break
                    
                count += len(data['subscribers'])
                
                # Break if this is the last page
                if len(data['subscribers']) < PER_PAGE_PARAM:
                    break
                    
                page += 1
                
            # Assign count to appropriate result
            if params == total_params:
                results['total_subscribers'] = count
            elif params == tag_params and tag_params.get('filter[tags]'):
                results['tagged_subscribers'] = count
            elif params == paperboy_params:
                results['paperboy_subscribers'] = count
                
        print(f"Final results: {results}")
        return results
        
    except requests.exceptions.RequestException as e:
        print(f"API Error: {str(e)}")
        if hasattr(e, 'response'):
            print(f"Response: {e.response.text}")
        raise Exception("Error fetching subscriber data - please try a smaller date range")

def get_available_tags(api_key):
    """Get available tags with error handling"""
    try:
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        response = requests.get(
            "https://api.convertkit.com/v4/tags",
            headers=headers,
            timeout=5
        )
        response.raise_for_status()
        data = response.json()
        print(f"Tags response: {data}")
        return data.get('tags', [])
    except Exception as e:
        print(f"Error fetching tags: {str(e)}")
        if hasattr(e, 'response'):
            print(f"Response content: {e.response.text}")
        return []

@app.route('/', methods=['GET', 'POST'])
def index():
    if 'access_token' not in session:
        return render_template('index.html', authenticated=False)
        
    api_key = session.get('access_token')
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    if request.method == 'POST':
        try:
            start_date = request.form['start_date']
            end_date = request.form['end_date']
            paperboy_date = request.form['paperboy_date']
            selected_tag = request.form.get('tag')
            
            print(f"Form data: start={start_date}, end={end_date}, tag={selected_tag}")
            
            total_params = {
                'from': f"{start_date}T00:00:00Z",
                'to': f"{end_date}T23:59:59Z"
            }
            
            tag_params = {**total_params}
            if selected_tag:
                tag_params['filter[tags]'] = selected_tag
                
            paperboy_params = {
                'from': f"{paperboy_date}T00:00:00Z",
                'to': f"{paperboy_date}T23:59:59Z"
            }
            
            results = get_subscriber_counts(headers, total_params, tag_params, paperboy_params)
            return render_template('index.html', 
                                results=results,
                                authenticated=True,
                                tags=get_available_tags(api_key))
                                
        except Exception as e:
            print(f"Error in index route: {str(e)}")
            flash(f'An error occurred: {str(e)}', 'error')
            return redirect(url_for('index'))
            
    return render_template('index.html', 
                         authenticated=True,
                         tags=get_available_tags(api_key))

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
    code = request.args.get('code')
    
    try:
        token_response = exchange_code_for_token(code)
        session['access_token'] = token_response['access_token']
        session['api_key'] = token_response['access_token']
        session.permanent = True
        return redirect(url_for('index'))
    except Exception as e:
        print(f"Error in OAuth callback: {str(e)}")
        return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(port=5002, debug=True)