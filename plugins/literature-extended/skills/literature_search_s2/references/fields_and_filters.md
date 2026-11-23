# Semantic Scholar (S2) Fields, IDs & Bulk Query Reference

## Supported Paper ID Formats
- Semantic Scholar 40-char SHA: `649def34f8be52c8b66281af98ae884c09aef38b`
- Corpus ID: `CorpusId:215416146`
- DOI: `DOI:10.1038/s41586-021-03819-2`
- arXiv: `ARXIV:1706.03762`
- PubMed: `PMID:34265844`
- PubMed Central: `PMCID:PMC8371605`
- ACL Anthology: `ACL:W12-3903`
- MAG: `MAG:112218234`
- URL: `URL:https://arxiv.org/abs/1706.03762`

## Common Paper `--fields`
- Identifiers: `paperId`, `corpusId`, `externalIds`, `url`
- Core bibliographic: `title`, `abstract`, `venue`, `publicationVenue`, `year`, `publicationDate`, `journal`, `publicationTypes`
- Impact & access: `referenceCount`, `citationCount`, `influentialCitationCount`, `isOpenAccess`, `openAccessPdf`, `fieldsOfStudy`, `s2FieldsOfStudy`
- Summaries & authors: `tldr`, `authors`, `authors.authorId`, `authors.name`, `authors.affiliations`, `authors.hIndex`

## Citation / Reference Edge `--fields`
- `contexts`, `intents`, `isInfluential` plus any paper fields above (returned under `citingPaper` / `citedPaper`).

## Bulk Search (`bulk-search`) Boolean Operators
- `+term` — term must appear
- `-term` — exclude term
- `term1 | term2` — logical OR
- `"exact phrase"` — phrase match
- `"word1 word2"~3` — proximity match within 3 words
- `term*` — prefix wildcard
- Parentheses `(...)` for grouping
- `--sort` accepts `paperId`, `publicationDate`, or `citationCount` with `:asc` or `:desc`.
