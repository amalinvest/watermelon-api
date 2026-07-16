# Watermelon API

A Flask API that retrieves and decodes data from the Watermelon Index service.

## Setup

Requires [uv](https://docs.astral.sh/uv/) (`brew install uv`).

1. Install dependencies (creates `.venv` automatically):
```bash
uv sync
```

2. Run the application:
```bash
uv run python app.py
```

3. Run the tests:
```bash
uv run pytest
```

`requirements.txt` is generated from the lockfile for the pip-based deploy — after
changing dependencies in `pyproject.toml`, regenerate it with:
```bash
uv export --no-dev --no-hashes -o requirements.txt
```

## Usage

The API exposes a single endpoint:

- GET `/api`: Retrieves the decoded data from the Watermelon Index service

Example request:
```bash
curl http://localhost:5000/api/
```

The response will be the decoded JSON data from the service.
