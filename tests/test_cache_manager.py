import pytest
import json
import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import patch, mock_open
import cache_manager


class TestCacheManager:
    """Test suite for cache_manager module"""

    def setup_method(self):
        """Setup for each test method"""
        self.test_data = {"test": "data", "number": 123}
        self.test_cache = {
            "timestamp": datetime.now().isoformat(),
            "data": self.test_data
        }

    @patch('cache_manager.os.path.exists')
    def test_load_cache_file_not_exists(self, mock_exists):
        """Test load_cache when cache file doesn't exist"""
        mock_exists.return_value = False
        result = cache_manager.load_cache()
        assert result is None

    @patch('cache_manager.os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_load_cache_expired(self, mock_file, mock_exists):
        """Test load_cache when cache is expired"""
        mock_exists.return_value = True
        
        # Create expired cache (2 days old)
        expired_time = datetime.now() - timedelta(days=2)
        expired_cache = {
            "timestamp": expired_time.isoformat(),
            "data": self.test_data
        }
        mock_file.return_value.read.return_value = json.dumps(expired_cache)
        
        result = cache_manager.load_cache()
        assert result is None

    @patch('cache_manager.os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_load_cache_valid(self, mock_file, mock_exists):
        """Test load_cache with valid, non-expired cache"""
        mock_exists.return_value = True
        mock_file.return_value.read.return_value = json.dumps(self.test_cache)
        
        result = cache_manager.load_cache()
        assert result == self.test_data

    @patch('cache_manager.os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_load_cache_ticker_type(self, mock_file, mock_exists):
        """Test load_cache with ticker cache type"""
        mock_exists.return_value = True
        mock_file.return_value.read.return_value = json.dumps(self.test_cache)
        
        result = cache_manager.load_cache('ticker')
        assert result == self.test_data

    @patch('cache_manager.os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_load_cache_invalid_json(self, mock_file, mock_exists):
        """Test load_cache with invalid JSON"""
        mock_exists.return_value = True
        mock_file.return_value.read.return_value = "invalid json"
        
        result = cache_manager.load_cache()
        assert result is None

    @patch('builtins.open', new_callable=mock_open)
    def test_save_cache_success(self, mock_file):
        """Test successful cache save"""
        cache_manager.save_cache(self.test_data)
        
        # Verify file was opened for writing
        mock_file.assert_called_once_with('data_cache.json', 'w')
        
        # Verify json.dump was called with correct structure
        written_data = mock_file.return_value.__enter__.return_value.write.call_args_list
        assert len(written_data) > 0

    @patch('builtins.open', new_callable=mock_open)
    def test_save_cache_ticker_type(self, mock_file):
        """Test cache save with ticker type"""
        cache_manager.save_cache(self.test_data, 'ticker')
        
        # Verify correct file was used
        mock_file.assert_called_once_with('ticker_cache.json', 'w')

    @patch('builtins.open', side_effect=IOError("Permission denied"))
    def test_save_cache_error(self, mock_file):
        """Test cache save with file error"""
        # Should not raise exception, just log error
        cache_manager.save_cache(self.test_data)

    def test_cache_durations(self):
        """Test that cache durations are properly configured"""
        assert cache_manager.CACHE_DURATIONS['data'] == timedelta(days=1)
        assert cache_manager.CACHE_DURATIONS['ticker'] == timedelta(days=365)

    def test_cache_file_constants(self):
        """Test cache file constants"""
        assert cache_manager.CACHE_FILE == 'data_cache.json'
        assert cache_manager.TICKER_CACHE_FILE == 'ticker_cache.json'
