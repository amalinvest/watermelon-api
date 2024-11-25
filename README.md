# Watermelon API

A Flask API that retrieves and decodes data from the Watermelon Index service.

## Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python app.py
```

## Usage

The API exposes a single endpoint:

- GET `/api/data`: Retrieves the decoded data from the Watermelon Index service

Example request:
```bash
curl http://localhost:5000/api/data
```

The response will be the decoded JSON data from the service.
