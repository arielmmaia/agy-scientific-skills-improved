# Springer Nature Query Constraints & Rate Limits Reference

## Common `q=` Field Constraints
- `doi:10.1038/s41586-021-03819-2` — Exact DOI lookup
- `title:"AlphaFold"` — Title match
- `keyword:"CRISPR"` — Author keyword
- `subject:"Bioinformatics"` — Subject discipline
- `name:"Jumper"` — Author name
- `journal:"Nature"` or `issn:1476-4687` — Journal name or ISSN
- `datefrom:2023-01-01` and `dateto:2025-12-31` — Publication date bounds
- `openaccess:true` — Open-access articles only (useful on Meta API v2)
- `type:Journal` or `type:Book` — Publication type
- `sort:date` — Sort by publication date (newest first)
- Boolean operators: `AND`, `OR`, `NOT` (combine constraints, e.g. `keyword:"CRISPR" AND openaccess:true AND datefrom:2024-01-01`)

## Pagination Rules
- `s=` (`--start`) is **1-indexed** (first page: `--start 1 --limit 25`; second page: `--start 26 --limit 25`).
- `p=` (`--limit`) is up to **100** on metadata JSON endpoints (`/meta/v2/json`, `/openaccess/json`), and lower (typically **20**) on full-text JATS XML (`/openaccess/jats`).
- Inspect `result[0].total`, `result[0].start`, and `result[0].pageLength` in the JSON output.

## Rate Limits & Quotas
- **Basic plan:** 100 req/min and **500 req/day** per API (Meta v2 and Open Access each have separate quotas).
- **Premium plan:** 200–300 req/min and **10,000 req/day**.
- Exceeding limits returns HTTP `429 Too Many Requests`.
