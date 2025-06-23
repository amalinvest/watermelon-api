import pytest
import json
from unittest.mock import patch, Mock, MagicMock
import requests
import utils


class TestUtils:
    """Test suite for utils module"""

    def setup_method(self):
        """Setup for each test method"""
        self.sample_company_data = {
            'Sheet1': [
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
            'Campaigns': [
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

    def test_is_valid_ticker_valid_cases(self):
        """Test is_valid_ticker with valid ticker formats"""
        valid_tickers = [
            'AAPL',      # Regular NYSE/NASDAQ
            'GOOGL',     # Regular NYSE/NASDAQ
            'ABBNY',     # ADR ticker
            'ADDYY',     # ADR ending in Y
            'EADSY',     # Foreign ordinary shares
            'BAESY',     # ADR format
            'A',         # Single letter
            'ABCDE'      # 5 letters
        ]
        
        for ticker in valid_tickers:
            assert utils.is_valid_ticker(ticker), f"Ticker {ticker} should be valid"

    def test_is_valid_ticker_invalid_cases(self):
        """Test is_valid_ticker with invalid ticker formats"""
        invalid_tickers = [
            '',           # Empty string
            None,         # None value
            '123ABC',     # Starts with numbers
            'ABCDEFGHIJK', # Too long
            'abc',        # Lowercase
            'AB-CD',      # Contains hyphen
            'AB CD'       # Contains space
        ]
        
        for ticker in invalid_tickers:
            assert not utils.is_valid_ticker(ticker), f"Ticker {ticker} should be invalid"

    @patch('utils.search_with_perplexity')
    @patch('utils.save_cache')
    @patch('utils.load_cache')
    def test_get_stock_ticker_cached(self, mock_load_cache, mock_save_cache, mock_search):
        """Test get_stock_ticker when result is cached"""
        # Setup cache to return cached ticker
        utils.ticker_cache = {'Test Company': 'TEST'}
        
        result = utils.get_stock_ticker('Test Company')
        
        assert result == 'TEST'
        mock_search.assert_not_called()

    @patch('utils.search_with_perplexity')
    @patch('utils.save_cache')
    @patch('utils.load_cache')
    def test_get_stock_ticker_api_success(self, mock_load_cache, mock_save_cache, mock_search):
        """Test get_stock_ticker with successful API response"""
        utils.ticker_cache = {}
        
        # Mock successful Perplexity response
        mock_search.return_value = {
            'choices': [{'message': {'content': 'AAPL'}}]
        }
        
        result = utils.get_stock_ticker('Apple Inc.')
        
        assert result == 'AAPL'
        assert utils.ticker_cache['Apple Inc.'] == 'AAPL'
        mock_save_cache.assert_called_once()

    @patch('utils.search_with_perplexity')
    @patch('utils.save_cache')
    def test_get_stock_ticker_null_response(self, mock_save_cache, mock_search):
        """Test get_stock_ticker with null response"""
        utils.ticker_cache = {}
        
        # Mock null response
        mock_search.return_value = {
            'choices': [{'message': {'content': 'null'}}]
        }
        
        result = utils.get_stock_ticker('Private Company')
        
        assert result is None
        assert utils.ticker_cache['Private Company'] is None

    @patch('utils.search_with_perplexity')
    def test_get_stock_ticker_api_error(self, mock_search):
        """Test get_stock_ticker with API error"""
        utils.ticker_cache = {}
        
        # Mock API error
        mock_search.return_value = None
        
        result = utils.get_stock_ticker('Test Company')
        
        assert result is None

    @patch('utils.search_with_perplexity')
    @patch('utils.save_cache')
    def test_get_stock_ticker_invalid_format(self, mock_save_cache, mock_search):
        """Test get_stock_ticker with invalid ticker format"""
        utils.ticker_cache = {}

        # Mock response with invalid ticker
        mock_search.return_value = {
            'choices': [{'message': {'content': '123INVALID'}}]
        }

        result = utils.get_stock_ticker('Test Company')

        assert result is None
        assert utils.ticker_cache['Test Company'] is None

    @patch('utils.search_with_perplexity')
    @patch('utils.save_cache')
    def test_get_stock_ticker_extracts_from_sentence(self, mock_save_cache, mock_search):
        """Test get_stock_ticker extracts ticker from descriptive response"""
        utils.ticker_cache = {}

        # Mock response with ticker embedded in sentence
        mock_search.return_value = {
            'choices': [{'message': {'content': 'The stock ticker symbol for ABB Group in the US OTC market is ABBNY.'}}]
        }

        result = utils.get_stock_ticker('ABB Group')

        assert result == 'ABBNY'
        assert utils.ticker_cache['ABB Group'] == 'ABBNY'

    @patch('utils.parse_ticker_with_openrouter')
    @patch('utils.search_with_perplexity')
    @patch('utils.save_cache')
    def test_get_stock_ticker_with_openrouter_parsing(self, mock_save_cache, mock_search, mock_openrouter):
        """Test get_stock_ticker uses OpenRouter for parsing"""
        utils.ticker_cache = {}

        # Mock Perplexity response
        mock_search.return_value = {
            'choices': [{'message': {'content': 'The stock ticker symbol for Allianz in the US OTC markets is ALIZF.'}}]
        }

        # Mock OpenRouter parsing
        mock_openrouter.return_value = 'ALIZF'

        result = utils.get_stock_ticker('Allianz')

        assert result == 'ALIZF'
        assert utils.ticker_cache['Allianz'] == 'ALIZF'
        mock_openrouter.assert_called_once()

    @patch('utils.parse_ticker_with_openrouter')
    @patch('utils.search_with_perplexity')
    @patch('utils.save_cache')
    def test_get_stock_ticker_openrouter_fallback(self, mock_save_cache, mock_search, mock_openrouter):
        """Test fallback when OpenRouter fails"""
        utils.ticker_cache = {}

        # Mock Perplexity response
        mock_search.return_value = {
            'choices': [{'message': {'content': 'AAPL'}}]
        }

        # Mock OpenRouter failure
        mock_openrouter.return_value = None

        result = utils.get_stock_ticker('Apple')

        assert result == 'AAPL'  # Should fallback to first word
        mock_openrouter.assert_called_once()

    @patch('requests.post')
    def test_parse_ticker_with_openrouter_success(self, mock_post):
        """Test successful OpenRouter ticker parsing"""
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {
            'choices': [{'message': {'content': 'ALIZF'}}]
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = utils.parse_ticker_with_openrouter("The stock ticker symbol for Allianz is ALIZF")

        assert result == 'ALIZF'
        mock_post.assert_called_once()

    @patch('requests.post')
    def test_parse_ticker_with_openrouter_null_response(self, mock_post):
        """Test OpenRouter parsing with null response"""
        # Mock null response
        mock_response = Mock()
        mock_response.json.return_value = {
            'choices': [{'message': {'content': 'null'}}]
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = utils.parse_ticker_with_openrouter("This company is not publicly traded")

        assert result is None

    @patch('requests.post')
    def test_parse_ticker_with_openrouter_error(self, mock_post):
        """Test OpenRouter parsing with API error"""
        # Mock API error
        mock_post.side_effect = requests.exceptions.RequestException("API Error")

        result = utils.parse_ticker_with_openrouter("Test input")

        assert result is None

    @patch('requests.post')
    def test_search_with_perplexity_success(self, mock_post):
        """Test successful Perplexity API call"""
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {'choices': [{'message': {'content': 'AAPL'}}]}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        result = utils.search_with_perplexity('Test query')
        
        assert result == {'choices': [{'message': {'content': 'AAPL'}}]}
        mock_post.assert_called_once()

    @patch('requests.post')
    def test_search_with_perplexity_error(self, mock_post):
        """Test Perplexity API call with error"""
        # Mock request exception
        mock_post.side_effect = requests.exceptions.RequestException("API Error")
        
        result = utils.search_with_perplexity('Test query')
        
        assert result is None

    @patch('utils.get_stock_ticker')
    def test_flatten_and_standardize(self, mock_get_ticker):
        """Test flatten_and_standardize function"""
        mock_get_ticker.return_value = 'TEST'

        result = utils.flatten_and_standardize(self.sample_company_data)

        assert len(result) == 1
        company = result[0]

        # Check basic company data
        assert company['companyName'] == 'Test Company'
        assert company['companyId'] == 'test-company'
        assert company['sector'] == 'Technology'
        assert company['stockTicker'] == 'TEST'

        # Check sources array
        assert company['sources'] == ['Source 1', 'Source 2']

        # Check campaign data was merged
        assert company['campaignName'] == 'Test Campaign'
        assert company['campaignId'] == 'campaign-1'

    @patch('utils.get_stock_ticker')
    def test_flatten_and_standardize_missing_companies_field(self, mock_get_ticker):
        """Test flatten_and_standardize handles missing 'Companies' field gracefully"""
        mock_get_ticker.return_value = 'TEST'

        # Data with campaign missing 'Companies' field
        test_data = {
            'Sheet1': [
                {
                    'data': {
                        'Company Name': 'Test Company',
                        'Company name': 'test-company',
                        'Sector': 'Technology',
                        'Complicity details': 'Test details',
                        'Record last updated': {'repr': '2023-01-01'},
                        'Source': 'Source 1'
                    }
                }
            ],
            'Campaigns': [
                {
                    'id': 'campaign-1',
                    'data': {
                        'Campaign Name': 'Campaign Without Companies',
                        # Missing 'Companies' field
                        'Description': 'Test campaign description'
                    }
                }
            ]
        }

        # Should not raise KeyError
        result = utils.flatten_and_standardize(test_data)

        assert len(result) == 1
        company = result[0]
        assert company['companyName'] == 'Test Company'
        # Campaign data should not be merged since no Companies field
        assert 'campaignName' not in company

    @patch('utils.get_stock_ticker')
    def test_flatten_and_standardize_empty_companies_field(self, mock_get_ticker):
        """Test flatten_and_standardize handles empty 'Companies' field gracefully"""
        mock_get_ticker.return_value = 'TEST'

        # Data with campaign having empty 'Companies' field
        test_data = {
            'Sheet1': [
                {
                    'data': {
                        'Company Name': 'Test Company',
                        'Company name': 'test-company',
                        'Sector': 'Technology',
                        'Complicity details': 'Test details',
                        'Record last updated': {'repr': '2023-01-01'},
                        'Source': 'Source 1'
                    }
                }
            ],
            'Campaigns': [
                {
                    'id': 'campaign-1',
                    'data': {
                        'Campaign Name': 'Campaign With Empty Companies',
                        'Companies': '',  # Empty Companies field
                        'Description': 'Test campaign description'
                    }
                }
            ]
        }

        # Should not raise error and should skip empty Companies field
        result = utils.flatten_and_standardize(test_data)

        assert len(result) == 1
        company = result[0]
        assert company['companyName'] == 'Test Company'
        # Campaign data should not be merged since Companies field is empty
        assert 'campaignName' not in company

    @patch('requests.post')
    @patch('requests.get')
    def test_fetch_raw_data_success(self, mock_get, mock_post):
        """Test successful fetch_raw_data"""
        # Mock initial POST response
        mock_post_response = Mock()
        mock_post_response.json.return_value = {'dataSnapshot': 'http://test.com/snapshot'}
        mock_post_response.raise_for_status.return_value = None
        mock_post.return_value = mock_post_response
        
        # Mock snapshot GET response
        test_data = {'test': 'data'}
        encoded_data = json.dumps(test_data).encode()
        import base64
        encoded_b64 = base64.b64encode(encoded_data).decode()
        
        mock_get_response = Mock()
        mock_get_response.text = encoded_b64
        mock_get_response.raise_for_status.return_value = None
        mock_get.return_value = mock_get_response
        
        result = utils.fetch_raw_data()
        
        assert result == test_data

    @patch('requests.post')
    def test_fetch_raw_data_no_snapshot_url(self, mock_post):
        """Test fetch_raw_data when dataSnapshot URL is missing"""
        mock_response = Mock()
        mock_response.json.return_value = {}  # No dataSnapshot key
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        with pytest.raises(ValueError, match="dataSnapshot URL not found"):
            utils.fetch_raw_data()

    @patch('utils.fetch_raw_data')
    @patch('utils.flatten_and_standardize')
    @patch('utils.save_cache')
    @patch('utils.load_cache')
    def test_fetch_and_decode_data_cached(self, mock_load_cache, mock_save_cache, 
                                         mock_flatten, mock_fetch_raw):
        """Test fetch_and_decode_data with cached data"""
        cached_data = {
            'raw_data': {'test': 'raw'},
            'processed_data': {'test': 'processed'}
        }
        mock_load_cache.return_value = cached_data
        
        result = utils.fetch_and_decode_data()
        
        assert result['processed_data'] == {'test': 'processed'}
        mock_fetch_raw.assert_not_called()
        mock_flatten.assert_not_called()

    @patch('utils.fetch_raw_data')
    @patch('utils.flatten_and_standardize')
    @patch('utils.save_cache')
    @patch('utils.load_cache')
    def test_fetch_and_decode_data_fresh(self, mock_load_cache, mock_save_cache,
                                        mock_flatten, mock_fetch_raw):
        """Test fetch_and_decode_data without cached data"""
        mock_load_cache.return_value = None
        mock_fetch_raw.return_value = {'data': self.sample_company_data}
        mock_flatten.return_value = [{'company': 'data'}]

        result = utils.fetch_and_decode_data()

        assert 'processed_data' in result
        assert 'raw_data' in result  # Fixed: should be 'raw_data' not 'data'
        mock_fetch_raw.assert_called_once()
        mock_flatten.assert_called_once()
        mock_save_cache.assert_called_once()
