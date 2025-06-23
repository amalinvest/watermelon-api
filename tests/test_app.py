import pytest
import json
from unittest.mock import patch, Mock
from app import app


class TestFlaskApp:
    """Test suite for Flask application"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client

    @pytest.fixture
    def sample_processed_data(self):
        """Sample processed data for testing"""
        return [
            {
                'companyName': 'Test Company 1',
                'companyId': 'test-company-1',
                'sector': 'Technology',
                'stockTicker': 'TEST1'
            },
            {
                'companyName': 'Test Company 2',
                'companyId': 'test-company-2',
                'sector': 'Finance',
                'stockTicker': 'TEST2'
            }
        ]

    @patch('app.fetch_and_decode_data')
    def test_get_data_success(self, mock_fetch, client, sample_processed_data):
        """Test successful API call to /api endpoint"""
        # Mock successful data fetch
        mock_fetch.return_value = {
            'data': {'raw': 'data'},
            'processed_data': sample_processed_data
        }
        
        response = client.get('/api')
        
        assert response.status_code == 200
        assert response.content_type == 'application/json'
        
        data = json.loads(response.data)
        assert len(data) == 2
        assert data[0]['companyName'] == 'Test Company 1'
        assert data[1]['companyName'] == 'Test Company 2'

    @patch('app.fetch_and_decode_data')
    def test_get_data_with_trailing_slash(self, mock_fetch, client, sample_processed_data):
        """Test API call to /api/ endpoint (with trailing slash)"""
        mock_fetch.return_value = {
            'data': {'raw': 'data'},
            'processed_data': sample_processed_data
        }

        response = client.get('/api/')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data) == 2

    @patch('app.fetch_and_decode_data')
    def test_get_data_error_handling(self, mock_fetch, client):
        """Test error handling in API endpoint"""
        # Mock exception in data fetch
        mock_fetch.side_effect = Exception("External API error")

        response = client.get('/api')

        assert response.status_code == 500
        assert response.content_type == 'application/json'

        data = json.loads(response.data)
        assert 'error' in data
        assert data['error'] == 'External API error'

    @patch('app.fetch_and_decode_data')
    def test_get_data_request_exception(self, mock_fetch, client):
        """Test handling of requests.RequestException"""
        import requests
        mock_fetch.side_effect = requests.exceptions.RequestException("Network error")

        response = client.get('/api')

        assert response.status_code == 500
        data = json.loads(response.data)
        assert 'error' in data
        assert 'Network error' in data['error']

    @patch('app.fetch_and_decode_data')
    def test_get_data_value_error(self, mock_fetch, client):
        """Test handling of ValueError"""
        mock_fetch.side_effect = ValueError("Invalid data format")

        response = client.get('/api')

        assert response.status_code == 500
        data = json.loads(response.data)
        assert 'error' in data
        assert 'Invalid data format' in data['error']

    def test_invalid_endpoint(self, client):
        """Test request to non-existent endpoint"""
        response = client.get('/nonexistent')
        assert response.status_code == 404

    def test_invalid_method(self, client):
        """Test invalid HTTP method on /api endpoint"""
        response = client.post('/api')
        assert response.status_code == 405  # Method Not Allowed

        response = client.put('/api')
        assert response.status_code == 405

        response = client.delete('/api')
        assert response.status_code == 405

    @patch('app.fetch_and_decode_data')
    def test_empty_processed_data(self, mock_fetch, client):
        """Test API response with empty processed data"""
        mock_fetch.return_value = {
            'data': {'raw': 'data'},
            'processed_data': []
        }

        response = client.get('/api')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data == []

    @patch('app.fetch_and_decode_data')
    def test_malformed_response_data(self, mock_fetch, client):
        """Test handling of malformed response data"""
        # Mock response missing 'processed_data' key
        mock_fetch.return_value = {
            'data': {'raw': 'data'}
            # Missing 'processed_data' key
        }

        response = client.get('/api')

        assert response.status_code == 500
        data = json.loads(response.data)
        assert 'error' in data

    def test_app_configuration(self):
        """Test Flask app configuration"""
        assert app.name == 'app'
        
        # Test that debug is False in production
        with app.app_context():
            assert not app.debug

    @patch('app.fetch_and_decode_data')
    def test_response_headers(self, mock_fetch, client, sample_processed_data):
        """Test response headers"""
        mock_fetch.return_value = {
            'data': {'raw': 'data'},
            'processed_data': sample_processed_data
        }

        response = client.get('/api')

        assert response.status_code == 200
        assert 'application/json' in response.content_type

        # Check that response is properly formatted JSON
        data = json.loads(response.data)
        assert isinstance(data, list)

    @patch('app.fetch_and_decode_data')
    def test_large_dataset_response(self, mock_fetch, client):
        """Test API response with large dataset"""
        # Create a large dataset
        large_dataset = []
        for i in range(1000):
            large_dataset.append({
                'companyName': f'Company {i}',
                'companyId': f'company-{i}',
                'sector': 'Technology',
                'stockTicker': f'TEST{i}'
            })

        mock_fetch.return_value = {
            'data': {'raw': 'data'},
            'processed_data': large_dataset
        }

        response = client.get('/api')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data) == 1000
        assert data[0]['companyName'] == 'Company 0'
        assert data[999]['companyName'] == 'Company 999'
