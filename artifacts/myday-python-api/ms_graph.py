"""
ms_graph.py — Microsoft 365 connector (Phase 2: Outlook + Calendar via Graph).

Auth: OAuth 2.0 device-code flow with a public client (no secret stored). The
flow runs in a background thread so the web UI can show the code + link and poll
for completion. Tokens are cached to disk (msal SerializableTokenCache) so
re-auth isn't needed across restarts; silent refresh is used afterwards.

Confidentiality (V2A): metadata-only by default. Email bodies are stored LOCALLY
in InboxItem.raw_content; what the agent sends to Claude is metadata (subject,
sender, time) unless the user explicitly asks to read a body.

Setup required (ask IT / Azure Entra ID):
- Register an app (or reuse one) → get the Application (client) ID and Tenant ID.
- Enable "Allow public client flows" (mobile & desktop / device code).
- Delegated permissions: Mail.Read, Calendars.Read (offline_access for refresh).
"""
import os
import threading
from datetime import datetime, date, timedelta, timezone
from typing import Optional

import msal
import requests

GRAPH = "https://graph.microsoft.com/v1.0"

# Delegated scopes. Calendars.Read self-consents in the V2A tenant (TimeTracker
# proves it). Mail.Read requires ADMIN approval in this tenant, so it's left out
# by default — add it back via MS_SCOPES once IT/admin grants it:
#   MS_SCOPES="Calendars.Read Mail.Read"
# offline_access / openid / profile are added automatically by msal.
SCOPES = (os.environ.get("MS_SCOPES") or "Calendars.Read").split()


def mail_enabled() -> bool:
    return "Mail.Read" in SCOPES

_CACHE_PATH = os.path.join(os.path.dirname(__file__), ".ms_token_cache.json")

# Module-global state for the pending device-code flow (single-user, local).
_pending_flow: Optional[dict] = None
_flow_error: Optional[str] = None
_flow_lock = threading.Lock()


# ─── Config ───────────────────────────────────────────────────────────────────

def client_id() -> Optional[str]:
    return os.environ.get("MS_CLIENT_ID") or None


def tenant() -> str:
    # "organizations" works for any work/school account; override with the V2A
    # tenant GUID or domain for stricter scoping.
    return os.environ.get("MS_TENANT_ID") or "organizations"


def authority() -> str:
    return f"https://login.microsoftonline.com/{tenant()}"


def is_configured() -> bool:
    return bool(client_id())


# ─── Token cache ───────────────────────────────────────────────────────────────

def _load_cache() -> msal.SerializableTokenCache:
    """Load tokens. Prefers DPAPI-encrypted format (only the current Windows
    user can decrypt); falls back to legacy plaintext. Mirrors TimeTracker."""
    cache = msal.SerializableTokenCache()
    if not os.path.exists(_CACHE_PATH):
        return cache
    try:
        from msal_extensions import FilePersistenceWithDataProtection
        cache.deserialize(FilePersistenceWithDataProtection(_CACHE_PATH).load())
        return cache
    except Exception:
        pass
    try:
        with open(_CACHE_PATH, "r", encoding="utf-8") as f:
            cache.deserialize(f.read())
    except Exception:
        pass
    return cache


def _save_cache(cache: msal.SerializableTokenCache) -> None:
    """Persist cache, encrypting with Windows DPAPI when available."""
    if not cache.has_state_changed:
        return
    try:
        from msal_extensions import FilePersistenceWithDataProtection
        FilePersistenceWithDataProtection(_CACHE_PATH).save(cache.serialize())
    except Exception:
        try:
            with open(_CACHE_PATH, "w", encoding="utf-8") as f:
                f.write(cache.serialize())
        except Exception:
            pass


def _build_app(cache: msal.SerializableTokenCache) -> msal.PublicClientApplication:
    return msal.PublicClientApplication(
        client_id(), authority=authority(), token_cache=cache
    )


# ─── Auth state ────────────────────────────────────────────────────────────────

def is_connected() -> bool:
    """True if we have a cached account we can get a token for silently."""
    if not is_configured():
        return False
    cache = _load_cache()
    app = _build_app(cache)
    accounts = app.get_accounts()
    if not accounts:
        return False
    result = app.acquire_token_silent(SCOPES, account=accounts[0])
    _save_cache(cache)
    return bool(result and "access_token" in result)


def connected_account() -> Optional[str]:
    if not is_configured():
        return None
    app = _build_app(_load_cache())
    accounts = app.get_accounts()
    return accounts[0].get("username") if accounts else None


def _get_token() -> Optional[str]:
    """Silently acquire an access token from cache (refresh if needed)."""
    if not is_configured():
        return None
    cache = _load_cache()
    app = _build_app(cache)
    accounts = app.get_accounts()
    if not accounts:
        return None
    result = app.acquire_token_silent(SCOPES, account=accounts[0])
    _save_cache(cache)
    if result and "access_token" in result:
        return result["access_token"]
    return None


# ─── Device-code flow (interactive sign-in) ─────────────────────────────────────

