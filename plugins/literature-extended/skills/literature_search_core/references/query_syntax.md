# CORE API v3 Query Syntax & Quota Reference

## Common Elasticsearch Query Fields (`search`)
- `title:"retrieval augmented generation"` — Exact phrase in title
- `abstract:CRISPR` — Abstract text match
- `fullText:"single-cell RNA"` — Full-text body match
- `authors:"Jumper"` — Author name
- `doi:"10.1038/s41586-021-03819-2"` — Exact DOI lookup
- `yearPublished>=2023` or `yearPublished:[2020 TO 2025]` — Publication year filter
- `language.code:en` — Language filter
- `documentType:research` — Document type (`research`, `thesis`, `slides`, etc.)
- `_exists_:fullText` — Restrict to works with indexed full text (or pass `--has-fulltext`)
- Boolean operators: `AND`, `OR`, `NOT`

## Pagination & Scroll Costs
- Standard paging (`--offset`, `--limit`) is cheapest in quota tokens.
- Deep paging (`--scroll` / `--scroll-id`) bypasses offset limits but consumes roughly **3–5 quota tokens** per request.

## Rate-Limit Headers
Every response returns:
- `X-RateLimit-Limit` — Quota allowance for the active window
- `X-RateLimit-Remaining` — Remaining tokens before HTTP `429`
- `X-RateLimit-Retry-After` — Seconds/timestamp to wait when exhausted
