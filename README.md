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

### Response shape

The response is a JSON array of Company objects:

```json
{
  "companyName": "Aalberts Industries UK",
  "companyId": "Co1",
  "sector": "Manufacturing",
  "complicityDetails": "…",
  "recordLastUpdated": "1/2/2024",
  "sources": ["https://…", "https://…"],
  "stockTicker": "AALB",

  "military": "Yes",

  "campaignName": "…",
  "campaignId": "…",
  "campaignDescription": "…",
  "campaignLocation": "…",
  "campaignOutcomes": "…",
  "campaignAimsAchieved": "…",
  "campaignGroups": "…",
  "campaignMethods": "…",
  "campaignLinks": ["https://…"],
  "targetAim": "…"
}
```

Field notes:

- **Always present**: `companyName`, `companyId`, `sector`, `complicityDetails`,
  `recordLastUpdated`, `sources` (array, may be empty), `stockTicker`.
- **`stockTicker` is nullable** — `null` means the company isn't publicly
  traded in the US (or the ticker couldn't be resolved).
- **Complicity category keys are conditional**: `military`,
  `settlement_production`, `population_control`, `economic_exploitation`,
  `cultural` appear only when the Watermelon Index records that category
  for the company.
- **Campaign fields are conditional**: the `campaign*` keys and `targetAim`
  appear only when a campaign references the company.

See `CONTEXT.md` for the domain vocabulary behind these fields.
