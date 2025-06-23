import requests
import json
import base64
import logging
import os
import re
from cache_manager import load_cache, save_cache
from dotenv import load_dotenv

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

load_dotenv()  # Load environment variables from .env file

# Cache for stock tickers
TICKER_CACHE_KEY = 'ticker'
ticker_cache = load_cache(TICKER_CACHE_KEY) or {}

def search_with_perplexity(query):
    """
    Performs a search using Perplexity API
    """
    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {os.getenv('PERPLEXITY_API_KEY')}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "sonar",
        "messages": [
            {
                "role": "system",
                "content": "You are a financial data assistant. Return only factual information about stock tickers and company listings. If uncertain, say so."
            },
            {
                "role": "user",
                "content": query
            }
        ],
        "temperature": 0.2,
        "max_tokens": 150,
        "search_recency_filter": "month"
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Perplexity API error: {str(e)}")
        return None

def is_valid_ticker(ticker):
    """
    Validates if a string looks like a valid stock ticker.
    Valid formats:
    - 1-5 letters (NYSE/NASDAQ)
    - 4-5 letters ending in Y (ADR)
    - Letters followed by .X where X is exchange code
    - May have up to 2 digits but not at start
    - OTC/ADR tickers can be 5-6 letters
    """
    if not ticker or len(ticker) > 10:  # Allow longer tickers for OTC/ADR with exchange codes
        return False
    
    # Basic patterns for different types of tickers
    patterns = [
        r'^[A-Z]{1,5}$',                    # Regular NYSE/NASDAQ
        r'^[A-Z]{4,5}Y$',                   # ADRs ending in Y
        r'^[A-Z]{2,6}F$',                   # Foreign ordinary shares
        r'^[A-Z]{4,6}(\.[A-Z]{1,2})?$',    # OTC/ADR tickers (like ABBNY)
        r'^[A-Z]{1,4}\d{1,2}(\.[A-Z]{1,2})?$'  # Tickers with numbers
    ]
    
    return any(bool(re.match(pattern, ticker)) for pattern in patterns)

def get_stock_ticker(company_name):
    """
    Uses Perplexity search to find the stock ticker for a publicly traded company.
    Results are cached persistently to avoid redundant API calls.
    Returns None if the company is not publicly traded or if the ticker cannot be found.
    """
    global ticker_cache
    
    # Check cache first
    if company_name in ticker_cache:
        return ticker_cache[company_name]
        
    try:
        # Clean company name
        search_name = company_name.replace(".", "").replace(",", "")
        
        # Search focusing on major exchanges and ADRs
        search_query = f"What is the stock ticker symbol for {search_name} in the US (NYSE, NASDAQ, OTC markets, or as an ADR)? Only return the ticker symbol, no explanation. Return null if not found."
        logger.info(f"Searching for ticker with query: {search_query}")
        
        response = search_with_perplexity(search_query)
        if not response or 'choices' not in response:
            return None
            
        content = response['choices'][0]['message']['content'].strip()
        logger.info(f"Perplexity returned '{content}' for {company_name}")

        # Handle null-like responses
        if content.lower().strip('.') in ['null', 'none', '-', 'n/a']:
            ticker_cache[company_name] = None
            save_cache(ticker_cache, TICKER_CACHE_KEY)
            return None

        # Extract ticker symbol from response using regex
        # Look for valid ticker patterns in the response, prioritizing longer matches
        import re

        # Find all potential ticker matches
        all_matches = []
        ticker_patterns = [
            r'\b([A-Z]{4,6}Y)\b',                   # ADRs ending in Y (prioritize first)
            r'\b([A-Z]{2,6}F)\b',                   # Foreign ordinary shares
            r'\b([A-Z]{4,6}(?:\.[A-Z]{1,2})?)\b',   # OTC/ADR tickers
            r'\b([A-Z]{1,4}\d{1,2}(?:\.[A-Z]{1,2})?)\b',  # Tickers with numbers
            r'\b([A-Z]{1,5})\b'                     # Regular NYSE/NASDAQ (last to avoid company names)
        ]

        for pattern in ticker_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if is_valid_ticker(match):
                    # Skip if it's likely part of the company name in the query
                    company_words = company_name.upper().split()
                    if match not in company_words:
                        all_matches.append(match)

        # Choose the longest valid ticker (more specific)
        ticker = max(all_matches, key=len) if all_matches else None

        # Fallback to first word if no valid ticker found in patterns
        if not ticker:
            ticker = content.split()[0]
        
        # Validate the ticker format
        if not is_valid_ticker(ticker):
            logger.warning(f"Invalid ticker format received for {company_name}: {ticker}")
            ticker_cache[company_name] = None
            save_cache(ticker_cache, TICKER_CACHE_KEY)
            return None
        
        # Cache the result
        ticker_cache[company_name] = ticker
        save_cache(ticker_cache, TICKER_CACHE_KEY)
        
        return ticker
    except Exception as e:
        logger.error(f"Error getting stock ticker for {company_name}: {str(e)}")
        return None

