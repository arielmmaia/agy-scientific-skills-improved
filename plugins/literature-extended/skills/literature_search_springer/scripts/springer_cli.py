#!/usr/bin/env python3
"""Springer Nature API CLI (Meta API v2 & Open Access JSON/JATS XML).

Reads SPRINGER_META_API_KEY (for Meta v2) and SPRINGER_OA_API_KEY (for Open
Access) from ~/.env, falling back to SPRINGER_API_KEY if only one key is set.
Enforces cross-process rate limiting via polite-http.
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
import xml.etree.ElementTree as ET
from typing import Any

import dotenv
from polite_http import http_client

BASE_URL = "https://api.springernature.com/"
USER_AGENT = "antigravity-literature-extended/1.0"
_DOI_PREFIX_RE = re.compile(
    r"^(?:https?://(?:dx\.)?doi\.org/|doi\.org/|doi:\s*)", re.IGNORECASE
)

# Basic tier allows 100 req/min (~1.67/s); pace safely at 1.5 req/s.
_CLIENT = http_client.HttpClient(
    BASE_URL,
    qps=1.5,
    user_agent=USER_AGENT,
    max_retries=4,
    backoff_base=2.0,
    backoff_max=60.0,
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


def _get_api_key(primary_env: str) -> str:
  key = (
      os.environ.get(primary_env) or os.environ.get("SPRINGER_API_KEY") or ""
  ).strip()
  if not key:
    print(
        f"Error: {primary_env} (or fallback SPRINGER_API_KEY) is not set in"
        " ~/.env.\nRegister at https://dev.springernature.com/ and add it via"
        " the safe credentials protocol in the 'credentials' skill.",
        file=sys.stderr,
    )
    sys.exit(1)
  return key


def _fetch_endpoint(
    path: str,
    params: dict[str, Any],
    api_key: str,
    *,
    expect_json: bool = True,
) -> Any:
  # Keep api_key out of params dict so it is never logged accidentally.
  clean = {k: v for k, v in params.items() if v is not None and v != ""}
  query = urllib.parse.urlencode(clean)
  key_q = urllib.parse.urlencode({"api_key": api_key})
  full_path = f"{path}?{query}&{key_q}" if query else f"{path}?{key_q}"
  accept = "application/json" if expect_json else "application/xml"
  try:
    resp = _CLIENT.fetch(full_path, headers={"Accept": accept})
    return resp.json() if expect_json else resp.text
  except http_client.HttpError as e:
    # Redact api_key from any URL echoed in error messages.
    redacted = re.sub(r"(api_key=)[^&\s]+", r"\1REDACTED", str(e))
    print(
        f"Springer Nature API error (HTTP {e.status_code}): {redacted}",
        file=sys.stderr,
    )
    sys.exit(1)


def _extract_jats_articles(xml_text: str) -> list[ET.Element]:
  try:
    root = ET.fromstring(xml_text)
  except ET.ParseError as e:
    raise ValueError(f"Invalid JATS XML returned by Springer Nature: {e}") from e

  return [
      elem for elem in root.iter() if elem.tag.split("}")[-1].lower() == "article"
  ]


def _jats_to_plain_text(xml_text: str) -> str:
  articles = _extract_jats_articles(xml_text)
  if not articles:
    raise LookupError(
        "No Open Access JATS <article> records found in Springer Nature response."
    )

  def _walk(node: ET.Element, out: list[str]) -> None:
    tag = node.tag.split("}")[-1].lower()
    if tag in ("ref-list", "back"):
      return
    if tag in ("article-title", "title"):
      t = " ".join("".join(node.itertext()).split())
      if t:
        out.append(f"## {t}")
      return
    if tag == "p":
      t = " ".join("".join(node.itertext()).split())
      if t:
        out.append(t)
      return
    for child in node:
      _walk(child, out)

  rendered_articles: list[str] = []
  for art in articles:
    lines: list[str] = []
    _walk(art, lines)
    if lines:
      rendered_articles.append("\n\n".join(lines))

  if not rendered_articles:
    raise LookupError(
        "Open Access JATS <article> records contained no extractable body text."
    )
  return "\n\n---\n\n".join(rendered_articles)


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
      description="Springer Nature Meta API v2 & Open Access API CLI"
  )
  sub = parser.add_subparsers(dest="command", required=True)

  p_meta = sub.add_parser("meta-search", help="Search Springer Nature Meta API v2 (JSON)")
  p_meta.add_argument("--query", required=True, help="Query string with Springer constraints")
  p_meta.add_argument("--start", type=int, default=1, help="1-indexed start offset (default 1)")
  p_meta.add_argument("--limit", type=int, required=True, help="Records per page (p=, 1-100)")
  p_meta.add_argument("--output", required=True, help="Output JSON file path")

  p_doi = sub.add_parser("meta-doi", help="Look up a single DOI via Meta API v2")
  p_doi.add_argument("--doi", required=True, help="DOI string (with or without doi.org/ or DOI: prefix)")
  p_doi.add_argument("--output", required=True, help="Output JSON file path")

  p_oa = sub.add_parser("oa-search", help="Search Springer Nature Open Access metadata (JSON)")
  p_oa.add_argument("--query", required=True, help="Query string with Springer constraints")
  p_oa.add_argument("--start", type=int, default=1, help="1-indexed start offset (default 1)")
  p_oa.add_argument("--limit", type=int, required=True, help="Records per page (p=, 1-100)")
  p_oa.add_argument("--output", required=True, help="Output JSON file path")

  p_jats = sub.add_parser("oa-fulltext", help="Fetch Open Access full text via /openaccess/jats")
  group = p_jats.add_mutually_exclusive_group(required=True)
  group.add_argument("--doi", help="Exact DOI of an Open Access Springer Nature article")
  group.add_argument("--query", help="Search query to fetch matching OA full-text articles")
  p_jats.add_argument("--start", type=int, default=1, help="1-indexed start offset (default 1)")
  p_jats.add_argument(
      "--limit",
      type=int,
      help="Records per page (default 1 for --doi; required 1-20 for --query)",
  )
  p_jats.add_argument("--format", default="text", choices=["text", "xml"])
  p_jats.add_argument("--output", required=True, help="Output file path (.txt or .xml)")

  return parser


def main() -> None:
  parser = build_parser()
  args = parser.parse_args()
  _safe_load_dotenv()

  if args.command == "meta-search":
    key = _get_api_key("SPRINGER_META_API_KEY")
    data = _fetch_endpoint(
        "meta/v2/json",
        {"q": args.query, "s": args.start, "p": args.limit},
        key,
        expect_json=True,
    )
    _write_output(data, args.output, as_json=True)

  elif args.command == "meta-doi":
    key = _get_api_key("SPRINGER_META_API_KEY")
    doi_clean = _normalize_doi(args.doi)
    data = _fetch_endpoint(
        "meta/v2/json",
        {"q": f"doi:{doi_clean}", "s": 1, "p": 1},
        key,
        expect_json=True,
    )
    _write_output(data, args.output, as_json=True)

  elif args.command == "oa-search":
    key = _get_api_key("SPRINGER_OA_API_KEY")
    data = _fetch_endpoint(
        "openaccess/json",
        {"q": args.query, "s": args.start, "p": args.limit},
        key,
        expect_json=True,
    )
    _write_output(data, args.output, as_json=True)

  elif args.command == "oa-fulltext":
    key = _get_api_key("SPRINGER_OA_API_KEY")
    if args.doi:
      q = f"doi:{_normalize_doi(args.doi)}"
      limit = args.limit or 1
    else:
      if args.limit is None:
        parser.error("--limit is required when using --query with oa-fulltext (recommended 1-20).")
      q = args.query
      limit = args.limit
    xml_text = _fetch_endpoint(
        "openaccess/jats",
        {"q": q, "s": args.start, "p": limit},
        key,
        expect_json=False,
    )
    try:
      articles = _extract_jats_articles(xml_text)
      if not articles:
        print(
            f"Error: No Open Access JATS full-text articles found for query"
            f" {q!r}. The article may be closed-access or absent from the"
            " Springer Nature Open Access corpus.",
            file=sys.stderr,
        )
        sys.exit(1)
      if args.format == "xml":
        _write_output(xml_text, args.output, as_json=False)
      else:
        _write_output(_jats_to_plain_text(xml_text), args.output, as_json=False)
    except (ValueError, LookupError) as e:
      print(f"Error: {e}", file=sys.stderr)
      sys.exit(1)


if __name__ == "__main__":
  main()