def start_device_flow() -> dict:
    """Begin the device-code flow. Returns {user_code, verification_uri, message}.
    Completes auth in a background thread; poll is_connected() to detect success."""
    global _pending_flow, _flow_error
    if not is_configured():
        return {"error": "MS_CLIENT_ID no está configurado en .env."}

    with _flow_lock:
        _flow_error = None
        cache = _load_cache()
        app = _build_app(cache)
        flow = app.initiate_device_flow(scopes=SCOPES)
        if "user_code" not in flow:
            return {"error": flow.get("error_description", "No se pudo iniciar el device flow.")}
        _pending_flow = flow

        def _complete():
            global _flow_error
            try:
                result = app.acquire_token_by_device_flow(flow)  # blocks until done/expired
                if "access_token" not in result:
                    _flow_error = result.get("error_description", "Autenticación fallida.")
                _save_cache(cache)
            except Exception as exc:
                _flow_error = str(exc)

        threading.Thread(target=_complete, daemon=True).start()
        return {
            "user_code": flow["user_code"],
            "verification_uri": flow.get("verification_uri"),
            "message": flow.get("message"),
        }


def flow_status() -> dict:
    return {
        "configured": is_configured(),
        "connected": is_connected(),
        "account": connected_account(),
        "error": _flow_error,
        "pending": _pending_flow is not None and not is_connected() and _flow_error is None,
    }


def disconnect() -> None:
    """Forget the account: clear the cache file."""
    global _pending_flow, _flow_error
    _pending_flow = None
    _flow_error = None
    try:
        if os.path.exists(_CACHE_PATH):
            os.remove(_CACHE_PATH)
    except Exception:
        pass


# ─── Graph calls ─────────────────────────────────────────────────────────────

def _graph_get(path: str, params: Optional[dict] = None) -> dict:
    token = _get_token()
    if not token:
        raise RuntimeError("No conectado a Microsoft 365.")
    resp = requests.get(
        f"{GRAPH}{path}",
        headers={"Authorization": f"Bearer {token}"},
        params=params or {},
        timeout=25,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Graph error {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def _fmt_dt(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).isoformat()
    except Exception:
        return s


def get_calendar_events(days: int = 1) -> list:
    """Today's (and next `days`) events. Metadata only — safe to send to Claude."""
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=days)
    data = _graph_get(
        "/me/calendarView",
        {
            "startDateTime": now.isoformat(),
            "endDateTime": end.isoformat(),
            "$select": "subject,start,end,location,isAllDay,organizer,attendees,onlineMeeting,showAs",
            "$orderby": "start/dateTime",
            "$top": "50",
        },
    )
    events = []
    for e in data.get("value", []):
        org = (e.get("organizer") or {}).get("emailAddress", {}).get("name")
        events.append({
            "subject": e.get("subject") or "(sin título)",
            "start": _fmt_dt((e.get("start") or {}).get("dateTime")),
            "end": _fmt_dt((e.get("end") or {}).get("dateTime")),
            "location": (e.get("location") or {}).get("displayName"),
            "is_all_day": e.get("isAllDay", False),
            "organizer": org,
            "attendee_count": len(e.get("attendees") or []),
            "is_online": bool(e.get("onlineMeeting")),
            "show_as": e.get("showAs"),
        })
    return events


def get_messages(top: int = 25, unread_only: bool = False) -> list:
    """Recent inbox messages. Returns metadata + body (body kept local on store)."""
    params = {
        "$select": "id,subject,from,receivedDateTime,bodyPreview,body,isRead,webLink,hasAttachments",
        "$orderby": "receivedDateTime desc",
        "$top": str(top),
    }
    if unread_only:
        params["$filter"] = "isRead eq false"
    data = _graph_get("/me/mailFolders/inbox/messages", params)
    msgs = []
    for m in data.get("value", []):
        frm = (m.get("from") or {}).get("emailAddress", {})
        msgs.append({
            "id": m.get("id"),
            "subject": m.get("subject") or "(sin asunto)",
            "from_name": frm.get("name"),
            "from_address": frm.get("address"),
            "received": _fmt_dt(m.get("receivedDateTime")),
            "preview": m.get("bodyPreview"),
            "body": (m.get("body") or {}).get("content"),
            "body_type": (m.get("body") or {}).get("contentType"),
            "is_read": m.get("isRead", False),
            "web_link": m.get("webLink"),
            "has_attachments": m.get("hasAttachments", False),
        })
    return msgs


# ─── Normalization → InboxItem (email triage) ──────────────────────────────────

def email_to_inbox_fields(msg: dict) -> dict:
    """Convert a Graph message into InboxItem kwargs. Metadata-only summary;
    full body stored LOCALLY in raw_content (never auto-sent to Claude)."""
    sender = msg.get("from_name") or msg.get("from_address") or "desconocido"
    received = msg.get("received") or ""
    summary = f"De: {sender} · {received[:16].replace('T', ' ')}"  # metadata only
    return {
        "source": "ms_email",
        "source_type": "email",
        "external_id": msg.get("id"),
        "title": msg.get("subject") or "(sin asunto)",
        "raw_content": msg.get("body") or msg.get("preview"),  # local only
        "summary": summary,
        "suggested_actions_json": "[]",
        "linked_note_url": msg.get("web_link"),
        "status": "new",
        "created_at": _parse_received(received),
    }


def _parse_received(s: str) -> datetime:
    if not s:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return datetime.utcnow()
