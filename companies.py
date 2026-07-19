import logging

logger = logging.getLogger(__name__)

def flatten_and_standardize(data):
    """
    Flattens and standardizes a Watermelon Index snapshot into a list of
    Company entries. Pure transform: no network calls, no caches.
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
            'sources': sources,
        }
        #Add complicity categories. Note that some categories may be absent.
        for category in ["Military", "Settlement production", "Population control", "Economic exploitation", "Cultural"]:
            if category in company_data['data']:
                company[category.lower().replace(' ', '_')] = company_data['data'][category]
        companies.append(company)


    # Process Campaigns data, adding campaign-related information to companies
    for campaign_data in data['Campaigns']:
        # Check if 'Companies' field exists in campaign data
        companies_field = campaign_data['data'].get('Companies', '')
        if not companies_field:
            logger.warning(f"Campaign {campaign_data.get('id', 'unknown')} has no 'Companies' field, skipping")
            continue

        company_ids = [x.strip() for x in companies_field.split(',')] #Handle potential multiple companies
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

def enrich_with_tickers(companies, resolve):
    """
    Adds a stockTicker to each Company using the resolve callable
    (companyName -> ticker symbol, or None if not publicly traded).
    """
    for company in companies:
        company['stockTicker'] = resolve(company['companyName'])
    return companies
