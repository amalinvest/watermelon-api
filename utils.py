import requests
import json
import base64
import logging
import os
from cache_manager import load_cache, save_cache
from together import Together
from dotenv import load_dotenv

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

load_dotenv()  # Load environment variables from .env file

# Initialize Together AI client
together = Together(api_key=os.getenv('TOGETHER_API_KEY'))

def get_stock_ticker(company_name):
    """
    Uses Together AI to find the stock ticker for a publicly traded company.
    Returns None if the company is not publicly traded or if the ticker cannot be found.
    """
    try:
        messages = [
            {"role": "system", "content": "You are a helpful assistant that provides stock ticker symbols for publicly traded companies. Only return the ticker symbol or 'NONE', with no additional text."},
            {"role": "user", "content": f"What is the stock ticker symbol for {company_name}? If the company is not publicly traded or you're unsure, return 'NONE'."}
        ]
        
        response = together.chat.completions.create(
            model="meta-llama/Meta-Llama-3-8B-Instruct-Turbo",
            messages=messages,
            temperature=0.1,
            max_tokens=10
        )
        
        ticker = response.choices[0].message.content.strip()
        return None if ticker == "NONE" else ticker
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
