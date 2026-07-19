import companies


def make_snapshot(sheet1=None, campaigns=None):
    """Build a minimal Watermelon Index snapshot for tests."""
    return {
        'Sheet1': sheet1 if sheet1 is not None else [
            {
                'data': {
                    'Company Name': 'Test Company',
                    'Company name': 'test-company',
                    'Sector': 'Technology',
                    'Complicity details': 'Test details',
                    'Record last updated': {'repr': '2023-01-01'},
                    'Source': 'Source 1',
                    'Second source': 'Source 2',
                    'Military': 'Yes'
                }
            }
        ],
        'Campaigns': campaigns if campaigns is not None else [
            {
                'id': 'campaign-1',
                'data': {
                    'Campaign Name': 'Test Campaign',
                    'Companies': 'test-company',
                    'Description': 'Test campaign description',
                    'Location': 'Test Location'
                }
            }
        ]
    }


class TestFlattenAndStandardize:
    """Pure flatten: snapshot in, Company entries out. No mocks needed."""

    def test_flatten_and_standardize(self):
        """Test basic company data, sources, categories and campaign merge"""
        result = companies.flatten_and_standardize(make_snapshot())

        assert len(result) == 1
        company = result[0]

        # Check basic company data
        assert company['companyName'] == 'Test Company'
        assert company['companyId'] == 'test-company'
        assert company['sector'] == 'Technology'
        assert company['recordLastUpdated'] == '2023-01-01'

        # Check sources array
        assert company['sources'] == ['Source 1', 'Source 2']

        # Complicity categories are lowercased with underscores
        assert company['military'] == 'Yes'

        # Check campaign data was merged
        assert company['campaignName'] == 'Test Campaign'
        assert company['campaignId'] == 'campaign-1'

        # Ticker enrichment is a separate pass
        assert 'stockTicker' not in company

    def test_flatten_absent_categories_omitted(self):
        """Categories not present in the source stay absent from the Company"""
        result = companies.flatten_and_standardize(make_snapshot())
        company = result[0]

        assert 'settlement_production' not in company
        assert 'cultural' not in company

    def test_flatten_campaign_with_multiple_companies(self):
        """A campaign listing several companies is merged onto each of them"""
        sheet1 = []
        for i in (1, 2):
            sheet1.append({
                'data': {
                    'Company Name': f'Company {i}',
                    'Company name': f'company-{i}',
                    'Sector': 'Technology',
                    'Complicity details': 'Details',
                    'Record last updated': {'repr': '2023-01-01'},
                    'Source': 'Source 1'
                }
            })
        campaigns = [
            {
                'id': 'campaign-1',
                'data': {
                    'Campaign Name': 'Joint Campaign',
                    'Companies': 'company-1, company-2',
                    'Description': 'Targets both'
                }
            }
        ]

        result = companies.flatten_and_standardize(make_snapshot(sheet1, campaigns))

        assert len(result) == 2
        assert all(c['campaignName'] == 'Joint Campaign' for c in result)

    def test_flatten_missing_companies_field(self):
        """Campaigns without a 'Companies' field are skipped gracefully"""
        campaigns = [
            {
                'id': 'campaign-1',
                'data': {
                    'Campaign Name': 'Campaign Without Companies',
                    # Missing 'Companies' field
                    'Description': 'Test campaign description'
                }
            }
        ]

        # Should not raise KeyError
        result = companies.flatten_and_standardize(make_snapshot(campaigns=campaigns))

        assert len(result) == 1
        company = result[0]
        assert company['companyName'] == 'Test Company'
        # Campaign data should not be merged since no Companies field
        assert 'campaignName' not in company

    def test_flatten_empty_companies_field(self):
        """Campaigns with an empty 'Companies' field are skipped gracefully"""
        campaigns = [
            {
                'id': 'campaign-1',
                'data': {
                    'Campaign Name': 'Campaign With Empty Companies',
                    'Companies': '',  # Empty Companies field
                    'Description': 'Test campaign description'
                }
            }
        ]

        result = companies.flatten_and_standardize(make_snapshot(campaigns=campaigns))

        assert len(result) == 1
        assert 'campaignName' not in result[0]


class TestEnrichWithTickers:
    """Enrichment pass: resolver is injected, so a plain fake works."""

    def test_adds_ticker_from_resolver(self):
        entries = [{'companyName': 'Apple Inc.'}, {'companyName': 'Boeing'}]
        tickers = {'Apple Inc.': 'AAPL', 'Boeing': 'BA'}
        resolved_names = []

        def resolve(name):
            resolved_names.append(name)
            return tickers[name]

        result = companies.enrich_with_tickers(entries, resolve)

        assert result[0]['stockTicker'] == 'AAPL'
        assert result[1]['stockTicker'] == 'BA'
        assert resolved_names == ['Apple Inc.', 'Boeing']

    def test_none_for_unresolved_company(self):
        entries = [{'companyName': 'Private Company'}]

        result = companies.enrich_with_tickers(entries, lambda name: None)

        assert result[0]['stockTicker'] is None

    def test_enriches_in_place(self):
        entries = [{'companyName': 'Apple Inc.'}]

        result = companies.enrich_with_tickers(entries, lambda name: 'AAPL')

        assert result is entries
        assert entries[0]['stockTicker'] == 'AAPL'
