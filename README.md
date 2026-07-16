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

Deploys install straight from `uv.lock` via the Python buildpack (the buildpack
errors if more than one package manager file is present, so there is no
`requirements.txt`). After changing dependencies in `pyproject.toml`, run
`uv lock` and commit the updated lockfile.

## Usage

The API exposes a single endpoint:

- GET `/api`: Retrieves the decoded data from the Watermelon Index service

Example request:
```bash
curl http://localhost:5000/api/
```

The response will be the decoded JSON data from the service.
