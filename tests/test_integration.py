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

    @pytest.fixture(autouse=True)
    def clear_ticker_cache(self):
        """Clear ticker cache before each test"""
        utils.ticker_cache = {}

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
    @patch('utils.save_cache')
    @patch('utils.load_cache')
    def test_full_api_flow_with_mocked_externals(self, mock_load_cache, mock_save_cache, client, sample_external_data):
        """Test complete API flow with mocked external services"""
        mock_load_cache.return_value = None

        encoded_data = base64.b64encode(json.dumps(sample_external_data).encode()).decode()

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
            m.post(
                'https://openrouter.ai/api/v1/chat/completions',
                json={'choices': [{'message': {'content': 'AAPL'}}]}
            )

            response = client.get('/api')

            assert response.status_code == 200
            data = json.loads(response.data)

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

            assert len(data) == 1
            assert data[0]['companyName'] == 'Cached Company'
            assert data[0]['stockTicker'] == 'CACHE'

    @pytest.mark.integration
    @patch('utils.save_cache')
    @patch('utils.load_cache', return_value=None)
    def test_external_api_failure_handling(self, mock_load_cache, mock_save_cache, client):
        """Test handling of external API failures"""
        with requests_mock.Mocker() as m:
            m.post(
                'https://watermelonindex.glide.page/api/container/playerFunctionCritical/getAppSnapshot',
                status_code=500
            )

            response = client.get('/api')

            assert response.status_code == 500
            data = json.loads(response.data)
            assert 'error' in data

    @pytest.mark.integration
    @patch('utils.save_cache')
    @patch('utils.load_cache', return_value=None)
    def test_perplexity_api_failure_graceful_handling(self, mock_load_cache, mock_save_cache, client, sample_external_data):
        """Test that Perplexity API failures don't break the main flow"""
        encoded_data = base64.b64encode(json.dumps(sample_external_data).encode()).decode()

        with requests_mock.Mocker() as m:
            m.post(
                'https://watermelonindex.glide.page/api/container/playerFunctionCritical/getAppSnapshot',
                json={'dataSnapshot': 'http://test.com/snapshot'}
            )
            m.get('http://test.com/snapshot', text=encoded_data)
            m.post(
                'https://api.perplexity.ai/chat/completions',
                status_code=500
            )

            response = client.get('/api')

            assert response.status_code == 200
            data = json.loads(response.data)

            assert len(data) == 1
            company = data[0]
            assert company['companyName'] == 'Apple Inc.'
            assert company['stockTicker'] is None

    @pytest.mark.integration
    @patch('utils.save_cache')
    @patch('utils.load_cache', return_value=None)
    def test_malformed_external_data_handling(self, mock_load_cache, mock_save_cache, client):
        """Test handling of malformed data from external API"""
        with requests_mock.Mocker() as m:
            m.post(
                'https://watermelonindex.glide.page/api/container/playerFunctionCritical/getAppSnapshot',
                json={'dataSnapshot': 'http://test.com/snapshot'}
            )
            m.get('http://test.com/snapshot', text='invalid-base64-data')

            response = client.get('/api')

            assert response.status_code == 500
            data = json.loads(response.data)
            assert 'error' in data

    @pytest.mark.integration
    @patch('utils.save_cache')
    @patch('utils.load_cache', return_value=None)
    def test_missing_datasnapshot_url(self, mock_load_cache, mock_save_cache, client):
        """Test handling when dataSnapshot URL is missing"""
        with requests_mock.Mocker() as m:
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
    @patch('utils.save_cache')
    @patch('utils.load_cache', return_value=None)
    def test_ticker_caching_behavior(self, mock_load_cache, mock_save_cache, client, sample_external_data):
        """Test that ticker results are properly cached"""
        encoded_data = base64.b64encode(json.dumps(sample_external_data).encode()).decode()

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
            m.post(
                'https://openrouter.ai/api/v1/chat/completions',
                json={'choices': [{'message': {'content': 'AAPL'}}]}
            )

            # First request should call Perplexity + OpenRouter
            response1 = client.get('/api')
            assert response1.status_code == 200

            # Verify ticker was cached in memory
            assert 'Apple Inc.' in utils.ticker_cache
            assert utils.ticker_cache['Apple Inc.'] == 'AAPL'

            # Second request - ticker should come from memory cache
            # Count Perplexity calls so far
            perplexity_calls_before = len([h for h in m.request_history if 'perplexity.ai' in h.url])

            response2 = client.get('/api')
            assert response2.status_code == 200

            # No new Perplexity calls should have been made
            perplexity_calls_after = len([h for h in m.request_history if 'perplexity.ai' in h.url])
            assert perplexity_calls_after == perplexity_calls_before

    @pytest.mark.integration
    @patch('utils.save_cache')
    @patch('utils.load_cache', return_value=None)
    def test_concurrent_requests_handling(self, mock_load_cache, mock_save_cache, client, sample_external_data):
        """Test that the API can handle multiple sequential requests"""
        encoded_data = base64.b64encode(json.dumps(sample_external_data).encode()).decode()

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
            m.post(
                'https://openrouter.ai/api/v1/chat/completions',
                json={'choices': [{'message': {'content': 'AAPL'}}]}
            )

            results = []
            for _ in range(5):
                response = client.get('/api')
                results.append(response.status_code)

            assert all(status == 200 for status in results)
            assert len(results) == 5
