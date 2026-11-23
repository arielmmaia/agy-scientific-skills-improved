# Elsevier Scopus & ScienceDirect Query Syntax & View Reference

## Common Scopus Search Field Codes (`search-scopus` Only)
- `TITLE-ABS-KEY(...)` — Title, abstract, and author keywords (most common)
- `TITLE(...)`, `ABS(...)`, `KEY(...)` — Individual sections
- `AUTH("Jumper J.")` or `AU-ID(12345678900)` — Author search
- `DOI(10.1016/...)` — Exact DOI lookup
- `SRCTITLE("Cell")` or `ISSN(00928674)` — Journal filter
- `PUBYEAR > 2022` / `PUBYEAR = 2024` — Publication year filter
- `OPENACCESS(1)` — Open-access articles only
- `DOCTYPE(ar)` (Article), `DOCTYPE(re)` (Review), `DOCTYPE(cp)` (Conference paper)
- `SUBJAREA(BIOC)` (Biochemistry), `SUBJAREA(MEDI)`, `SUBJAREA(CHEM)`, `SUBJAREA(COMP)`
- Boolean operators: `AND`, `OR`, `AND NOT` (uppercase)

## ScienceDirect Search v2 Syntax (`search-sciencedirect` Only)
- Do **not** use Scopus field codes such as `TITLE-ABS-KEY(...)` or `PUBYEAR > 2022` with `search-sciencedirect`.
- `--query` maps to the ScienceDirect v2 `qs` field, which accepts standard keywords, quoted phrases (`"base editing"`), and uppercase Boolean operators (`AND`, `OR`, `NOT`).
- Pass publication year filters via `--date` (e.g., `--date "2023-2026"`), sorting via `--sort` (`relevance` or `date`), and open-access filtering via `--open-access`.
- ScienceDirect v2 `display.show` accepts discrete page sizes (`10`, `25`, `50`, `100`); `elsevier_cli.py` automatically rounds `--count` up to the next valid bucket and slices results to the exact requested `--count`.

## View Tiers & Access Notes
- **`STANDARD`** (Scopus Search): Works with a standard `ELSEVIER_API_KEY` even off-campus; returns title, first author, journal, date, DOI, EID, citation count, open-access flag (max 25 results/page on standard keys).
- **`COMPLETE`** (Scopus Search): Returns full author lists, affiliations, abstracts, and keywords — requires institutional IP range or `ELSEVIER_INSTTOKEN`.
- **`META` / `META_ABS`** (Article/Abstract Retrieval): Lightweight metadata and abstract views.
- **`FULL`** (Article Retrieval): Full text for Open Access articles, or subscribed articles when on institutional IP / with `ELSEVIER_INSTTOKEN`.

## Common HTTP Error Codes
- `401 Unauthorized` — Invalid or missing `ELSEVIER_API_KEY`.
- `403 Forbidden (AUTHORIZATION_ERROR)` — Requested view (`COMPLETE` or `FULL` on paywalled content) requires institutional IP or `ELSEVIER_INSTTOKEN`; retry with `--view STANDARD` or `--view META_ABS`.
- `429 Too Many Requests (QUOTA_EXCEEDED)` — Rolling 7-day weekly quota exhausted; inspect stderr reset timestamp.
