from utils import fetch_and_decode_data
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    try:
        logger.info("Starting cache refresh...")
        fetch_and_decode_data()
        logger.info("Cache refresh completed successfully")
    except Exception as e:
        logger.error(f"Error refreshing cache: {str(e)}")
        raise

if __name__ == "__main__":
    main() 