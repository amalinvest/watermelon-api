import requests
import json
import base64
import logging
from cache_manager import load_cache, save_cache

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

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

def fetch_and_decode_data():
    # Try to get data from cache first
    cached_data = load_cache()
    if cached_data is not None:
        return cached_data

    # API endpoint and headers
    url = 'https://watermelonindex.glide.page/api/container/playerFunctionCritical/getAppSnapshot?reqid=1PKuPWeIywUcbOBGX5P9'
    headers = {
        'accept': '*/*',
        'accept-language': 'en-US,en;q=0.9',
        'content-type': 'application/json',
        'dnt': '1',
        'fly-customer-request-id': '1PKuPWeIywUcbOBGX5P9',
        'origin': 'https://watermelonindex.glide.page',
        'priority': 'u=1, i',
        'referer': 'https://watermelonindex.glide.page/dl/companies',
        'sec-ch-ua': '"Not?A_Brand";v="99", "Chromium";v="130"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'same-origin',
        'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
        'x-glide-anonymous-user': '',  
        'x-glide-attempt': '1'
    }
    
    # Request payload
    payload = {
        "appID": "57dVVMXNFIuBOYtiLIaP"
    }

    try:
        # Log request details
        logger.debug(f"Making request to: {url}")
        logger.debug(f"Headers: {json.dumps(headers, indent=2)}")
        logger.debug(f"Payload: {json.dumps(payload, indent=2)}")

        # Make the request
        response = requests.post(url, headers=headers, json=payload)
        
        # Log response details
        logger.debug(f"Response status code: {response.status_code}")
        logger.debug(f"Response headers: {json.dumps(dict(response.headers), indent=2)}")
        logger.debug(f"Response content: {response.text[:500]}...")  # First 500 chars
        
        response.raise_for_status()
        
        # Extract the dataSnapshot URL from the response
        data = response.json()
        data_snapshot_url = data.get('dataSnapshot')
        if not data_snapshot_url:
            raise ValueError("dataSnapshot URL not found in response")
        
        # Fetch the base64 encoded data
        snapshot_response = requests.get(data_snapshot_url)
        snapshot_response.raise_for_status()
        
        # Decode base64 data
        encoded_data = snapshot_response.text
        decoded_bytes = base64.b64decode(encoded_data)
        decoded_json = json.loads(decoded_bytes)
        
        # Save the decoded data to cache
        save_cache(decoded_json)
        
        return decoded_json
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"Error response: {e.response.text}")
        raise
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        raise
