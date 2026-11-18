import logging

from flask import Flask, jsonify
from utils import fetch_and_decode_data

app = Flask(__name__)
logger = logging.getLogger(__name__)

@app.route('/api', methods=['GET'], strict_slashes=False)
def get_data():
    try:
        data = fetch_and_decode_data()
        return jsonify(data['processed_data'])
    except Exception:
        # Log the detail server-side; upstream error text can include URLs and
        # response bodies that shouldn't reach the public.
        logger.exception("Failed to fetch watermelon data")
        return jsonify({'error': 'Failed to fetch data'}), 500

if __name__ == '__main__':
    app.run(port=5000, debug=False)
