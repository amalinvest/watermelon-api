import pytest
import json
import base64
import requests_mock
from unittest.mock import patch, Mock
from app import app
import utils


class TestIntegration:
    """Integration tests for the watermelon-api"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client

    @pytest.fixture
    def sample_external_data(self):
        """Sample data that would come from external API"""
        return {
            'data': {
                'Sheet1': [
                    {
                        'data': {
                            'Company Name': 'Apple Inc.',
                            'Company name': 'apple-inc',
                            'Sector': 'Technology',
                            'Complicity details': 'Test complicity details',
                            'Record last updated': {'repr': '2023-12-01'},
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
                            'Campaign Name': 'Tech Boycott',
                            'Companies': 'apple-inc',
                            'Description': 'Campaign against tech companies',
                            'Location': 'Global'
                        }
                    }
                ]
            }
        }

    @pytest.mark.integration
    def test_full_api_flow_with_mocked_externals(self, client, sample_external_data):
        """Test complete API flow with mocked external services"""
        # Clear any existing cache
        utils.ticker_cache = {}
        
        # Encode the sample data as it would come from the external API
        encoded_data = base64.b64encode(json.dumps(sample_external_data).encode()).decode()
        
        with requests_mock.Mocker() as m:
            # Mock the initial POST request to get dataSnapshot URL
            m.post(
                'https://watermelonindex.glide.page/api/container/playerFunctionCritical/getAppSnapshot',
                json={'dataSnapshot': 'http://test.com/snapshot'}
            )
            
            # Mock the GET request to fetch the actual data
            m.get('http://test.com/snapshot', text=encoded_data)
            
            # Mock Perplexity API for ticker lookup
            m.post(
                'https://api.perplexity.ai/chat/completions',
                json={'choices': [{'message': {'content': 'AAPL'}}]}
            )
            
            # Make request to our API
            response = client.get('/api')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            
            # Verify the response structure
            assert isinstance(data, list)
            assert len(data) == 1
            
            company = data[0]
            assert company['companyName'] == 'Apple Inc.'
            assert company['companyId'] == 'apple-inc'
            assert company['sector'] == 'Technology'
            assert company['stockTicker'] == 'AAPL'
            assert company['campaignName'] == 'Tech Boycott'

    @pytest.mark.integration
    def test_api_with_cache_hit(self, client, sample_external_data):
        """Test API behavior when cache is hit"""
        # Pre-populate cache
        cache_data = {
            'raw_data': sample_external_data,
            'processed_data': [
                {
                    'companyName': 'Cached Company',
                    'companyId': 'cached-company',
                    'sector': 'Cached Sector',
                    'stockTicker': 'CACHE'
                }
            ]
        }
        
        with patch('utils.load_cache') as mock_load_cache:
            mock_load_cache.return_value = cache_data
            
            response = client.get('/api')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            
            # Should return cached data
            assert len(data) == 1
            assert data[0]['companyName'] == 'Cached Company'
            assert data[0]['stockTicker'] == 'CACHE'

    @pytest.mark.integration
    def test_external_api_failure_handling(self, client):
        """Test handling of external API failures"""
        with requests_mock.Mocker() as m:
            # Mock external API failure
            m.post(
                'https://watermelonindex.glide.page/api/container/playerFunctionCritical/getAppSnapshot',
                status_code=500
            )
            
            response = client.get('/api')
            
            assert response.status_code == 500
            data = json.loads(response.data)
            assert 'error' in data

    @pytest.mark.integration
    def test_perplexity_api_failure_graceful_handling(self, client, sample_external_data):
        """Test that Perplexity API failures don't break the main flow"""
        # Clear ticker cache
        utils.ticker_cache = {}
        
        encoded_data = base64.b64encode(json.dumps(sample_external_data).encode()).decode()
        
        with requests_mock.Mocker() as m:
            # Mock successful main API
            m.post(
                'https://watermelonindex.glide.page/api/container/playerFunctionCritical/getAppSnapshot',
                json={'dataSnapshot': 'http://test.com/snapshot'}
            )
            m.get('http://test.com/snapshot', text=encoded_data)
            
            # Mock Perplexity API failure
            m.post(
                'https://api.perplexity.ai/chat/completions',
                status_code=500
            )
            
            response = client.get('/api')
            
            # Should still succeed, just without stock tickers
            assert response.status_code == 200
            data = json.loads(response.data)
            
            assert len(data) == 1
            company = data[0]
            assert company['companyName'] == 'Apple Inc.'
            assert company['stockTicker'] is None  # Should be None due to API failure

    @pytest.mark.integration
    def test_malformed_external_data_handling(self, client):
        """Test handling of malformed data from external API"""
        with requests_mock.Mocker() as m:
            # Mock successful initial request
            m.post(
                'https://watermelonindex.glide.page/api/container/playerFunctionCritical/getAppSnapshot',
                json={'dataSnapshot': 'http://test.com/snapshot'}
            )
            
            # Mock malformed data response
            m.get('http://test.com/snapshot', text='invalid-base64-data')
            
            response = client.get('/api')
            
            assert response.status_code == 500
            data = json.loads(response.data)
            assert 'error' in data

    @pytest.mark.integration
    def test_missing_datasnapshot_url(self, client):
        """Test handling when dataSnapshot URL is missing"""
        with requests_mock.Mocker() as m:
            # Mock response without dataSnapshot
            m.post(
                'https://watermelonindex.glide.page/api/container/playerFunctionCritical/getAppSnapshot',
                json={'some_other_field': 'value'}
            )
            
            response = client.get('/api')
            
            assert response.status_code == 500
            data = json.loads(response.data)
            assert 'error' in data
            assert 'dataSnapshot URL not found' in data['error']

    @pytest.mark.integration
    def test_ticker_caching_behavior(self, client, sample_external_data):
        """Test that ticker results are properly cached"""
        # Clear ticker cache
        utils.ticker_cache = {}
        
        encoded_data = base64.b64encode(json.dumps(sample_external_data).encode()).decode()
        
        with requests_mock.Mocker() as m:
            # Mock main API
            m.post(
                'https://watermelonindex.glide.page/api/container/playerFunctionCritical/getAppSnapshot',
                json={'dataSnapshot': 'http://test.com/snapshot'}
            )
            m.get('http://test.com/snapshot', text=encoded_data)
            
            # Mock Perplexity API
            m.post(
                'https://api.perplexity.ai/chat/completions',
                json={'choices': [{'message': {'content': 'AAPL'}}]}
            )
            
            # First request should call Perplexity
            response1 = client.get('/api')
            assert response1.status_code == 200
            
            # Verify ticker was cached
            assert 'Apple Inc.' in utils.ticker_cache
            assert utils.ticker_cache['Apple Inc.'] == 'AAPL'
            
            # Second request should use cache (Perplexity shouldn't be called again)
            # Reset the mock to ensure it's not called
            m.reset_mock()
            m.post(
                'https://watermelonindex.glide.page/api/container/playerFunctionCritical/getAppSnapshot',
                json={'dataSnapshot': 'http://test.com/snapshot'}
            )
            m.get('http://test.com/snapshot', text=encoded_data)
            
            response2 = client.get('/api')
            assert response2.status_code == 200
            
            # Verify Perplexity was not called the second time
            perplexity_calls = [call for call in m.request_history 
                              if 'perplexity.ai' in call.url]
            assert len(perplexity_calls) == 0

    @pytest.mark.integration
    def test_concurrent_requests_handling(self, client, sample_external_data):
        """Test that the API can handle multiple concurrent requests"""
        import threading
        import time
        
        encoded_data = base64.b64encode(json.dumps(sample_external_data).encode()).decode()
        results = []
        
        def make_request():
            with requests_mock.Mocker() as m:
                m.post(
                    'https://watermelonindex.glide.page/api/container/playerFunctionCritical/getAppSnapshot',
                    json={'dataSnapshot': 'http://test.com/snapshot'}
                )
                m.get('http://test.com/snapshot', text=encoded_data)
                m.post(
                    'https://api.perplexity.ai/chat/completions',
                    json={'choices': [{'message': {'content': 'AAPL'}}]}
                )
                
                response = client.get('/api')
                results.append(response.status_code)
        
        # Create multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All requests should succeed
        assert all(status == 200 for status in results)
        assert len(results) == 5
