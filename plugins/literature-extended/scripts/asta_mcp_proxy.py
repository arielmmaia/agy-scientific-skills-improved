#!/usr/bin/env python3
"""Stdio-to-Streamable-HTTP MCP proxy for Ai2 Asta Scientific Corpus Tool.

Reads ASTA_API_KEY (or fallback ASTA_TOOL_KEY) from project .env or ~/.env via
python-dotenv so zero secrets ever live in mcp_config.json.

Bridges newline-delimited JSON-RPC over stdio to Asta's stateless Streamable
HTTP endpoint (https://asta-tools.allen.ai/mcp/v1), handling both JSON and SSE
response bodies cleanly without opening a standalone GET SSE stream.
"""

# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "python-dotenv",
# ]
# ///

from __future__ import annotations

import gzip
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

ASTA_URL = "https://asta-tools.allen.ai/mcp/v1"
USER_AGENT = "antigravity-literature-extended/1.0"
TIMEOUT_SECS = 120.0

import dotenv  # noqa: E402


def _safe_load_dotenv() -> None:
  for path in (None, os.path.expanduser("~/.env")):
    try:
      if path is None:
        dotenv.load_dotenv()
      else:
        dotenv.load_dotenv(path)
    except OSError:
      pass


def _get_asta_key() -> str | None:
  return (
      os.environ.get("ASTA_API_KEY")
      or os.environ.get("ASTA_TOOL_KEY")
      or ""
  ).strip() or None


def _redact(text: str, secret: str | None) -> str:
  if secret and len(secret) >= 4:
    return text.replace(secret, "[REDACTED]")
  return text


def _decode_body(raw: bytes, headers: dict[str, str]) -> str:
  enc = ""
  for k, v in headers.items():
    if k.lower() == "content-encoding":
      enc = v.lower()
      break
  if enc in ("gzip", "x-gzip") or raw.startswith(b"\x1f\x8b"):
    try:
      raw = gzip.decompress(raw)
    except OSError:
      pass
  return raw.decode("utf-8", errors="replace")


def _extract_jsonrpc_messages(body: str, content_type: str) -> list[dict[str, Any]]:
  """Parses JSON-RPC payloads from either application/json or text/event-stream."""
  stripped = body.strip()
  if not stripped:
    return []

  if "text/event-stream" in content_type.lower() or stripped.startswith("event:") or stripped.startswith("data:"):
    messages: list[dict[str, Any]] = []
    data_lines: list[str] = []

    def _flush() -> None:
      if not data_lines:
        return
      payload = "\n".join(data_lines).strip()
      data_lines.clear()
      if not payload:
        return
      try:
        parsed = json.loads(payload)
      except json.JSONDecodeError:
        return
      if isinstance(parsed, dict):
        messages.append(parsed)
      elif isinstance(parsed, list):
        messages.extend(item for item in parsed if isinstance(item, dict))

    for line in body.splitlines():
      if line.startswith("data:"):
        data_lines.append(line[5:].lstrip())
      elif not line.strip():
        _flush()
    _flush()
    return messages

  try:
    parsed = json.loads(stripped)
  except json.JSONDecodeError:
    return []
  if isinstance(parsed, dict):
    return [parsed]
  if isinstance(parsed, list):
    return [item for item in parsed if isinstance(item, dict)]
  return []


def _emit(msg: dict[str, Any]) -> None:
  sys.stdout.write(json.dumps(msg, separators=(",", ":"), ensure_ascii=False) + "\n")
  sys.stdout.flush()


def _error_response(req_id: Any, code: int, message: str) -> dict[str, Any]:
  return {
      "jsonrpc": "2.0",
      "id": req_id,
      "error": {"code": code, "message": message},
  }


def _forward_request(
    msg: dict[str, Any],
    api_key: str | None,
    session_id: str | None,
) -> tuple[list[dict[str, Any]], str | None]:
  headers: dict[str, str] = {
      "Content-Type": "application/json",
      "Accept": "application/json, text/event-stream",
      "Accept-Encoding": "gzip",
      "User-Agent": USER_AGENT,
  }
  if api_key:
    headers["x-api-key"] = api_key
  if session_id:
    headers["Mcp-Session-Id"] = session_id

  req = urllib.request.Request(
      ASTA_URL,
      data=json.dumps(msg).encode("utf-8"),
      headers=headers,
      method="POST",
  )
  has_id = "id" in msg and msg["id"] is not None

  try:
    with urllib.request.urlopen(req, timeout=TIMEOUT_SECS) as resp:
      resp_headers = dict(resp.headers)
      new_session = session_id
      for k, v in resp_headers.items():
        if k.lower() == "mcp-session-id" and v:
          new_session = v
      content_type = ""
      for k, v in resp_headers.items():
        if k.lower() == "content-type":
          content_type = v
          break
      raw = resp.read()
      if resp.status == 202 or not raw:
        return [], new_session
      body = _decode_body(raw, resp_headers)
      return _extract_jsonrpc_messages(body, content_type), new_session

  except urllib.error.HTTPError as e:
    err_headers = dict(e.headers) if e.headers else {}
    err_body = _redact(_decode_body(e.read(), err_headers)[:400], api_key)
    hint = ""
    if e.code in (401, 403):
      hint = (
          " Ensure ASTA_API_KEY in ~/.env is a valid Ai2 Asta MCP key"
          " (separate from S2_API_KEY; request at"
          " https://share.hsforms.com/1L4hUh20oT3mu8iXJQMV77w3ioxm)."
      )
    err_msg = f"Asta MCP HTTP {e.code}:{hint} {err_body}".strip()
    print(f"[asta-mcp-proxy] {err_msg}", file=sys.stderr, flush=True)
    if has_id:
      return [_error_response(msg["id"], -32000, err_msg)], session_id
    return [], session_id

  except (urllib.error.URLError, OSError) as e:
    err_msg = f"Asta MCP network error: {_redact(str(e), api_key)}"
    print(f"[asta-mcp-proxy] {err_msg}", file=sys.stderr, flush=True)
    if has_id:
      return [_error_response(msg["id"], -32000, err_msg)], session_id
    return [], session_id


def main() -> None:
  _safe_load_dotenv()
  api_key = _get_asta_key()
  if not api_key:
    print(
        "[asta-mcp-proxy] Warning: ASTA_API_KEY is not set in ~/.env or"
        " project .env. Tool calls may be rate-limited or rejected with 403.",
        file=sys.stderr,
        flush=True,
    )

  session_id: str | None = None
  for raw_line in sys.stdin:
    line = raw_line.strip()
    if not line:
      continue
    try:
      msg = json.loads(line)
    except json.JSONDecodeError as e:
      print(f"[asta-mcp-proxy] Invalid JSON on stdin: {e}", file=sys.stderr, flush=True)
      continue

    if not isinstance(msg, dict):
      continue

    # Answer MCP ping locally without consuming remote API quota.
    if msg.get("method") == "ping" and "id" in msg:
      _emit({"jsonrpc": "2.0", "id": msg["id"], "result": {}})
      continue

    responses, session_id = _forward_request(msg, api_key, session_id)
    # Never write responses for JSON-RPC notifications (messages without id).
    if "id" in msg and msg["id"] is not None:
      for r in responses:
        _emit(r)


if __name__ == "__main__":
  main()
