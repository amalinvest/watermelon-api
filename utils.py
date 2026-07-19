import requests
import json
import base64
import logging
import os
import re
from cache_manager import load_cache, save_cache
from companies import flatten_and_standardize, enrich_with_tickers
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

def parse_ticker_with_openrouter(perplexity_response):
    """
    Uses OpenRouter with Gemini to parse ticker from Perplexity response
    """
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://watermelon-api.com",
        "X-Title": "Watermelon API Ticker Parser"
    }

    prompt = f"""Return just the ticker symbol. If more than one ticker is mentioned, return the most prominent one. If no valid ticker is found, return 'null'.

{perplexity_response}

Response:"""

    payload = {
        "model": "google/gemini-2.5-flash",
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.1,
        "max_tokens": 10
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()

        if 'choices' in result and len(result['choices']) > 0:
            ticker = result['choices'][0]['message']['content'].strip()
            logger.info(f"OpenRouter parsed ticker: {ticker}")
            return ticker if ticker.lower() != 'null' else None
        return None
    except Exception as e:
        logger.error(f"OpenRouter API error: {str(e)}")
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

        # Use OpenRouter with Gemini to parse the ticker from Perplexity response
        ticker = parse_ticker_with_openrouter(content)

        # If OpenRouter fails, fallback to first word
        if not ticker:
            ticker = content.split()[0] if content.split() else None
        
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

def fetch_raw_data():
    """Fetches raw data from the API endpoint"""
    url = 'https://watermelonindex.glide.page/api/container/playerFunctionCritical/getAppSnapshot?reqid=cRtoCkoYLvPuumH1tQ03'
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
        companies = flatten_and_standardize(decoded_json['data'])
        processed_data = enrich_with_tickers(companies, get_stock_ticker)
        
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
