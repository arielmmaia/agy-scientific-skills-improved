---
name: literature-search-s2
description: >-
  Search and traverse the Semantic Scholar Academic Graph and Recommendations
  APIs (S2). Supports relevance search, token-paginated bulk search, exact title
  matching, single and 500-paper batch metadata lookup (with TLDR summaries and
  open-access PDF links), citation/reference graphs with contexts, full-text
  snippet search, author publications, and seed-based paper recommendations.
  Use when querying Semantic Scholar directly, running bulk/batch literature
  exports to JSON files, fetching paper recommendations, or retrieving TLDRs.
  For quick interactive evidence lookup over the same corpus, the
  literature-extended_asta MCP server is also available.
---

# Semantic Scholar (S2) Literature Search & Recommendations

CLI wrapper for the [Semantic Scholar Academic Graph API](https://api.semanticscholar.org/api-docs/graph)
(`graph/v1`) and [Recommendations API](https://api.semanticscholar.org/api-docs/recommendations)
(`recommendations/v1`).

## Prerequisites

1.  **`uv`**: Read the `uv` skill and follow its Setup instructions to ensure
    `uv` is installed and on PATH.
2.  **User Notification**: If `.licenses/literature_search_s2_LICENSE.txt` does
    not already exist in the workspace root directory then (1) prominently notify
    the user to check the Semantic Scholar API terms at
    https://www.semanticscholar.org/product/api and the license of any retrieved
    papers, then (2) create the file recording the notification text and
    timestamp.
3.  **`.env` file**: Ensure `~/.env` exists.
4.  **`S2_API_KEY`** *(or `SEMANTIC_SCHOLAR_API_KEY`)*: Strongly recommended
    (required for reliable execution — unauthenticated requests share a heavily
    throttled public pool). Register at
    https://www.semanticscholar.org/product/api#api-key-form. You **MUST** use
    the safe credentials protocol in the `credentials` skill to check for
    `S2_API_KEY` (or `SEMANTIC_SCHOLAR_API_KEY`) without printing its value.

## Core Rules

-   **Use the Wrapper**: Always run `uv run scripts/s2_cli.py ...` rather than
    raw `curl` or ad-hoc `python3` scripts. The wrapper enforces cross-process
    rate limiting (`0.95 req/s`, safely under S2's 1 RPS personal-key cap) and
    exponential backoff on HTTP 429/5xx.
-   **Keep Payloads Lean**: Always request only the `--fields` you need (the
    defaults are already compact). See
    [references/fields_and_filters.md](references/fields_and_filters.md).
-   **File Output**: All subcommands require `--output <file>` to prevent
    context overflow. Inspect JSON outputs with `jq` or targeted Python reads.
-   **List Sources**: Whenever this skill is used, state that Semantic Scholar
    (S2) was used and list the URLs or DOIs of all papers cited in your answer.

## Utility Scripts (`scripts/s2_cli.py`)

### 1. Relevance Paper Search (`search`)

Keyword search sorted by relevance (max 100/page; offset capped around 1,000).

```bash
uv run scripts/s2_cli.py search "CRISPR base editing" \
  --limit 10 \
  --year "2022-" \
  --open-access-pdf \
  --output s2_search.json
```

### 2. Bulk Filtered Search (`bulk-search`)

Large-scale Boolean search using cursor `token` pagination (up to 1,000 papers
per page; no offset cap).

```bash
uv run scripts/s2_cli.py bulk-search '("protein folding" | "AlphaFold") +diffusion' \
  --year "2023-2026" \
  --sort "citationCount:desc" \
  --output s2_bulk_p1.json

# Next page using returned .token:
uv run scripts/s2_cli.py bulk-search '("protein folding" | "AlphaFold") +diffusion' \
  --year "2023-2026" \
  --sort "citationCount:desc" \
  --token "<NEXT_TOKEN>" \
  --output s2_bulk_p2.json
```

### 3. Exact Title Match (`match`)

Resolve a paper title string to its closest Semantic Scholar record + `matchScore`.

```bash
uv run scripts/s2_cli.py match "Highly accurate protein structure prediction with AlphaFold" \
  --output s2_match.json
```

### 4. Single Paper Details (`get`)

Supports S2 ID, `DOI:...`, `ARXIV:...`, `PMID:...`, `PMCID:...`, `CorpusId:...`,
`MAG:...`, `ACL:...`, or `URL:...`.

```bash
uv run scripts/s2_cli.py get "DOI:10.1038/s41586-021-03819-2" \
  --fields "paperId,title,year,venue,citationCount,tldr,openAccessPdf,abstract,externalIds" \
  --output alphafold.json
```

### 5. Batch Paper Lookup (`batch`)

Fetch up to 500 papers per POST request (automatically chunked if more IDs are
supplied).

```bash
uv run scripts/s2_cli.py batch \
  --ids "DOI:10.1038/s41586-021-03819-2,ARXIV:1706.03762" \
  --output batch_papers.json
```

### 6. Citations & References (`citations`, `references`)

```bash
uv run scripts/s2_cli.py citations "DOI:10.1038/s41586-021-03819-2" \
  --limit 25 --output citations.json

uv run scripts/s2_cli.py references "DOI:10.1038/s41586-021-03819-2" \
  --limit 50 --output references.json
```

### 7. Full-Text Snippet Search (`snippets`)

Retrieve ~500-word full-text passages matching a query across indexed papers.

```bash
uv run scripts/s2_cli.py snippets "prime editing pegRNA efficiency in primary T cells" \
  --limit 10 --year "2022-" --output snippets.json
```

### 8. Paper Recommendations (`recommend`)

Find related papers from one or more positive seed paper IDs (and optional
negative seed IDs to steer away from irrelevant subfields).

```bash
# Single seed paper:
uv run scripts/s2_cli.py recommend \
  --positive "DOI:10.1038/s41586-021-03819-2" \
  --limit 20 --output recs.json

# Multi-seed positive + negative steering:
uv run scripts/s2_cli.py recommend \
  --positive "DOI:10.1038/s41586-021-03819-2" "ARXIV:2107.02179" \
  --negative "ARXIV:1706.03762" \
  --limit 20 --output recs_steered.json
```

### 9. Author Search & Publications (`author-search`, `author-papers`)

```bash
uv run scripts/s2_cli.py author-search "John Jumper" --limit 5 --output authors.json
uv run scripts/s2_cli.py author-papers "<AUTHOR_ID>" --limit 25 --output author_papers.json
```

## Rate Limiting

- Standard personal API keys allow **1 request/second** across all S2 endpoints.
- `scripts/s2_cli.py` uses `polite-http` with cross-process file locking at
  `qps=0.95` and automatic exponential backoff on HTTP 429/5xx.

## Reference

- [references/fields_and_filters.md](references/fields_and_filters.md) — full
  list of paper/author/citation fields, ID prefixes, and bulk query operators.

## Companion Asta MCP Tool Schema Note

When calling the companion Ai2 Asta MCP server (`literature-extended_asta`),
four upstream tools currently return `"parameters": null` in their JSON schema.
Pass these exact parameter names from their docstrings:

- **`search_papers_by_relevance`**: `keyword` (required), `fields`, `limit`, `publication_date_range`, `venues`
- **`search_paper_by_title`**: `title` (required), `fields`, `publication_date_range`, `venues`
- **`search_authors_by_name`**: `name` (required), `fields`, `limit`
- **`get_author_papers`**: `author_id` (required), `paper_fields`, `limit`, `publication_date_range`
