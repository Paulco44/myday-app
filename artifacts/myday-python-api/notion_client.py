"""
notion_client.py — Lightweight Notion REST wrapper (stdlib urllib, no extra deps).

All normalization logic lives here so webhook-based sync can later call the
same normalize_page / normalize_database_entry functions directly.
"""
import json
import os
import urllib.request
import urllib.error
from datetime import datetime
from typing import Optional

NOTION_VERSION = "2022-06-28"
NOTION_BASE = "https://api.notionhq.com/v1"


# ─── Token ───────────────────────────────────────────────────────────────────

def get_token() -> Optional[str]:
    return os.environ.get("NOTION_API_TOKEN") or None


def is_configured() -> bool:
    return bool(get_token())


# ─── HTTP helpers ─────────────────────────────────────────────────────────────

def _headers() -> dict:
    token = get_token()
    if not token:
        raise RuntimeError("NOTION_API_TOKEN is not configured.")
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _request(method: str, path: str, body: Optional[dict] = None) -> dict:
    url = f"{NOTION_BASE}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=_headers(), method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"Notion API error {e.code}: {detail}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Notion connection error: {e.reason}")


# ─── Text extraction helpers ──────────────────────────────────────────────────

def _plain_text(rich_text_list: list) -> str:
    return "".join(item.get("plain_text", "") for item in (rich_text_list or []))


def _page_title(page: dict) -> str:
    props = page.get("properties", {})
    # Look for the title-type property first
    for prop in props.values():
        if prop.get("type") == "title":
            return _plain_text(prop.get("title", [])).strip()
    # Fallback: check "Name" key
    if "Name" in props:
        return _plain_text(props["Name"].get("title", [])).strip()
    return ""


def _blocks_to_text(blocks: list) -> str:
    """Recursively flatten block rich_text to plain text, one block per line."""
    lines = []
    for block in blocks:
        btype = block.get("type", "")
        content = block.get(btype, {})
        rt = content.get("rich_text", [])
        text = _plain_text(rt).strip()
        if text:
            lines.append(text)
        # Handle simple nested children (one level)
        children = block.get("children", [])
        if children:
            lines.extend(_blocks_to_text(children))
    return "\n".join(lines)


def _summary_from_raw(raw: str, max_chars: int = 250) -> Optional[str]:
    if not raw:
        return None
    raw = raw.strip()
    if len(raw) <= max_chars:
        return raw
    truncated = raw[:max_chars].rsplit(" ", 1)[0]
    return truncated + "…"


def _parse_notion_time(ts: str) -> datetime:
    if not ts:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return datetime.utcnow()


# ─── API calls ────────────────────────────────────────────────────────────────

def fetch_page(page_id: str) -> dict:
    """Fetch a single Notion page's metadata."""
    return _request("GET", f"/pages/{page_id.replace('-', '')}")


def fetch_block_children(block_id: str) -> list:
    """Fetch top-level block children for a page or block."""
    clean_id = block_id.replace("-", "")
    resp = _request("GET", f"/blocks/{clean_id}/children?page_size=100")
    return resp.get("results", [])


def query_database(database_id: str, page_size: int = 25) -> list:
    """Return up to page_size entries from a Notion database."""
    clean_id = database_id.replace("-", "")
    resp = _request("POST", f"/databases/{clean_id}/query", {"page_size": page_size})
    return resp.get("results", [])


# ─── Normalization (canonical path — reuse for webhooks) ─────────────────────

def normalize_page(page: dict, blocks: Optional[list] = None) -> dict:
    """
    Convert a Notion page object + its blocks into an InboxItem field dict.
    This is the single canonical normalization function.
    Webhook-based sync should call this too.

    Returns a dict ready to pass as **kwargs to models.InboxItem().
    """
    raw = _blocks_to_text(blocks or [])
    title = _page_title(page) or "Untitled Notion page"
    url = page.get("url") or ""
    created_at = _parse_notion_time(page.get("created_time", ""))

    return {
        "source": "notion",
        "source_type": "page",
        "external_id": page.get("id", "").replace("-", ""),
        "title": title,
        "raw_content": raw or None,
        "summary": _summary_from_raw(raw),
        "suggested_actions_json": "[]",
        "linked_note_url": url or None,
        "status": "new",
        "created_at": created_at,
    }


def normalize_database_entry(page: dict, blocks: Optional[list] = None) -> dict:
    """Same as normalize_page but marks source_type as 'database_entry'."""
    result = normalize_page(page, blocks)
    result["source_type"] = "database_entry"
    return result


# ─── High-level import helpers (called from routes) ──────────────────────────

def import_page(page_id: str) -> dict:
    """Fetch a Notion page + its blocks. Returns normalized InboxItem dict."""
    page = fetch_page(page_id)
    blocks = fetch_block_children(page_id)
    return normalize_page(page, blocks)


def import_database_entries(database_id: str, page_size: int = 25) -> list[dict]:
    """
    Fetch all entries from a Notion database.
    Returns a list of normalized InboxItem dicts (blocks fetched per-entry).
    """
    entries = query_database(database_id, page_size)
    results = []
    for page in entries:
        pid = page.get("id", "").replace("-", "")
        try:
            blocks = fetch_block_children(pid)
        except Exception:
            blocks = []
        results.append(normalize_database_entry(page, blocks))
    return results
