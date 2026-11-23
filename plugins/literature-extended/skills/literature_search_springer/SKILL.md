---
name: literature-search-springer
description: >-
  Search Springer Nature's Meta API v2 and Open Access API for Nature, Springer,
  BMC, and Palgrave scholarly articles, chapters, metadata, abstracts, and
  full-text JATS XML. Use when querying Springer Nature publications, looking up
  Nature/Springer DOIs, or extracting full text of Springer Nature Open Access
  articles.
---

# Springer Nature Literature Search (Meta v2 & Open Access API)

CLI wrapper for the [Springer Nature Developer APIs](https://dev.springernature.com/)
(`https://api.springernature.com`), covering both the **Meta API v2**
(`/meta/v2/json`) and the **Open Access API** (`/openaccess/json` and
`/openaccess/jats`).

## Prerequisites

1.  **`uv`**: Read the `uv` skill and follow its Setup instructions to ensure
    `uv` is installed and on PATH.
2.  **User Notification**: If `.licenses/literature_search_springer_LICENSE.txt`
    does not already exist in the workspace root directory then (1) prominently
    notify the user to check the Springer Nature API terms at
    https://dev.springernature.com/terms-and-conditions/ and individual article
    licenses, then (2) create the file recording the notification text and
    timestamp.
3.  **`.env` file**: Ensure `~/.env` exists.
4.  **API Keys** *(Required)*:
    - **`SPRINGER_META_API_KEY`** — used by `meta-search` and `meta-doi`
      (falls back to `SPRINGER_API_KEY` if unset).
    - **`SPRINGER_OA_API_KEY`** — used by `oa-search` and `oa-fulltext`
      (falls back to `SPRINGER_API_KEY` if unset).
    Register keys at https://dev.springernature.com/. You **MUST** use the safe
    credentials protocol in the `credentials` skill to check `~/.env` without
    printing key values.

## Core Rules

-   **Use the Wrapper**: Always run `uv run scripts/springer_cli.py ...` rather
    than raw `curl`. The script appends `api_key` safely without logging it and
    enforces cross-process rate limiting (`1.5 req/s`, under Basic tier's
    100 req/min limit).
-   **Respect Daily Caps**: Springer Nature Basic keys are capped at **500
    requests/day per API** (Premium: 10,000/day). Avoid unnecessary pagination
    loops and use specific field constraints (`doi:`, `journal:`, `datefrom:`).
-   **1-Indexed Pagination**: `--start` (`s=`) starts at **1** (not 0).
-   **File Output**: All subcommands require `--output <file>`.
-   **List Sources**: State that Springer Nature API was used and list the URLs
    or DOIs of all cited papers.

## Utility Scripts (`scripts/springer_cli.py`)

### 1. Meta API v2 Search (`meta-search`)

Search bibliographic metadata and abstracts across all Springer Nature content
(Nature, Springer, BMC, etc.).

```bash
uv run scripts/springer_cli.py meta-search \
  --query 'keyword:"protein folding" AND journal:"Nature" AND datefrom:2023-01-01' \
  --limit 10 \
  --output springer_meta.json
```

### 2. Meta API v2 DOI Lookup (`meta-doi`)

```bash
uv run scripts/springer_cli.py meta-doi \
  --doi "10.1038/s41586-021-03819-2" \
  --output alphafold_nature.json
```

### 3. Open Access Metadata Search (`oa-search`)

Search metadata specifically across Springer Nature Open Access content.

```bash
uv run scripts/springer_cli.py oa-search \
  --query 'subject:"Bioinformatics" AND keyword:"single-cell" AND datefrom:2024-01-01' \
  --limit 15 \
  --output springer_oa.json
```

### 4. Open Access Full Text via JATS XML (`oa-fulltext`)

Fetch full-text content from `/openaccess/jats` by `--doi` or `--query`.
Outputs clean plain text (`--format text`, default) or raw JATS XML
(`--format xml`).

```bash
# Clean plain text for a single OA DOI:
uv run scripts/springer_cli.py oa-fulltext \
  --doi "10.1038/s41586-021-03819-2" \
  --format text \
  --output alphafold_fulltext.txt

# Raw JATS XML:
uv run scripts/springer_cli.py oa-fulltext \
  --doi "10.1038/s41586-021-03819-2" \
  --format xml \
  --output alphafold_fulltext.xml
```

## Reference

- [references/query_constraints.md](references/query_constraints.md) — Springer
  Nature query constraints, pagination rules, and tier rate limits.
