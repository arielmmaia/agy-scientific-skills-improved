#!/usr/bin/env python3
"""CORE API v3 CLI — open-access search, metadata, full text & PDF downloads.

Reads CORE_API_KEY from ~/.env (sent via Authorization: Bearer).
Enforces conservative cross-process pacing via polite-http, logs X-RateLimit-*
response headers to stderr, and strips Authorization on cross-origin redirects
during PDF downloads.
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
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

import dotenv
from polite_http import http_client

BASE_URL = "https://api.core.ac.uk/v3/"
USER_AGENT = "antigravity-literature-extended/1.0"
_DOI_PREFIX_RE = re.compile(
    r"^(?:https?://(?:dx\.)?doi\.org/|doi\.org/|doi:\s*)", re.IGNORECASE
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


def _normalize_doi(doi: str) -> str:
  return _DOI_PREFIX_RE.sub("", doi.strip()).strip()


def _origin(url: str) -> tuple[str, str, int | None]:
  parsed = urllib.parse.urlparse(url)
  scheme = (parsed.scheme or "").lower()
  host = (parsed.hostname or "").lower()
  port = parsed.port
  if port is None:
    port = 443 if scheme == "https" else 80 if scheme == "http" else None
  return (scheme, host, port)


class _CrossOriginSafeRedirectHandler(urllib.request.HTTPRedirectHandler):
  """Strips Authorization headers whenever a redirect changes origin."""

  def redirect_request(self, req, fp, code, msg, headers, newurl):
    new_req = super().redirect_request(req, fp, code, msg, headers, newurl)
    if new_req is None:
      return None
    if _origin(req.full_url) != _origin(new_req.full_url):
      for h_dict in (new_req.headers, new_req.unredirected_hdrs):
        for key in list(h_dict.keys()):
          if key.lower() == "authorization":
            del h_dict[key]
    return new_req


def _get_api_key() -> str:
  key = (os.environ.get("CORE_API_KEY") or "").strip()
  if not key:
    print(
        "Error: CORE_API_KEY is not set in ~/.env.\n"
        "Register for a free academic key at https://core.ac.uk/services/api"
        " and add it via the safe credentials protocol in the 'credentials'"
        " skill.",
        file=sys.stderr,
    )
    sys.exit(1)
  return key


def _make_client(api_key: str) -> http_client.HttpClient:
  # Conservative free-tier baseline (~5 single requests / 10s).
  return http_client.HttpClient(
      BASE_URL,
      qps=0.5,
      user_agent=USER_AGENT,
      default_headers={
          "Authorization": f"Bearer {api_key}",
          "Accept": "application/json",
      },
      max_retries=4,
      backoff_base=3.0,
      backoff_max=90.0,
  )


def _log_rate_limit(headers: dict[str, str]) -> None:
  lower = {k.lower(): v for k, v in headers.items()}
  parts = []
  rem = lower.get("x-ratelimit-remaining")
  lim = lower.get("x-ratelimit-limit")
  retry = lower.get("x-ratelimit-retry-after") or lower.get("retry-after")
  if rem is not None and lim is not None:
    parts.append(f"remaining={rem}/{lim}")
  elif rem is not None:
    parts.append(f"remaining={rem}")
  if retry is not None:
    parts.append(f"retry_after={retry}")
  if parts:
    print(f"[CORE rate-limit] {', '.join(parts)}", file=sys.stderr)


def _slim_work(work: Any, *, include_fulltext: bool) -> Any:
  if include_fulltext or not isinstance(work, dict):
    return work
  out = dict(work)
  ft = out.pop("fullText", None)
  out["hasFullText"] = bool(ft and isinstance(ft, str) and ft.strip())
  out["fullTextLength"] = len(ft) if isinstance(ft, str) else 0
  return out


def _slim_payload(data: Any, *, include_fulltext: bool) -> Any:
  if include_fulltext:
    return data
  if isinstance(data, dict) and isinstance(data.get("results"), list):
    out = dict(data)
    out["results"] = [
        _slim_work(w, include_fulltext=False) for w in data["results"]
    ]
    return out
  if isinstance(data, list):
    return [_slim_work(w, include_fulltext=False) for w in data]
  return _slim_work(data, include_fulltext=False)


def _write_output(content: Any, output_path: str, *, mode: str = "json") -> None:
  try:
    parent = os.path.dirname(os.path.abspath(output_path))
    if parent:
      os.makedirs(parent, exist_ok=True)
    if mode == "bytes":
      with open(output_path, "wb") as f:
        f.write(content)
    elif mode == "text":
      with open(output_path, "w", encoding="utf-8") as f:
        f.write(str(content))
    else:
      with open(output_path, "w", encoding="utf-8") as f:
        json.dump(content, f, indent=2, ensure_ascii=False)
    print(f"Success! Data written to: {output_path}")
  except OSError as e:
    print(f"Error writing output file {output_path}: {e}", file=sys.stderr)
    sys.exit(1)


def _fetch_work(
    client: http_client.HttpClient,
    *,
    work_id: str | None = None,
    doi: str | None = None,
) -> dict[str, Any]:
  if work_id:
    path = f"works/{urllib.parse.quote(str(work_id), safe='')}"
    resp = client.fetch(path)
    _log_rate_limit(resp.headers)
    return resp.json()
  assert doi is not None
  doi_clean = _normalize_doi(doi)
  try:
    path = f"works/doi:{urllib.parse.quote(doi_clean, safe='/')}"
    resp = client.fetch(path)
    _log_rate_limit(resp.headers)
    return resp.json()
  except http_client.HttpError as e:
    if e.status_code != 404:
      raise
  q = urllib.parse.urlencode({"q": f'doi:"{doi_clean}"', "limit": 1})
  resp = client.fetch(f"search/works?{q}")
  _log_rate_limit(resp.headers)
  payload = resp.json()
  results = payload.get("results") or []
  if not results:
    print(f"Error: No CORE work found for DOI: {doi_clean}", file=sys.stderr)
    sys.exit(1)
  return results[0]


def _download_pdf_bytes(
    url: str, api_key: str, *, attach_bearer: bool
) -> bytes | None:
  parsed = urllib.parse.urlparse(url)
  if not parsed.scheme or not parsed.netloc:
    return None
  # Enforce cross-process per-host rate limiting via polite-http, while using
  # a redirect handler that strips Authorization on cross-origin hops so
  # CORE_API_KEY never leaks to third-party repositories or breaks S3 URLs.
  base = f"{parsed.scheme}://{parsed.netloc}/"
  limiter_client = http_client.HttpClient(base, qps=0.5, user_agent=USER_AGENT)
  limiter_client.wait()

  headers = {
      "User-Agent": USER_AGENT,
      "Accept": "application/pdf,*/*",
  }
  if attach_bearer:
    headers["Authorization"] = f"Bearer {api_key}"

  req = urllib.request.Request(url, headers=headers, method="GET")
  opener = urllib.request.build_opener(_CrossOriginSafeRedirectHandler())
  try:
    with opener.open(req, timeout=60.0) as resp:
      data = resp.read()
  except urllib.error.HTTPError as e:
    print(f"[CORE] PDF fetch failed from {url}: HTTP {e.code}", file=sys.stderr)
    return None
  except (urllib.error.URLError, OSError) as e:
    print(f"[CORE] PDF fetch error from {url}: {e}", file=sys.stderr)
    return None

  if data and data.lstrip()[:5] == b"%PDF-":
    return data
  print(f"[CORE] URL did not return a valid PDF: {url}", file=sys.stderr)
  return None


def build_parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(description="CORE API v3 CLI")
  sub = parser.add_subparsers(dest="command", required=True)

  p_search = sub.add_parser("search", help="Search open-access works")
  p_search.add_argument("query", help="CORE Elasticsearch query string")
  p_search.add_argument("--limit", type=int, required=True, help="Results per page (1-100)")
  p_search.add_argument("--offset", type=int, default=0, help="Pagination offset")
  p_search.add_argument("--scroll", action="store_true", help="Enable deep scroll (higher quota cost)")
  p_search.add_argument("--scroll-id", help="Scroll token from previous scroll response")
  p_search.add_argument(
      "--has-fulltext",
      action="store_true",
      help="Append 'AND _exists_:fullText' to query",
  )
  p_search.add_argument(
      "--include-fulltext",
      action="store_true",
      help="Keep raw fullText in search JSON (default strips it for brevity)",
  )
  p_search.add_argument("--output", required=True, help="Output JSON file path")

  p_get = sub.add_parser("get", help="Get work metadata by CORE ID or DOI")
  g_get = p_get.add_mutually_exclusive_group(required=True)
  g_get.add_argument("--id", dest="work_id", help="Numeric CORE work ID")
  g_get.add_argument("--doi", help="Article DOI (with or without doi.org/ or DOI: prefix)")
  p_get.add_argument("--include-fulltext", action="store_true")
  p_get.add_argument("--output", required=True, help="Output JSON file path")

  p_batch = sub.add_parser("batch", help="Batch retrieve works by CORE IDs (POST /v3/works)")
  p_batch.add_argument("--ids", help="Comma-separated numeric CORE IDs")
  p_batch.add_argument("--ids-file", help="Newline-delimited file of numeric CORE IDs")
  p_batch.add_argument("--include-fulltext", action="store_true")
  p_batch.add_argument("--output", required=True, help="Output JSON file path")

  p_ft = sub.add_parser("get-fulltext", help="Extract parsed fullText to plain-text file")
  g_ft = p_ft.add_mutually_exclusive_group(required=True)
  g_ft.add_argument("--id", dest="work_id", help="Numeric CORE work ID")
  g_ft.add_argument("--doi", help="Article DOI (with or without doi.org/ or DOI: prefix)")
  p_ft.add_argument("--output", required=True, help="Output .txt file path")

  p_pdf = sub.add_parser("download-pdf", help="Download open-access PDF for a CORE work")
  g_pdf = p_pdf.add_mutually_exclusive_group(required=True)
  g_pdf.add_argument("--id", dest="work_id", help="Numeric CORE work ID")
  g_pdf.add_argument("--doi", help="Article DOI (with or without doi.org/ or DOI: prefix)")
  p_pdf.add_argument("--output", required=True, help="Output .pdf file path")

  p_prov = sub.add_parser("providers", help="Search CORE repository data providers")
  p_prov.add_argument("query", help="Provider search query")
  p_prov.add_argument("--limit", type=int, required=True, help="Results per page (1-100)")
  p_prov.add_argument("--offset", type=int, default=0)
  p_prov.add_argument("--output", required=True, help="Output JSON file path")

  return parser


def main() -> None:
  parser = build_parser()
  args = parser.parse_args()
  _safe_load_dotenv()
  api_key = _get_api_key()
  client = _make_client(api_key)

  try:
    if args.command == "search":
      q = args.query
      if args.has_fulltext and "_exists_:fullText" not in q:
        q = f"({q}) AND _exists_:fullText"
      params: dict[str, Any] = {"q": q, "limit": args.limit}
      if args.scroll_id:
        params["scrollId"] = args.scroll_id
      elif args.scroll:
        print(
            "[CORE] Note: scroll=true consumes more quota tokens per request.",
            file=sys.stderr,
        )
        params["scroll"] = "true"
      else:
        params["offset"] = args.offset
      resp = client.fetch(f"search/works?{urllib.parse.urlencode(params)}")
      _log_rate_limit(resp.headers)
      data = _slim_payload(resp.json(), include_fulltext=args.include_fulltext)
      _write_output(data, args.output, mode="json")

    elif args.command == "get":
      work = _fetch_work(client, work_id=args.work_id, doi=args.doi)
      _write_output(
          _slim_work(work, include_fulltext=args.include_fulltext),
          args.output,
          mode="json",
      )

    elif args.command == "batch":
      raw_ids: list[str] = []
      if args.ids:
        raw_ids.extend(x.strip() for x in args.ids.split(",") if x.strip())
      if args.ids_file:
        with open(args.ids_file, encoding="utf-8") as f:
          raw_ids.extend(
              line.strip() for line in f if line.strip() and not line.startswith("#")
          )
      if not raw_ids:
        print("Error: Provide IDs via --ids or --ids-file.", file=sys.stderr)
        sys.exit(1)
      ids_payload: list[int | str] = [
          int(x) if x.isdigit() else x for x in raw_ids
      ]
      resp = client.fetch("works", method="POST", json_body=ids_payload)
      _log_rate_limit(resp.headers)
      data = _slim_payload(resp.json(), include_fulltext=args.include_fulltext)
      _write_output(data, args.output, mode="json")

    elif args.command == "get-fulltext":
      work = _fetch_work(client, work_id=args.work_id, doi=args.doi)
      ft = work.get("fullText")
      if not ft or not isinstance(ft, str) or not ft.strip():
        dl = work.get("downloadUrl") or ""
        print(
            "Error: CORE record does not contain indexed fullText."
            + (f" Candidate downloadUrl: {dl}" if dl else ""),
            file=sys.stderr,
        )
        sys.exit(1)
      _write_output(ft, args.output, mode="text")

    elif args.command == "download-pdf":
      work = _fetch_work(client, work_id=args.work_id, doi=args.doi)
      candidates: list[tuple[str, bool]] = []
      if work.get("id"):
        candidates.append((f"{BASE_URL}works/{work['id']}/download", True))
      if work.get("downloadUrl"):
        u = str(work["downloadUrl"])
        candidates.append((u, _origin(u)[1] == "api.core.ac.uk"))
      for u in work.get("sourceFulltextUrls") or []:
        if u:
          candidates.append((str(u), False))
      seen: set[str] = set()
      for url, attach in candidates:
        if url in seen:
          continue
        seen.add(url)
        pdf_bytes = _download_pdf_bytes(url, api_key, attach_bearer=attach)
        if pdf_bytes:
          _write_output(pdf_bytes, args.output, mode="bytes")
          return
      print(
          "Error: Could not download a valid PDF from any CORE/source URL.",
          file=sys.stderr,
      )
      sys.exit(1)

    elif args.command == "providers":
      params = {"q": args.query, "limit": args.limit, "offset": args.offset}
      resp = client.fetch(f"search/data-providers?{urllib.parse.urlencode(params)}")
      _log_rate_limit(resp.headers)
      _write_output(resp.json(), args.output, mode="json")

  except http_client.HttpError as e:
    print(f"CORE API error (HTTP {e.status_code}): {e}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
  main()
