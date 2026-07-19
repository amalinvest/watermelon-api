# Domain glossary

The vocabulary used across code, tests, and architecture discussions. Module
names and interfaces should use these terms.

- **Watermelon Index** — the upstream Glide app (`watermelonindex.glide.page`)
  tracking companies with documented complicity ties. Our only data source.

- **Snapshot** — the Index's full database export (a base64-encoded JSON blob
  fetched via the Glide `getAppSnapshot` protocol): a `Sheet1` table of company
  rows and a `Campaigns` table.

- **Company** — one entry in the `/api` response. Always carries identity
  (`companyName`, `companyId`), `sector`, `complicityDetails`,
  `recordLastUpdated`, `sources`, and a `stockTicker` (nullable). Conditionally
  carries complicity category flags and campaign fields (see below).

- **Complicity categories** — `Military`, `Settlement production`,
  `Population control`, `Economic exploitation`, `Cultural`. Present on a
  Company only when the Index records them, as lowercase underscore keys
  (e.g. `settlement_production`).

- **Campaign** — a boycott/divestment campaign from the Index. Merged onto
  every Company its `Companies` field names, as `campaign*` fields plus
  `targetAim`.

- **Flatten** — the pure transform from a Snapshot to Company entries
  (`companies.flatten_and_standardize`). No network, no caches.

- **Ticker resolution** — mapping a company name to a US-listed stock ticker
  (NYSE/NASDAQ/OTC/ADR), or `None` if the company isn't publicly traded.
  LLM-assisted (Perplexity search, then Gemini extraction), validated against
  ticker format patterns, cached indefinitely. Applied to Companies by the
  enrichment pass (`companies.enrich_with_tickers`), which takes the resolver
  as an argument.
