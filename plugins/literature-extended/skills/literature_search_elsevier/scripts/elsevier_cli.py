#!/usr/bin/env python3
"""Elsevier Developer API CLI (Scopus Search, ScienceDirect v2 Search & Retrieval).

Reads ELSEVIER_API_KEY (required) and ELSEVIER_INSTTOKEN (optional) from ~/.env.
Enforces cross-process rate limiting via polite-http and logs live weekly quota
headers (X-RateLimit-Limit / Remaining / Reset) to stderr on both success and
error responses (including HTTP 429 QUOTA_EXCEEDED).
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
import datetime
import errno
import gzip
import json
import os
import random
import re
import socket
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any

import dotenv
from polite_http import http_client

BASE_URL = "https://api.elsevier.com/content/"
USER_AGENT = "antigravity-literature-extended/1.0"
MAX_RETRIES = 4
_SD_SHOW_BUCKETS = (10, 25, 50, 100)
_NON_RETRYABLE_ERRNOS = frozenset({errno.ENETUNREACH, errno.EACCES, errno.EPERM})
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


def _is_retryable_network_error(exc: OSError) -> bool:
  reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
  if not isinstance(reason, OSError):
    return False
  if isinstance(reason, (socket.gaierror, ssl.SSLCertVerificationError)):
    return False
  if isinstance(reason, ssl.SSLError):
    return True
  return reason.errno not in _NON_RETRYABLE_ERRNOS


def _sd_show_bucket(count: int) -> int:
  if count < 1 or count > 100:
    raise ValueError("--count must be between 1 and 100 for search-sciencedirect.")
  for bucket in _SD_SHOW_BUCKETS:
    if count <= bucket:
      return bucket
  return 100


def _normalize_doi(doi: str) -> str:
  return _DOI_PREFIX_RE.sub("", doi.strip()).strip()


def _get_credentials() -> tuple[str, str | None]:
  api_key = (os.environ.get("ELSEVIER_API_KEY") or "").strip()
  if not api_key:
    print(
        "Error: ELSEVIER_API_KEY is not set in ~/.env.\n"
        "Register at https://dev.elsevier.com/ and add it via the safe"
        " credentials protocol in the 'credentials' skill.",
        file=sys.stderr,
    )
    sys.exit(1)
  insttoken = (os.environ.get("ELSEVIER_INSTTOKEN") or "").strip() or None
  return api_key, insttoken


def _make_limiter_client() -> http_client.HttpClient:
  # Conservative 2 req/s cross-process pacing via polite-http file lock.
  return http_client.HttpClient(
      BASE_URL,
      qps=2.0,
      user_agent=USER_AGENT,
      max_retries=0,
  )


def _extract_quota(headers: Any) -> dict[str, str]:
  if not headers:
    return {}
  lower = {k.lower(): v for k, v in dict(headers).items()}
  quota: dict[str, str] = {}
  for src, dst in (
      ("x-ratelimit-limit", "limit"),
      ("x-ratelimit-remaining", "remaining"),
      ("x-ratelimit-reset", "reset"),
      ("x-els-status", "status"),
  ):
    if src in lower:
      quota[dst] = lower[src]
  if "reset" in quota and quota["reset"].isdigit():
    ts = int(quota["reset"])
    quota["reset_utc"] = datetime.datetime.fromtimestamp(
        ts, tz=datetime.timezone.utc
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
  return quota


def _log_quota(quota: dict[str, str]) -> None:
  if not quota:
    return
  parts = []
  if "remaining" in quota and "limit" in quota:
    parts.append(f"remaining={quota['remaining']}/{quota['limit']}")
  elif "remaining" in quota:
    parts.append(f"remaining={quota['remaining']}")
  if "reset_utc" in quota:
    parts.append(f"reset={quota['reset_utc']}")
  elif "reset" in quota:
    parts.append(f"reset={quota['reset']}")
  if "status" in quota:
    parts.append(f"status={quota['status']}")
  if parts:
    print(f"[Elsevier quota] {', '.join(parts)}", file=sys.stderr)


def _decode_body(raw: bytes, headers: Any) -> str:
  encoding = ""
  if headers:
    encoding = (dict(headers).get("Content-Encoding") or "").lower()
  if encoding in ("gzip", "x-gzip") or raw.startswith(b"\x1f\x8b"):
    try:
      raw = gzip.decompress(raw)
    except OSError:
      pass
  return raw.decode("utf-8", errors="replace")


def _is_weekly_quota_exceeded(
    status_code: int, quota: dict[str, str], body_text: str
) -> bool:
  if status_code != 429:
    return False
  status_hdr = quota.get("status", "").lower()
  return "quota_exceeded" in status_hdr or "quota_exceeded" in body_text.lower()


def _fetch(
    limiter: http_client.HttpClient,
    api_key: str,
    insttoken: str | None,
    path: str,
    *,
    method: str = "GET",
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    accept: str = "application/json",
) -> tuple[str, dict[str, str]]:
  clean = {
      k: v for k, v in (params or {}).items() if v is not None and v != ""
  }
  full_url = urllib.parse.urljoin(BASE_URL, path)
  if clean:
    full_url = f"{full_url}?{urllib.parse.urlencode(clean)}"

  headers: dict[str, str] = {
      "User-Agent": USER_AGENT,
      "Accept": accept,
      "Accept-Encoding": "gzip",
      "X-ELS-APIKey": api_key,
  }
  if insttoken:
    headers["X-ELS-Insttoken"] = insttoken

  body_bytes: bytes | None = None
  if json_body is not None:
    body_bytes = json.dumps(json_body).encode("utf-8")
    headers["Content-Type"] = "application/json"

  attempt = 0
  while True:
    limiter.wait()
    req = urllib.request.Request(
        full_url, data=body_bytes, headers=headers, method=method
    )
    try:
      with urllib.request.urlopen(req, timeout=60.0) as resp:
        resp_headers = dict(resp.headers)
        _log_quota(_extract_quota(resp_headers))
        return _decode_body(resp.read(), resp_headers), resp_headers
    except urllib.error.HTTPError as e:
      err_headers = dict(e.headers) if e.headers else {}
      quota = _extract_quota(err_headers)
      _log_quota(quota)
      err_body = _decode_body(e.read(), err_headers)
      if _is_weekly_quota_exceeded(e.code, quota, err_body):
        reset_msg = (
            f" Resets at {quota['reset_utc']}."
            if "reset_utc" in quota
            else ""
        )
        print(
            "Error: Elsevier weekly API quota exceeded (HTTP 429"
            f" QUOTA_EXCEEDED).{reset_msg} Do not retry until the reset window.",
            file=sys.stderr,
        )
        sys.exit(1)
      if e.code in (401, 403):
        print(
            f"Error: Elsevier authorization failed (HTTP {e.code})."
            " Note: FULL article views, ScienceDirect retrieval, or"
            " view=COMPLETE Scopus queries may require institutional IP access"
            " or ELSEVIER_INSTTOKEN. Try --view STANDARD or --view META_ABS.\n"
            f"Server body: {err_body[:500]}",
            file=sys.stderr,
        )
        sys.exit(1)
      retriable = e.code in (429, 500, 502, 503, 504)
      if not retriable or attempt >= MAX_RETRIES:
        print(
            f"Elsevier API error (HTTP {e.code}) on {full_url}:\n"
            f"{err_body[:500]}",
            file=sys.stderr,
        )
        sys.exit(1)
      delay = min(2.0 * (2**attempt), 30.0) + random.uniform(0, 0.5)
      print(
          f"[Elsevier] Transient error (HTTP {e.code}); retrying in"
          f" {delay:.1f}s (attempt {attempt + 1}/{MAX_RETRIES})...",
          file=sys.stderr,
      )
      limiter.wait(min_sleep=delay)
      attempt += 1
    except (urllib.error.URLError, OSError) as e:
      if not _is_retryable_network_error(e) or attempt >= MAX_RETRIES:
        print(
            f"Elsevier network error on {full_url}: {e}",
            file=sys.stderr,
        )
        sys.exit(1)
      delay = min(2.0 * (2**attempt), 30.0) + random.uniform(0, 0.5)
      limiter.wait(min_sleep=delay)
      attempt += 1


def _xml_to_plain_text(xml_text: str) -> str:
  try:
    root = ET.fromstring(xml_text)
  except ET.ParseError:
    return re.sub(r"<[^>]+>", " ", xml_text)
  chunks: list[str] = []
  for elem in root.iter():
    tag = elem.tag.split("}")[-1].lower()
    if tag in ("title", "section-title", "para", "simple-para", "abstract"):
      text = " ".join("".join(elem.itertext()).split())
      if text:
        chunks.append(text)
  if not chunks:
    return " ".join("".join(root.itertext()).split())
  return "\n\n".join(chunks)


def _write_output(content: Any, output_path: str, *, as_json: bool = True) -> None:
  try:
    parent = os.path.dirname(os.path.abspath(output_path))
    if parent:
      os.makedirs(parent, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
      if as_json:
        json.dump(content, f, indent=2, ensure_ascii=False)
      else:
        f.write(str(content))
    print(f"Success! Data written to: {output_path}")
  except OSError as e:
    print(f"Error writing output file {output_path}: {e}", file=sys.stderr)
    sys.exit(1)


def build_parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(
      description="Elsevier Scopus & ScienceDirect API CLI"
  )
  sub = parser.add_subparsers(dest="command", required=True)

  p_scopus = sub.add_parser("search-scopus", help="Search Scopus bibliographic database")
  p_scopus.add_argument("--query", required=True, help="Scopus query e.g. TITLE-ABS-KEY(CRISPR)")
  p_scopus.add_argument("--count", type=int, required=True, help="Results per page (typically 1-25 for STANDARD)")
  p_scopus.add_argument("--start", type=int, help="0-based offset (ignored if --cursor is used)")
  p_scopus.add_argument("--cursor", help="Cursor value ('*' for first page, or next cursor token)")
  p_scopus.add_argument("--view", default="STANDARD", choices=["STANDARD", "COMPLETE"])
  p_scopus.add_argument("--sort", help="Sort e.g. '-citedby-count' or '-coverDate'")
  p_scopus.add_argument("--date", help="Year range e.g. '2022-2026'")
  p_scopus.add_argument("--output", required=True, help="Output JSON file path")

  p_sd = sub.add_parser(
      "search-sciencedirect",
      help="Search ScienceDirect articles via Search API v2 (PUT)",
  )
  p_sd.add_argument("--query", required=True, help="ScienceDirect search query ('qs')")
  p_sd.add_argument("--count", type=int, required=True, help="Results per page (1-100)")
  p_sd.add_argument("--start", type=int, default=0, help="0-based result offset")
  p_sd.add_argument("--date", help="Year or range e.g. '2023-2026'")
  p_sd.add_argument("--sort", choices=["relevance", "date"], help="Sort order")
  p_sd.add_argument(
      "--open-access",
      action="store_true",
      help="Restrict to Open Access ScienceDirect articles",
  )
  p_sd.add_argument("--output", required=True, help="Output JSON file path")

  p_abs = sub.add_parser("get-abstract", help="Retrieve Scopus abstract/metadata by ID")
  p_abs.add_argument(
      "--id-type",
      required=True,
      choices=["doi", "eid", "scopus_id", "pmid", "pii"],
  )
  p_abs.add_argument("--id", required=True, dest="identifier")
  p_abs.add_argument("--view", default="META_ABS", choices=["META", "META_ABS", "FULL", "REF"])
  p_abs.add_argument("--output", required=True, help="Output JSON file path")

  p_art = sub.add_parser("get-article", help="Retrieve ScienceDirect article metadata or full text")
  p_art.add_argument(
      "--id-type",
      required=True,
      choices=["doi", "pii", "eid", "scopus_id", "pubmed_id"],
  )
  p_art.add_argument("--id", required=True, dest="identifier")
  p_art.add_argument("--view", default="META_ABS", choices=["META", "META_ABS", "FULL", "ENTITLED"])
  p_art.add_argument("--format", default="json", choices=["json", "xml", "text"])
  p_art.add_argument("--output", required=True, help="Output file path")

  p_ent = sub.add_parser("check-entitlement", help="Check full-text entitlement for a DOI")
  p_ent.add_argument("--doi", required=True, help="Article DOI")
  p_ent.add_argument("--output", required=True, help="Output JSON file path")

  return parser


def main() -> None:
  parser = build_parser()
  args = parser.parse_args()
  _safe_load_dotenv()
  api_key, insttoken = _get_credentials()
  limiter = _make_limiter_client()

  if args.command == "search-scopus":
    params: dict[str, Any] = {
        "query": args.query,
        "count": args.count,
        "view": args.view,
        "sort": args.sort,
        "date": args.date,
    }
    if args.cursor:
      params["cursor"] = args.cursor
    elif args.start is not None:
      params["start"] = args.start
    text, _ = _fetch(limiter, api_key, insttoken, "search/scopus", params=params)
    _write_output(json.loads(text), args.output, as_json=True)

  elif args.command == "search-sciencedirect":
    try:
      show_bucket = _sd_show_bucket(args.count)
    except ValueError as e:
      parser.error(str(e))
    payload: dict[str, Any] = {
        "qs": args.query,
        "display": {
            "offset": args.start,
            "show": show_bucket,
        },
    }
    if args.sort:
      payload["display"]["sortBy"] = args.sort
    if args.date:
      payload["date"] = args.date
    if args.open_access:
      payload["filters"] = {"openAccess": True}
    text, _ = _fetch(
        limiter,
        api_key,
        insttoken,
        "search/sciencedirect",
        method="PUT",
        json_body=payload,
    )
    data = json.loads(text)
    if (
        isinstance(data, dict)
        and isinstance(data.get("results"), list)
        and len(data["results"]) > args.count
    ):
      data["results"] = data["results"][: args.count]
    _write_output(data, args.output, as_json=True)

  elif args.command == "get-abstract":
    raw_id = (
        _normalize_doi(args.identifier)
        if args.id_type == "doi"
        else args.identifier.strip()
    )
    ident = urllib.parse.quote(raw_id, safe="/")
    text, _ = _fetch(
        limiter,
        api_key,
        insttoken,
        f"abstract/{args.id_type}/{ident}",
        params={"view": args.view},
    )
    _write_output(json.loads(text), args.output, as_json=True)

  elif args.command == "get-article":
    raw_id = (
        _normalize_doi(args.identifier)
        if args.id_type == "doi"
        else args.identifier.strip()
    )
    ident = urllib.parse.quote(raw_id, safe="/")
    accept = "application/json" if args.format == "json" else "application/xml"
    text, _ = _fetch(
        limiter,
        api_key,
        insttoken,
        f"article/{args.id_type}/{ident}",
        params={"view": args.view},
        accept=accept,
    )
    if args.format == "json":
      _write_output(json.loads(text), args.output, as_json=True)
    elif args.format == "xml":
      _write_output(text, args.output, as_json=False)
    else:
      _write_output(_xml_to_plain_text(text), args.output, as_json=False)

  elif args.command == "check-entitlement":
    ident = urllib.parse.quote(_normalize_doi(args.doi), safe="/")
    text, _ = _fetch(
        limiter, api_key, insttoken, f"article/entitlement/doi/{ident}"
    )
    _write_output(json.loads(text), args.output, as_json=True)


if __name__ == "__main__":
  main()
