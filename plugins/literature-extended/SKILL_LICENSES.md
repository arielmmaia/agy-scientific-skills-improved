# Literature Extended — Licenses & Third-Party API Terms

The software in `plugins/literature-extended/` is licensed under the Apache
License, Version 2.0 (see the repository root [LICENSE](../../LICENSE)).

## Bundled Upstream Helper Skills

- `skills/uv/SKILL.md` and `skills/credentials/SKILL.md` are bundled from
  [google-deepmind/science-skills](https://github.com/google-deepmind/science-skills)
  (Copyright 2026 Google LLC, licensed under Apache 2.0 / CC-BY 4.0) so that
  `literature-extended` remains self-contained even if official science plugins
  are disabled.

## Third-Party Data Sources & API Terms of Use

You are responsible for ensuring your use of each skill complies with the
provider's Terms of Use and the individual licenses of any retrieved papers:

- **Semantic Scholar (S2) Academic Graph & Recommendations API**
  (`literature-search-s2`): https://www.semanticscholar.org/product/api
- **Ai2 Asta Scientific Corpus MCP** (`asta` via `scripts/asta_mcp_proxy.py`):
  https://allenai.org/ and https://asta-tools.allen.ai/mcp/v1
- **Elsevier Developer APIs — Scopus & ScienceDirect**
  (`literature-search-elsevier`): https://dev.elsevier.com/policy.html
- **Springer Nature Developer APIs — Meta API v2 & Open Access API**
  (`literature-search-springer`):
  https://dev.springernature.com/terms-and-conditions/
- **CORE API v3** (`literature-search-core`): https://core.ac.uk/terms
