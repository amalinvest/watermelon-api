from flask import Flask, jsonify
from utils import fetch_and_decode_data
import json

app = Flask(__name__)

@app.route('/api/data', methods=['GET'])
def get_data():
    try:
        data = fetch_and_decode_data()
        return jsonify(data['processed_data'])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)
