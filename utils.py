import requests
import json
import base64
import logging
import os
import re
from cache_manager import load_cache, save_cache
from together import Together
from dotenv import load_dotenv
from tavily import TavilyClient

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

load_dotenv()  # Load environment variables from .env file

# Initialize Together AI client
together = Together(api_key=os.getenv('TOGETHER_API_KEY'))

# Initialize Tavily client
tavily_client = TavilyClient(api_key=os.getenv('TAVILY_API_KEY'))

# Cache for stock tickers
TICKER_CACHE_KEY = 'ticker'
ticker_cache = load_cache(TICKER_CACHE_KEY) or {}

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
    Uses Tavily search to find the stock ticker for a publicly traded company.
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
        search_query = f'"{search_name}" (NYSE OR NASDAQ OR OTC OR OTCQX OR OTCQB OR "Pink Sheet" OR ADR OR "American Depositary Receipt") stock ticker symbol'
        logger.info(f"Searching for ticker with query: {search_query}")
        response = tavily_client.search(search_query)
        
        # Log search results for debugging
        logger.debug("Search results:")
        for idx, result in enumerate(response.get('results', [])[:3]):
            logger.debug(f"Result {idx + 1}: {result.get('title', '')} - {result.get('content', '')[:200]}...")
        
        # Use Together AI to extract the ticker from search results
        content = "\n".join(r['content'] for r in response.get('results', [])[:3])
        messages = [
            {"role": "system", "content": """You are a helpful assistant that extracts stock ticker symbols from text.
Your task is to find tickers from these exchanges ONLY:
- NYSE (New York Stock Exchange)
- NASDAQ
- OTC Markets (OTCQX, OTCQB, Pink Sheets)
- ADRs (American Depositary Receipts)

Follow these rules strictly:
1. Return ONLY the ticker symbol or 'NONE' with no additional text
2. If multiple tickers exist for the same company, prioritize in this order:
   a) NYSE/NASDAQ listings
   b) ADR tickers (usually 5 letters ending in Y or similar)
   c) OTC/Pink Sheet tickers
3. Do not return tickers from other exchanges (e.g., LSE, TSX, etc.)
4. If unsure or no valid ticker is found, return 'NONE'
5. Never guess or make up tickers"""},
            {"role": "user", "content": f"What is the stock ticker symbol for {company_name} in this text? Return 'NONE' if not found or unsure.\n\nText: {content}"}
        ]
        
        response = together.chat.completions.create(
            model="meta-llama/Meta-Llama-3-8B-Instruct-Turbo",
            messages=messages,
            temperature=0.1,
            max_tokens=10
        )
        
        ticker = response.choices[0].message.content.strip()
        logger.info(f"LLM returned ticker '{ticker}' for {company_name}")
        
        # Validate the ticker format
        if ticker != "NONE" and not is_valid_ticker(ticker):
            logger.warning(f"Invalid ticker format received for {company_name}: {ticker}")
            ticker = "NONE"
        
        result = None if ticker == "NONE" else ticker
        
        # Cache the result
        ticker_cache[company_name] = result
        save_cache(ticker_cache, TICKER_CACHE_KEY)
        
        return result
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
