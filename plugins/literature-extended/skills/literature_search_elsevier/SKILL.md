---
name: literature-search-elsevier
description: >-
  Search Elsevier's Scopus and ScienceDirect APIs and retrieve article abstracts,
  metadata, entitlements, and full text (for open-access or entitled content).
  Use when searching Scopus citation/bibliographic records, querying
  ScienceDirect journals, or retrieving Elsevier article metadata/full text by
  DOI, PII, EID, or Scopus ID.
---

# Elsevier (Scopus & ScienceDirect) Literature Search

CLI wrapper for the [Elsevier Developer APIs](https://dev.elsevier.com/)
(`https://api.elsevier.com/content/`), covering Scopus Search, ScienceDirect
Search, Abstract Retrieval, Article Retrieval, and Entitlement Checks.

## Prerequisites

1.  **`uv`**: Read the `uv` skill and follow its Setup instructions to ensure
    `uv` is installed and on PATH.
2.  **User Notification**: If `.licenses/literature_search_elsevier_LICENSE.txt`
    does not already exist in the workspace root directory then (1) prominently
    notify the user to review the Elsevier API policy at
    https://dev.elsevier.com/policy.html and TDM rules, then (2) create the file
    recording the notification text and timestamp.
3.  **`.env` file**: Ensure `~/.env` exists.
4.  **`ELSEVIER_API_KEY`** *(Required)*: Register at https://dev.elsevier.com/.
    You **MUST** use the safe credentials protocol in the `credentials` skill to
    verify `ELSEVIER_API_KEY` in `~/.env` without printing its value.
5.  **`ELSEVIER_INSTTOKEN`** *(Optional)*: Only needed if running off-campus
    with an institutional token to unlock subscribed paywalled full text and
    `view=COMPLETE` Scopus fields. Without it, `STANDARD` Scopus views,
    `META_ABS` article metadata, and Elsevier Open Access full texts remain
    accessible.

## Core Rules

-   **Use the Wrapper**: Always run `uv run scripts/elsevier_cli.py ...` rather
    than raw `curl` or ad-hoc HTTP requests.
-   **Conserve Weekly Quotas**: Elsevier enforces rolling **7-day weekly
    quotas** per endpoint (~20,000/week for Scopus Search; ~5,000/week for
    Abstract/Article Retrieval). Prefer lighter views (`--view STANDARD` or
    `--view META_ABS`) unless full records are specifically needed.
-   **Check Quota Output**: The script logs `X-RateLimit-Remaining` and reset
    time to stderr after every call and stops immediately on `QUOTA_EXCEEDED`
    (HTTP 429) without wasting retries.
-   **File Output**: All subcommands require `--output <file>`.
-   **List Sources**: State that Elsevier (Scopus / ScienceDirect) was used and
    list the DOIs/URLs of all cited papers.

## Utility Scripts (`scripts/elsevier_cli.py`)

### 1. Scopus Search (`search-scopus`)

```bash
uv run scripts/elsevier_cli.py search-scopus \
  --query 'TITLE-ABS-KEY("CRISPR" AND "base editing") AND PUBYEAR > 2022' \
  --count 10 \
  --view STANDARD \
  --output scopus_results.json
```

### 2. ScienceDirect Search v2 (`search-sciencedirect`)

Uses ScienceDirect Search API v2 (`PUT /content/search/sciencedirect`) with a
structured JSON payload.

```bash
uv run scripts/elsevier_cli.py search-sciencedirect \
  --query "protein language model structure prediction" \
  --count 10 \
  --date "2023-2026" \
  --sort relevance \
  --open-access \
  --output sd_results.json
```

### 3. Abstract Retrieval (`get-abstract`)

Retrieve detailed Scopus metadata/abstract by `doi`, `eid`, `scopus_id`,
`pmid`, or `pii`.

```bash
uv run scripts/elsevier_cli.py get-abstract \
  --id-type doi \
  --id "10.1016/j.cell.2020.01.021" \
  --view META_ABS \
  --output abstract.json
```

### 4. ScienceDirect Article Retrieval (`get-article`)

Retrieve ScienceDirect article metadata or full text (works for Open Access
articles without an institutional token, and subscribed articles when on-campus
or with `ELSEVIER_INSTTOKEN`). Supports `--format json`, `xml`, or `text`
(clean XML-stripped plain text).

```bash
# Metadata + abstract (JSON):
uv run scripts/elsevier_cli.py get-article \
  --id-type doi \
  --id "10.1016/j.cell.2020.01.021" \
  --view META_ABS \
  --format json \
  --output article_meta.json

# Full text stripped to plain text (OA or entitled articles):
uv run scripts/elsevier_cli.py get-article \
  --id-type doi \
  --id "10.1016/j.cell.2020.01.021" \
  --view FULL \
  --format text \
  --output article_fulltext.txt
```

### 5. Entitlement Check (`check-entitlement`)

Verify whether your current IP/key has full-text access to a DOI before
requesting `--view FULL`.

```bash
uv run scripts/elsevier_cli.py check-entitlement \
  --doi "10.1016/j.cell.2020.01.021" \
  --output entitlement.json
```

## Reference

- [references/scopus_query_syntax.md](references/scopus_query_syntax.md) —
  Scopus search field codes, view tiers, and error troubleshooting.
