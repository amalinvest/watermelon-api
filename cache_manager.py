import json
import os
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

CACHE_FILE = 'data_cache.json'
CACHE_DURATION = timedelta(days=1)

def load_cache():
    """Load data from cache if it exists and is not expired."""
    if not os.path.exists(CACHE_FILE):
        return None
        
    try:
        with open(CACHE_FILE, 'r') as f:
            cache = json.load(f)
            
        # Check if cache is expired
        cached_time = datetime.fromisoformat(cache['timestamp'])
        if datetime.now() - cached_time > CACHE_DURATION:
            logger.info("Cache has expired")
            return None
            
        logger.info("Using cached data")
        return cache['data']
    except Exception as e:
        logger.error(f"Error loading cache: {str(e)}")
        return None

def save_cache(data):
    """Save data to cache with current timestamp."""
    try:
        cache = {
            'timestamp': datetime.now().isoformat(),
            'data': data
        }
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache, f)
        logger.info("Data cached successfully")
    except Exception as e:
        logger.error(f"Error saving cache: {str(e)}")
