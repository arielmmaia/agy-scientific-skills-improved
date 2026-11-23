---
name: literature-search-core
description: >-
  Search CORE API v3's global open-access repository aggregator, retrieve
  article metadata by CORE ID or DOI, extract parsed full text (fullText),
  download open-access PDFs, and query repository data providers. Use when
  looking for open-access institutional repository copies, full-text plaintext,
  or OA PDFs that are unavailable in Europe PMC or OpenAlex.
---

# CORE API v3 Open-Access Literature Search & Full Text

CLI wrapper for the [CORE API v3](https://api.core.ac.uk/docs/v3)
(`https://api.core.ac.uk/v3`), aggregating hundreds of millions of open-access
scholarly records and full texts from global institutional repositories and
journals.

## Prerequisites

1.  **`uv`**: Read the `uv` skill and follow its Setup instructions to ensure
    `uv` is installed and on PATH.
2.  **User Notification**: If `.licenses/literature_search_core_LICENSE.txt`
    does not already exist in the workspace root directory then (1) prominently
    notify the user to check CORE's terms at https://core.ac.uk/terms and the
    license of retrieved papers, then (2) create the file recording the
    notification text and timestamp.
3.  **`.env` file**: Ensure `~/.env` exists.
4.  **`CORE_API_KEY`** *(Required)*: Register for a free academic key at
    https://core.ac.uk/services/api. Sent via `Authorization: Bearer <KEY>`
    (required for CORE v3 and `fullText` access). You **MUST** use the safe
    credentials protocol in the `credentials` skill to verify `CORE_API_KEY`
    in `~/.env` without printing its value.

## Core Rules

-   **Use the Wrapper**: Always run `uv run scripts/core_cli.py ...` rather than
    raw `curl`. The script enforces conservative cross-process pacing
    (`0.5 req/s`, safely within CORE free-tier limits) and logs live
    `X-RateLimit-Remaining` headers to stderr.
-   **Keep Search Outputs Compact**: By default, `search`, `get`, and `batch`
    strip the large `fullText` field (replacing it with `hasFullText: true/false`
    and `fullTextLength`) so JSON outputs never blow up context. Use
    `get-fulltext` to save full text cleanly to a `.txt` file.
-   **Avoid Unnecessary Scrolling**: `--scroll` consumes 3–5x more rate-limit
    tokens per request than standard `--offset` pagination; use it only for deep
    harvesting beyond standard offset limits.
-   **Validate PDFs**: `download-pdf` checks that downloaded files are non-empty
    and start with `%PDF-`.
-   **File Output**: All subcommands require `--output <file>`.
-   **List Sources**: State that CORE (core.ac.uk) was used and list the URLs or
    DOIs of all cited papers.

## Utility Scripts (`scripts/core_cli.py`)

### 1. Search Works (`search`)

Supports Elasticsearch query syntax (see
[references/query_syntax.md](references/query_syntax.md)). Add `--has-fulltext`
to restrict results to works with indexed full text.

```bash
uv run scripts/core_cli.py search 'title:"protein folding" AND yearPublished>=2023' \
  --limit 10 \
  --has-fulltext \
  --output core_search.json
```

### 2. Get Work Metadata by CORE ID or DOI (`get`)

```bash
uv run scripts/core_cli.py get --doi "10.1038/s41586-021-03819-2" --output core_work.json
uv run scripts/core_cli.py get --id 12345678 --output core_work.json
```

### 3. Batch Retrieve by CORE IDs (`batch`)

```bash
uv run scripts/core_cli.py batch --ids "12345678,23456789" --output core_batch.json
```

### 4. Extract Parsed Full Text (`get-fulltext`)

Writes the indexed plain-text `fullText` of a CORE work directly to a `.txt`
file.

```bash
uv run scripts/core_cli.py get-fulltext --doi "10.1038/s41586-021-03819-2" \
  --output paper_fulltext.txt
```

### 5. Download Open-Access PDF (`download-pdf`)

Resolves `downloadUrl` / `sourceFulltextUrls` (with fallback to CORE's direct
`/v3/works/{id}/download` endpoint), downloads the PDF, and verifies `%PDF-`.

```bash
uv run scripts/core_cli.py download-pdf --id 12345678 --output paper.pdf
```

### 6. Search Data Providers (`providers`)

```bash
uv run scripts/core_cli.py providers "MIT" --limit 10 --output providers.json
```

## Reference

- [references/query_syntax.md](references/query_syntax.md) — CORE v3 search
  fields, scroll pagination, and rate-limit headers.
