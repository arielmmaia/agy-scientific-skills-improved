#!/usr/bin/env python3
"""Semantic Scholar (S2) Academic Graph & Recommendations API CLI.

Follows Google DeepMind science-skills conventions:
- PEP 723 inline dependencies for `uv run`
- Cross-process rate limiting via `polite-http`
- Automatic `~/.env` credential loading via `python-dotenv`
- File-first JSON outputs (`--output`)
"""

# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "polite-http",
#   "python-dotenv",
# ]
# ///

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.parse
from typing import Any

import dotenv
from polite_http import http_client

GRAPH_BASE = "https://api.semanticscholar.org/graph/v1/"
RECS_BASE = "https://api.semanticscholar.org/recommendations/v1/"
USER_AGENT = "antigravity-literature-extended/1.0"
BATCH_CHUNK_SIZE = 500
_DOI_URL_RE = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi\.org/)(.+)$", re.IGNORECASE)
_BARE_DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$")

DEFAULT_PAPER_FIELDS = (
    "paperId,externalIds,url,title,year,venue,citationCount,"
    "influentialCitationCount,isOpenAccess,openAccessPdf,tldr,authors"
)
DEFAULT_DETAIL_FIELDS = (
    "paperId,corpusId,externalIds,url,title,abstract,year,venue,"
    "publicationDate,referenceCount,citationCount,influentialCitationCount,"
    "isOpenAccess,openAccessPdf,fieldsOfStudy,publicationTypes,tldr,authors"
)
DEFAULT_CITATION_FIELDS = (
    "contexts,intents,isInfluential,paperId,externalIds,title,year,venue,"
    "citationCount,authors"
)
DEFAULT_AUTHOR_FIELDS = (
    "authorId,url,name,affiliations,paperCount,citationCount,hIndex"
)


def _safe_load_dotenv() -> None:
  for path in (None, os.path.expanduser("~/.env")):
    try:
      if path is None:
        dotenv.load_dotenv()
      else:
        dotenv.load_dotenv(path)
    except OSError:
      pass


def _normalize_paper_id(paper_id: str) -> str:
  pid = paper_id.strip()
  m = _DOI_URL_RE.match(pid)
  if m:
    return f"DOI:{m.group(1).strip()}"
  if pid.lower().startswith("doi:"):
    return f"DOI:{pid[4:].strip()}"
  if _BARE_DOI_RE.match(pid):
    return f"DOI:{pid}"
  return pid


def _get_api_key() -> str | None:
  return (
      os.environ.get("S2_API_KEY")
      or os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
      or ""
  ).strip() or None


def _make_client(base_url: str, api_key: str | None) -> http_client.HttpClient:
  headers: dict[str, str] = {"Accept": "application/json"}
  if api_key:
    headers["x-api-key"] = api_key
  else:
    print(
        "[!] Warning: S2_API_KEY (or SEMANTIC_SCHOLAR_API_KEY) is not set in"
        " ~/.env. Falling back to the heavily rate-limited anonymous pool.",
        file=sys.stderr,
    )
  # Standard S2 personal API keys allow 1 req/s across all endpoints.
  return http_client.HttpClient(
      base_url,
      qps=0.95,
      user_agent=USER_AGENT,
      default_headers=headers,
      max_retries=5,
      backoff_base=2.0,
      backoff_max=60.0,
  )


def _build_url(path: str, params: dict[str, Any]) -> str:
  clean = {k: v for k, v in params.items() if v is not None and v != ""}
  if not clean:
    return path
  return f"{path}?{urllib.parse.urlencode(clean)}"


def _encode_id(item_id: str) -> str:
  return urllib.parse.quote(item_id, safe=":")


