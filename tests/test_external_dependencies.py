import pytest
import os
import tempfile
import json
from unittest.mock import patch, Mock
import requests
import utils
import cache_manager


class TestExternalDependencies:
    """Test suite for external dependencies and environment handling"""

    def setup_method(self):
        """Setup for each test method"""
        # Clear ticker cache
        utils.ticker_cache = {}

    def test_environment_variable_loading(self):
        """Test that environment variables are loaded correctly"""
        with patch.dict(os.environ, {'PERPLEXITY_API_KEY': 'test-key-123'}):
            # Reload the module to pick up new env var
            import importlib
            importlib.reload(utils)
            
            # Test that the API key is used in requests
            with patch('requests.post') as mock_post:
                mock_response = Mock()
                mock_response.json.return_value = {'choices': [{'message': {'content': 'AAPL'}}]}
                mock_response.raise_for_status.return_value = None
                mock_post.return_value = mock_response
                
                utils.search_with_perplexity("test query")
                
                # Verify the API key was used in the request
                call_args = mock_post.call_args
                headers = call_args[1]['headers']
                assert headers['Authorization'] == 'Bearer test-key-123'

    def test_missing_perplexity_api_key(self):
        """Test behavior when Perplexity API key is missing"""
        with patch.dict(os.environ, {}, clear=True):
            # Remove the key if it exists
            if 'PERPLEXITY_API_KEY' in os.environ:
                del os.environ['PERPLEXITY_API_KEY']
            
            with patch('requests.post') as mock_post:
                mock_response = Mock()
                mock_response.json.return_value = {'choices': [{'message': {'content': 'AAPL'}}]}
                mock_response.raise_for_status.return_value = None
                mock_post.return_value = mock_response
                
                utils.search_with_perplexity("test query")
                
                # Verify the request was made with None API key
                call_args = mock_post.call_args
                headers = call_args[1]['headers']
                assert headers['Authorization'] == 'Bearer None'

    def test_cache_file_permissions(self):
        """Test cache behavior with file permission issues"""
        from datetime import datetime

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = os.path.join(temp_dir, 'test_cache.json')

            # Create a cache file with current timestamp and make it read-only
            test_data = {'test': 'data'}
            current_time = datetime.now().isoformat()
            with open(cache_file, 'w') as f:
                json.dump({'timestamp': current_time, 'data': test_data}, f)

            os.chmod(cache_file, 0o444)  # Read-only

            with patch('cache_manager.CACHE_FILE', cache_file):
                # Should be able to load
                result = cache_manager.load_cache()
                assert result == test_data

                # Should handle save error gracefully
                cache_manager.save_cache({'new': 'data'})  # Should not raise exception

    def test_network_timeout_handling(self):
        """Test handling of network timeouts"""
        with patch('requests.post') as mock_post:
            mock_post.side_effect = requests.exceptions.Timeout("Request timed out")
            
            result = utils.search_with_perplexity("test query")
            assert result is None

    def test_network_connection_error(self):
        """Test handling of network connection errors"""
        with patch('requests.post') as mock_post:
            mock_post.side_effect = requests.exceptions.ConnectionError("Connection failed")
            
            result = utils.search_with_perplexity("test query")
            assert result is None

    def test_http_error_responses(self):
        """Test handling of HTTP error responses"""
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("401 Unauthorized")
            mock_post.return_value = mock_response
            
            result = utils.search_with_perplexity("test query")
            assert result is None

    def test_malformed_json_response(self):
        """Test handling of malformed JSON responses"""
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response
            
            result = utils.search_with_perplexity("test query")
            assert result is None

    def test_cache_corruption_handling(self):
        """Test handling of corrupted cache files"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json content {")
            cache_file = f.name
        
        try:
            with patch('cache_manager.CACHE_FILE', cache_file):
                # Should handle corrupted cache gracefully
                result = cache_manager.load_cache()
                assert result is None
        finally:
            os.unlink(cache_file)

    def test_disk_space_handling(self):
        """Test handling when disk is full (simulated)"""
        with patch('builtins.open', side_effect=OSError("No space left on device")):
            # Should handle disk full error gracefully
            cache_manager.save_cache({'test': 'data'})  # Should not raise exception

    def test_concurrent_cache_access(self):
        """Test concurrent access to cache files"""
        import threading
        import time
        
        results = []
        errors = []
        
        def cache_operation(data):
            try:
                cache_manager.save_cache({'thread': data})
                result = cache_manager.load_cache()
                results.append(result)
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads accessing cache
        threads = []
        for i in range(5):
            thread = threading.Thread(target=cache_operation, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Should not have any errors
        assert len(errors) == 0
        assert len(results) == 5

    def test_external_api_rate_limiting(self):
        """Test handling of API rate limiting"""
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("429 Too Many Requests")
            mock_post.return_value = mock_response
            
            result = utils.search_with_perplexity("test query")
            assert result is None

    def test_watermelon_api_structure_changes(self):
        """Test handling of changes in external API structure"""
        with patch('requests.post') as mock_post_snapshot:
            with patch('requests.get') as mock_get_data:
                # Mock response with missing dataSnapshot field
                mock_post_response = Mock()
                mock_post_response.json.return_value = {'unexpectedField': 'value'}
                mock_post_response.raise_for_status.return_value = None
                mock_post_snapshot.return_value = mock_post_response
                
                with pytest.raises(ValueError, match="dataSnapshot URL not found"):
                    utils.fetch_raw_data()

    def test_base64_decoding_errors(self):
        """Test handling of base64 decoding errors"""
        with patch('requests.post') as mock_post:
            with patch('requests.get') as mock_get:
                # Mock successful initial request
                mock_post_response = Mock()
                mock_post_response.json.return_value = {'dataSnapshot': 'http://test.com/data'}
                mock_post_response.raise_for_status.return_value = None
                mock_post.return_value = mock_post_response
                
                # Mock response with invalid base64
                mock_get_response = Mock()
                mock_get_response.text = "invalid-base64-content!"
                mock_get_response.raise_for_status.return_value = None
                mock_get.return_value = mock_get_response
                
                with pytest.raises(Exception):  # Should raise base64 decode error
                    utils.fetch_raw_data()

    def test_json_parsing_errors_in_decoded_data(self):
        """Test handling of JSON parsing errors in decoded data"""
        import base64
        
        with patch('requests.post') as mock_post:
            with patch('requests.get') as mock_get:
                # Mock successful initial request
                mock_post_response = Mock()
                mock_post_response.json.return_value = {'dataSnapshot': 'http://test.com/data'}
                mock_post_response.raise_for_status.return_value = None
                mock_post.return_value = mock_post_response
                
                # Mock response with invalid JSON (but valid base64)
                invalid_json = "invalid json content"
                encoded_invalid = base64.b64encode(invalid_json.encode()).decode()
                mock_get_response = Mock()
                mock_get_response.text = encoded_invalid
                mock_get_response.raise_for_status.return_value = None
                mock_get.return_value = mock_get_response
                
                with pytest.raises(json.JSONDecodeError):
                    utils.fetch_raw_data()

    def test_cache_expiration_edge_cases(self):
        """Test cache expiration edge cases"""
        from datetime import datetime, timedelta
        
        # Test cache that expires exactly now
        now = datetime.now()
        expired_cache = {
            'timestamp': (now - timedelta(days=1)).isoformat(),
            'data': {'test': 'expired'}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(expired_cache, f)
            cache_file = f.name
        
        try:
            with patch('cache_manager.CACHE_FILE', cache_file):
                result = cache_manager.load_cache()
                assert result is None  # Should be expired
        finally:
            os.unlink(cache_file)
