# Literature Extended Plugin

Personal Antigravity plugin expanding the built-in `scientific-literature` skills with five additional scholarly research sources, following the exact design conventions of `google-deepmind/science-skills` (`uv run` PEP 723 CLIs, `polite-http` cross-process rate limiting, and the `credentials` safe `~/.env` protocol).

## Included Components

### CLI Skills (`skills/`)
1. **`literature-search-s2`** — Semantic Scholar Academic Graph & Recommendations API (`S2_API_KEY` / `SEMANTIC_SCHOLAR_API_KEY`)
2. **`literature-search-elsevier`** — Elsevier Scopus Search, ScienceDirect v2 Search, Abstract Retrieval & Article Retrieval (`ELSEVIER_API_KEY`, optional `ELSEVIER_INSTTOKEN`)
3. **`literature-search-springer`** — Springer Nature Meta API v2 & Open Access API including JATS XML full text (`SPRINGER_META_API_KEY`, `SPRINGER_OA_API_KEY`)
4. **`literature-search-core`** — CORE API v3 open-access repository search, full text extraction, and PDF downloads (`CORE_API_KEY`)
5. **`uv`** & **`credentials`** — Bundled prerequisite helper skills (making the plugin self-contained even if official science plugins are disabled)

### MCP Server (`mcp_config.json`)
- **`asta`** (registered as `literature-extended_asta`) — Local `uv run` stdio proxy ([scripts/asta_mcp_proxy.py](scripts/asta_mcp_proxy.py)) bridging to Ai2 Asta Scientific Corpus (`https://asta-tools.allen.ai/mcp/v1`) for agentic `snippet_search`, paper lookup, citation traversal, and author discovery.

## Credentials

- All 4 CLI skills and the Asta MCP proxy automatically load keys from project `.env` or `~/.env` via `python-dotenv` (`ASTA_API_KEY`, `S2_API_KEY`, `ELSEVIER_API_KEY`, `SPRINGER_META_API_KEY`, `SPRINGER_OA_API_KEY`, `CORE_API_KEY`).
- Zero secrets are stored in `mcp_config.json`.
