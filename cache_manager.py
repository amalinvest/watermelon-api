import json
import os
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

CACHE_FILE = 'data_cache.json'
TICKER_CACHE_FILE = 'ticker_cache.json'

# Cache durations for different types
CACHE_DURATIONS = {
    'data': timedelta(days=1),
    'ticker': timedelta(days=365)  # 1 year for tickers
}

def load_cache(cache_type='data'):
    """Load data from cache if it exists and is not expired."""
    cache_file = TICKER_CACHE_FILE if cache_type == 'ticker' else CACHE_FILE
    cache_duration = CACHE_DURATIONS.get(cache_type, timedelta(days=1))  # default to 1 day if type not found
    
    if not os.path.exists(cache_file):
        return None
        
    try:
        with open(cache_file, 'r') as f:
            cache = json.load(f)
            
        # Check if cache is expired
        cached_time = datetime.fromisoformat(cache['timestamp'])
        if datetime.now() - cached_time > cache_duration:
            logger.info(f"{cache_type} cache has expired (duration: {cache_duration})")
            return None
            
        logger.info(f"Using cached {cache_type} data")
        return cache['data']
    except Exception as e:
        logger.error(f"Error loading {cache_type} cache: {str(e)}")
        return None

def save_cache(data, cache_type='data'):
    """Save data to cache with current timestamp."""
    try:
        cache_file = TICKER_CACHE_FILE if cache_type == 'ticker' else CACHE_FILE
        cache = {
            'timestamp': datetime.now().isoformat(),
            'data': data
        }
        with open(cache_file, 'w') as f:
            json.dump(cache, f)
        logger.info(f"{cache_type} data cached successfully")
    except Exception as e:
        logger.error(f"Error saving {cache_type} cache: {str(e)}")