def flatten_and_standardize(data):
    """
    Flattens and standardizes the input JSON data into a list of JSON entries 
    representing companies and their associated data.
    """

    companies = []
    # Process Sheet1 data
    for company_data in data['Sheet1']:
        # Get all sources in order
        sources = []
        source_fields = ['Source', 'Second source', 'Information source 3', 'Information source 4']
        for field in source_fields:
            value = company_data['data'].get(field, '')
            if value:
                sources.append(value)

        company = {
            'companyName': company_data['data']['Company Name'],
            'companyId': company_data['data']['Company name'],
            'sector': company_data['data']['Sector'],
            'complicityDetails': company_data['data']['Complicity details'],
            'recordLastUpdated': company_data['data']['Record last updated']['repr'],
            'sources': sources,  # Add sources array
            'stockTicker': get_stock_ticker(company_data['data']['Company Name'])  # Add stock ticker
        }
        #Add complicity categories. Note that some categories may be absent.
        for category in ["Military", "Settlement production", "Population control", "Economic exploitation", "Cultural"]:
            if category in company_data['data']:
                company[category.lower().replace(' ', '_')] = company_data['data'][category]
        companies.append(company)


    # Process Campaigns data, adding campaign-related information to companies
    for campaign_data in data['Campaigns']:
        print(campaign_data['data']['Companies'])
        company_ids = [x.strip() for x in campaign_data['data']['Companies'].split(',')] #Handle potential multiple companies
        for company_id in company_ids:
            for i, company in enumerate(companies):
                if company['companyId'] == company_id:
                    campaign_info = campaign_data['data']
                    company['campaignName'] = campaign_info.get('Campaign Name', '')
                    company['campaignId'] = campaign_data['id']
                    company['campaignDescription'] = campaign_info.get('Description', '')
                    company['campaignLocation'] = campaign_info.get('Location', '')
                    company['campaignOutcomes'] = campaign_info.get('Outcomes', '')
                    company['campaignAimsAchieved'] = campaign_info.get('Aims achieved', '')
                    company['campaignGroups'] = campaign_info.get('Campaign Groups', '')
                    company['campaignMethods'] = campaign_info.get('9f119b48c6e3251dc6be2ae8a8b969c4', '')
                    campaign_links = campaign_info.get('Campaign link', {}).get('$arrayItems', [])
                    company['campaignLinks'] = [item for item in campaign_links if item]
                    company['targetAim'] = campaign_info.get('Target aim: Divestment,Contract,Sponsor,Supply,Operations,Position,Other', '')
                    break

    return companies

def fetch_raw_data():
    """Fetches raw data from the API endpoint"""
    url = 'https://watermelonindex.glide.page/api/container/playerFunctionCritical/getAppSnapshot?reqid=1PKuPWeIywUcbOBGX5P9'
    headers = {
        'accept': '*/*',
        'content-type': 'application/json',
        'origin': 'https://watermelonindex.glide.page',
        'referer': 'https://watermelonindex.glide.page/dl/companies',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }
    payload = {"appID": "57dVVMXNFIuBOYtiLIaP"}

    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    
    data_snapshot_url = response.json().get('dataSnapshot')
    if not data_snapshot_url:
        raise ValueError("dataSnapshot URL not found in response")
    
    snapshot_response = requests.get(data_snapshot_url)
    snapshot_response.raise_for_status()
    
    decoded_bytes = base64.b64decode(snapshot_response.text)
    return json.loads(decoded_bytes)

def fetch_and_decode_data():
    """Main function to fetch and process data with caching"""
    cached_data = load_cache()
    if cached_data and 'processed_data' in cached_data:
        logger.info("Returning processed data from cache")
        return {'data': cached_data['raw_data'], 'processed_data': cached_data['processed_data']}

    try:
        decoded_json = fetch_raw_data()
        processed_data = flatten_and_standardize(decoded_json['data'])
        
        cache_data = {
            'raw_data': decoded_json,
            'processed_data': processed_data
        }
        save_cache(cache_data)
        
        return cache_data
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {str(e)}")
        if hasattr(e, 'response'):
            logger.error(f"Error response: {e.response.text}")
        raise
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        raise
