# Science skills (Improved Fork — `agy-scientific-skills-improved`)

> **Fork additions:** This fork of [`google-deepmind/science-skills`](https://github.com/google-deepmind/science-skills) keeps all 40 upstream DeepMind skills intact under `skills/` and adds a self-contained Antigravity plugin under [`plugins/literature-extended/`](plugins/literature-extended/) expanding scientific literature search with **5 additional APIs/tools** following the same `uv run` + `polite-http` + `~/.env` `credentials` design:
>
> - **`literature-search-s2`** — Semantic Scholar Academic Graph & Recommendations API (`S2_API_KEY`)
> - **`literature-search-elsevier`** — Elsevier Scopus Search, ScienceDirect Search v2 (`PUT`), Abstract Retrieval & Article Retrieval (`ELSEVIER_API_KEY`, optional `ELSEVIER_INSTTOKEN`)
> - **`literature-search-springer`** — Springer Nature Meta API v2 & Open Access API including JATS XML full-text extraction (`SPRINGER_META_API_KEY`, `SPRINGER_OA_API_KEY`)
> - **`literature-search-core`** — CORE API v3 open-access repository aggregator, full-text extraction, and redirect-safe PDF downloads (`CORE_API_KEY`)
> - **`asta` MCP server** (`literature-extended_asta`) — Zero-secret local `uv run` stdio proxy (`plugins/literature-extended/scripts/asta_mcp_proxy.py`) bridging to Ai2's Asta Scientific Corpus MCP (`ASTA_API_KEY`)
>
> ### Installing `literature-extended` Alongside Antigravity's Official Modular Plugins
>
> Because Antigravity distributes DeepMind's official skills as separate domain plugins (`scientific-literature`, `chemistry`, `genomics`, `structural-biology`), install just `plugins/literature-extended/` into your global Antigravity plugins folder to avoid duplicating the official skills:
>
> ```bash
> git clone https://github.com/arielmmaia/agy-scientific-skills-improved.git
> cp -r agy-scientific-skills-improved/plugins/literature-extended ~/.gemini/config/plugins/literature-extended
> ```
>
> All API keys are loaded automatically from `~/.env` (or project `.env`) via `python-dotenv` — no secrets are stored in this repository or in `mcp_config.json`. See [`plugins/literature-extended/README.md`](plugins/literature-extended/README.md) for full details.

---

# Science skills (Upstream Documentation)

A collection of agent skills for scientific research tasks, spanning genomics,
structural biology, literature search, and more.

Each skill provides structured instructions, scripts, and resources that extend
an AI agent's capabilities for specialized scientific tasks.

## Skill structure

Each skill directory contains:

-   **SKILL.md** — Main instruction file with YAML frontmatter and detailed
    markdown instructions
-   **scripts/** — Helper scripts and utilities
-   **references/** — Additional documentation and references (optional)

## Using Science skills with [Google Antigravity](https://antigravity.google/)

Science skills are best used in Google Antigravity, with the Science plugin
enabled.

-   Download and install the latest version of Google Antigravity from
    [antigravity.google](https://antigravity.google/).
-   Enable the Science plugin: In the Antigravity app, go to `Customizations` >
    `Build with Google` > `Science` > `Add`.

<details>

<summary><b>Video: how to install</b></summary>

https://github.com/user-attachments/assets/b20751f8-e9b0-442a-804f-2d587eb0426e

</details>

## Using Science skills via `npx`

Install the Science skills bundle via
[npx](https://docs.npmjs.com/cli/commands/npx) using:

```bash
npx skills add google-deepmind/science-skills/
```

### Prerequisites

We use the `uv` package manager to handle dependencies. The first time you
trigger a Science skill, the agent will ask for approval to install `uv`, and
then proceed to respond to your scientific query / task. We recommend restarting
Antigravity after this first time installation.

Some skills, such as AlphaGenome, require an API key to function. Others, such
as ClinVar and OpenAlex, benefit from an API key to unlock higher rate limits
but are still functional without one. The agent should prompt you to obtain the
API key and guide you through writing in the correct location. However, if you
would rather do this yourself, you can run a command like this in your terminal:
`echo "ALPHAGENOME_API_KEY=your_actual_api_key" >> ~/.env`

### Customizing or creating skills

If you want to customize an existing Science skill or create a new skill of your
own, you should **not** modify the files inside the Antigravity Science plugin
installation directory, as your changes will be overwritten whenever the plugin
is updated. Instead, place your custom or modified skills elsewhere, e.g. in
your personal skills directory:

```
~/.gemini/config/skills/
```

## Links

You can find examples and demos of Antigravity's use cases in science at
[antigravity.google/use-cases/science](https://antigravity.google/use-cases/science).

## Licensing & Disclaimer

Copyright 2026 Google LLC

All software is licensed under the Apache License, Version 2.0 (Apache 2.0); you
may not use this file except in compliance with the Apache 2.0 license. You may
obtain a copy of the Apache 2.0 license at:
https://www.apache.org/licenses/LICENSE-2.0

As set out in the attached file
‘[Skill Licences and Terms of Use](SKILL_LICENSES.md)’ certain third party data
sources referenced within individual Skill files have their own applicable
licenses and/or terms of use. See the
‘[Skill Licences and Terms of Use](SKILL_LICENSES.md)’ file for more
information. You are responsible for ensuring that your use of individual Skill
files complies with any such applicable licenses/ terms of use.

All other materials are licensed under the Creative Commons Attribution 4.0
International License (CC-BY). You may obtain a copy of the CC-BY license at:
https://creativecommons.org/licenses/by/4.0/legalcode

Unless required by applicable law or agreed to in writing, all software and
materials distributed here under the Apache 2.0 or CC-BY licenses are
distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the licenses for the specific language governing
permissions and limitations under those licenses.

This is not an official Google product.