def _write_json(data: Any, output_path: str) -> None:
  try:
    parent = os.path.dirname(os.path.abspath(output_path))
    if parent:
      os.makedirs(parent, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
      json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Success! Data written to: {output_path}")
  except OSError as e:
    print(f"Error writing output file {output_path}: {e}", file=sys.stderr)
    sys.exit(1)


def _add_filter_args(parser: argparse.ArgumentParser) -> None:
  parser.add_argument(
      "--year",
      help="Year or range, e.g. '2023', '2020-2025', '2022-', '-2020'",
  )
  parser.add_argument("--venue", help="Comma-separated venue names")
  parser.add_argument(
      "--fields-of-study",
      help="Comma-separated fields of study, e.g. 'Biology,Medicine'",
  )
  parser.add_argument(
      "--publication-types",
      help="Comma-separated types, e.g. 'Review,JournalArticle'",
  )
  parser.add_argument(
      "--min-citation-count",
      type=int,
      help="Minimum citation count filter",
  )
  parser.add_argument(
      "--open-access-pdf",
      action="store_true",
      help="Restrict to papers with a public open-access PDF",
  )


def _filter_params(args: argparse.Namespace) -> dict[str, Any]:
  params: dict[str, Any] = {
      "year": getattr(args, "year", None),
      "venue": getattr(args, "venue", None),
      "fieldsOfStudy": getattr(args, "fields_of_study", None),
      "publicationTypes": getattr(args, "publication_types", None),
      "minCitationCount": getattr(args, "min_citation_count", None),
  }
  if getattr(args, "open_access_pdf", False):
    params["openAccessPdf"] = ""
  return params


def _build_query_string_with_flags(
    path: str, params: dict[str, Any], flag_keys: set[str]
) -> str:
  parts: list[str] = []
  for k, v in params.items():
    if k in flag_keys:
      parts.append(urllib.parse.quote(k))
    elif v is not None and v != "":
      parts.append(urllib.parse.urlencode({k: v}))
  return f"{path}?{'&'.join(parts)}" if parts else path


def cmd_search(args: argparse.Namespace, client: http_client.HttpClient) -> Any:
  params: dict[str, Any] = {
      "query": args.query,
      "limit": args.limit,
      "offset": args.offset,
      "fields": args.fields,
  }
  params.update(_filter_params(args))
  flags = {"openAccessPdf"} if args.open_access_pdf else set()
  url = _build_query_string_with_flags("paper/search", params, flags)
  return client.fetch_json(url)


def cmd_bulk_search(args: argparse.Namespace, client: http_client.HttpClient) -> Any:
  params: dict[str, Any] = {
      "query": args.query,
      "fields": args.fields,
      "token": args.token,
      "sort": args.sort,
  }
  params.update(_filter_params(args))
  flags = {"openAccessPdf"} if args.open_access_pdf else set()
  url = _build_query_string_with_flags("paper/search/bulk", params, flags)
  return client.fetch_json(url)


def cmd_match(args: argparse.Namespace, client: http_client.HttpClient) -> Any:
  params = {"query": args.query, "fields": args.fields}
  return client.fetch_json(_build_url("paper/search/match", params))


def cmd_get(args: argparse.Namespace, client: http_client.HttpClient) -> Any:
  pid = _encode_id(_normalize_paper_id(args.paper_id))
  return client.fetch_json(_build_url(f"paper/{pid}", {"fields": args.fields}))


def cmd_batch(args: argparse.Namespace, client: http_client.HttpClient) -> Any:
  ids: list[str] = []
  if args.ids:
    ids.extend(_normalize_paper_id(x) for x in args.ids.split(",") if x.strip())
  if args.ids_file:
    with open(args.ids_file, encoding="utf-8") as f:
      for line in f:
        s = line.strip()
        if s and not s.startswith("#"):
          ids.append(_normalize_paper_id(s))
  if not ids:
    print("Error: Provide at least one ID via --ids or --ids-file.", file=sys.stderr)
    sys.exit(1)

  all_results: list[Any] = []
  url = _build_url("paper/batch", {"fields": args.fields})
  for i in range(0, len(ids), BATCH_CHUNK_SIZE):
    chunk = ids[i : i + BATCH_CHUNK_SIZE]
    chunk_data = client.fetch_json(url, method="POST", json_body={"ids": chunk})
    if isinstance(chunk_data, list):
      all_results.extend(chunk_data)
    else:
      all_results.append(chunk_data)
  return {"count": len(all_results), "data": all_results}


def cmd_graph_edges(
    args: argparse.Namespace, client: http_client.HttpClient, edge: str
) -> Any:
  pid = _encode_id(_normalize_paper_id(args.paper_id))
  params = {
      "fields": args.fields,
      "limit": args.limit,
      "offset": args.offset,
  }
  return client.fetch_json(_build_url(f"paper/{pid}/{edge}", params))


def cmd_snippets(args: argparse.Namespace, client: http_client.HttpClient) -> Any:
  paper_ids = None
  if args.paper_ids:
    paper_ids = ",".join(
        _normalize_paper_id(x) for x in args.paper_ids.split(",") if x.strip()
    )
  params: dict[str, Any] = {
      "query": args.query,
      "limit": args.limit,
      "paperIds": paper_ids,
      "year": args.year,
      "venue": args.venue,
      "fieldsOfStudy": args.fields_of_study,
      "minCitationCount": args.min_citation_count,
  }
  return client.fetch_json(_build_url("snippet/search", params))


def cmd_recommend(args: argparse.Namespace, api_key: str | None) -> Any:
  recs_client = _make_client(RECS_BASE, api_key)
  pos_ids = [_normalize_paper_id(x) for x in args.positive]
  neg_ids = [_normalize_paper_id(x) for x in (args.negative or [])]
  if len(pos_ids) == 1 and not neg_ids:
    pid = _encode_id(pos_ids[0])
    params: dict[str, Any] = {
        "fields": args.fields,
        "limit": args.limit,
        "from": args.pool,
    }
    return recs_client.fetch_json(_build_url(f"papers/forpaper/{pid}", params))

  url = _build_url("papers/", {"fields": args.fields, "limit": args.limit})
  payload = {
      "positivePaperIds": pos_ids,
      "negativePaperIds": neg_ids,
  }
  return recs_client.fetch_json(url, method="POST", json_body=payload)


def cmd_author_search(args: argparse.Namespace, client: http_client.HttpClient) -> Any:
  params = {
      "query": args.query,
      "fields": args.fields,
      "limit": args.limit,
      "offset": args.offset,
  }
  return client.fetch_json(_build_url("author/search", params))


def cmd_author_papers(args: argparse.Namespace, client: http_client.HttpClient) -> Any:
  aid = _encode_id(args.author_id)
  params = {
      "fields": args.fields,
      "limit": args.limit,
      "offset": args.offset,
  }
  return client.fetch_json(_build_url(f"author/{aid}/papers", params))


def build_parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(
      description="Semantic Scholar (S2) Graph & Recommendations CLI"
  )
  sub = parser.add_subparsers(dest="command", required=True)

  p_search = sub.add_parser("search", help="Relevance keyword search")
  p_search.add_argument("query", help="Search query string")
  p_search.add_argument("--limit", type=int, required=True, help="Results per page (1-100)")
  p_search.add_argument("--offset", type=int, default=0, help="Pagination offset")
  p_search.add_argument("--fields", default=DEFAULT_PAPER_FIELDS)
  _add_filter_args(p_search)
  p_search.add_argument("--output", required=True, help="Output JSON file path")

  p_bulk = sub.add_parser("bulk-search", help="Boolean bulk search with token pagination")
  p_bulk.add_argument("query", help="Boolean query string")
  p_bulk.add_argument("--token", help="Pagination token from previous response")
  p_bulk.add_argument("--sort", help="Sort e.g. 'citationCount:desc' or 'publicationDate:desc'")
  p_bulk.add_argument("--fields", default=DEFAULT_PAPER_FIELDS)
  _add_filter_args(p_bulk)
  p_bulk.add_argument("--output", required=True, help="Output JSON file path")

  p_match = sub.add_parser("match", help="Find closest single paper matching a title")
  p_match.add_argument("query", help="Paper title to match")
  p_match.add_argument("--fields", default=DEFAULT_DETAIL_FIELDS)
  p_match.add_argument("--output", required=True, help="Output JSON file path")

  p_get = sub.add_parser("get", help="Get detailed metadata for a single paper ID")
  p_get.add_argument("paper_id", help="S2 ID, DOI, doi.org URL, ARXIV:..., PMID:..., PMCID:..., etc.")
  p_get.add_argument("--fields", default=DEFAULT_DETAIL_FIELDS)
  p_get.add_argument("--output", required=True, help="Output JSON file path")

  p_batch = sub.add_parser("batch", help="Batch lookup up to 500+ paper IDs")
  p_batch.add_argument("--ids", help="Comma-separated paper IDs")
  p_batch.add_argument("--ids-file", help="Newline-delimited file of paper IDs")
  p_batch.add_argument("--fields", default=DEFAULT_PAPER_FIELDS)
  p_batch.add_argument("--output", required=True, help="Output JSON file path")

  for edge in ("citations", "references"):
    p_edge = sub.add_parser(edge, help=f"Get paper {edge}")
    p_edge.add_argument("paper_id", help="Paper ID (S2 ID, DOI, doi.org URL, ARXIV:..., etc.)")
    p_edge.add_argument("--limit", type=int, required=True, help="Results per page (1-1000)")
    p_edge.add_argument("--offset", type=int, default=0)
    p_edge.add_argument("--fields", default=DEFAULT_CITATION_FIELDS)
    p_edge.add_argument("--output", required=True, help="Output JSON file path")

  p_snip = sub.add_parser("snippets", help="Full-text ~500-word passage snippet search")
  p_snip.add_argument("query", help="Plain-text query for passage search")
  p_snip.add_argument("--limit", type=int, required=True, help="Max snippets (1-1000)")
  p_snip.add_argument("--paper-ids", help="Optional comma-separated paper IDs to restrict search")
  p_snip.add_argument("--year", help="Year or range, e.g. '2022-'")
  p_snip.add_argument("--venue", help="Comma-separated venue filter")
  p_snip.add_argument("--fields-of-study", help="Comma-separated fields of study")
  p_snip.add_argument("--min-citation-count", type=int)
  p_snip.add_argument("--output", required=True, help="Output JSON file path")

  p_rec = sub.add_parser("recommend", help="Paper recommendations from seed paper IDs")
  p_rec.add_argument("--positive", nargs="+", required=True, help="One or more positive seed paper IDs")
  p_rec.add_argument("--negative", nargs="*", default=[], help="Optional negative seed paper IDs")
  p_rec.add_argument("--limit", type=int, required=True, help="Number of recommendations (1-500)")
  p_rec.add_argument("--pool", choices=["recent", "all-cs"], help="Candidate pool (single-seed only)")
  p_rec.add_argument("--fields", default=DEFAULT_PAPER_FIELDS)
  p_rec.add_argument("--output", required=True, help="Output JSON file path")

  p_as = sub.add_parser("author-search", help="Search authors by name")
  p_as.add_argument("query", help="Author name")
  p_as.add_argument("--limit", type=int, required=True, help="Results per page (1-1000)")
  p_as.add_argument("--offset", type=int, default=0)
  p_as.add_argument("--fields", default=DEFAULT_AUTHOR_FIELDS)
  p_as.add_argument("--output", required=True, help="Output JSON file path")

  p_ap = sub.add_parser("author-papers", help="List papers for an author ID")
  p_ap.add_argument("author_id", help="Semantic Scholar authorId")
  p_ap.add_argument("--limit", type=int, required=True, help="Results per page (1-1000)")
  p_ap.add_argument("--offset", type=int, default=0)
  p_ap.add_argument("--fields", default=DEFAULT_PAPER_FIELDS)
  p_ap.add_argument("--output", required=True, help="Output JSON file path")

  return parser


def main() -> None:
  parser = build_parser()
  args = parser.parse_args()
  _safe_load_dotenv()
  api_key = _get_api_key()

  try:
    if args.command == "recommend":
      data = cmd_recommend(args, api_key)
    else:
      client = _make_client(GRAPH_BASE, api_key)
      if args.command == "search":
        data = cmd_search(args, client)
      elif args.command == "bulk-search":
        data = cmd_bulk_search(args, client)
      elif args.command == "match":
        data = cmd_match(args, client)
      elif args.command == "get":
        data = cmd_get(args, client)
      elif args.command == "batch":
        data = cmd_batch(args, client)
      elif args.command in ("citations", "references"):
        data = cmd_graph_edges(args, client, args.command)
      elif args.command == "snippets":
        data = cmd_snippets(args, client)
      elif args.command == "author-search":
        data = cmd_author_search(args, client)
      elif args.command == "author-papers":
        data = cmd_author_papers(args, client)
      else:
        parser.error(f"Unknown command: {args.command}")
  except http_client.HttpError as e:
    print(f"Semantic Scholar API error (HTTP {e.status_code}): {e}", file=sys.stderr)
    sys.exit(1)

  _write_json(data, args.output)


if __name__ == "__main__":
  main()
