"""
briefing_notify.py — Proactive desktop notification (Phase 3).

Standalone: generates (or reuses today's cached) briefing and shows a native
Windows toast with the day's objective. Runs WITHOUT the FastAPI server, so a
Windows Scheduled Task can fire it each morning even if the app is closed.

Usage:
    python briefing_notify.py            # generate + show toast
    python briefing_notify.py --print    # print briefing text only (no toast)

Schedule (one-time, idempotent) — created by register_briefing_task.ps1, or:
    schtasks /Create /TN "MyDay Morning Briefing" /SC DAILY /ST 08:30 ^
      /TR "C:\\MyDay\\.venv\\Scripts\\python.exe C:\\MyDay\\artifacts\\myday-python-api\\briefing_notify.py" /F
"""
import os
import subprocess
import sys
from pathlib import Path

# Console may be cp1252; make unicode (✦, emoji) printing safe.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE_DIR = Path(__file__).parent

# Load .env from repo root so ANTHROPIC_API_KEY / MS_* / DATABASE_URL are set.
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR.parent.parent / ".env")
except Exception:
    pass


def _build_briefing() -> dict:
    # Import here so .env is loaded first.
    from database import SessionLocal
    import agent
    db = SessionLocal()
    try:
        return agent.get_or_create_briefing(db)
    finally:
        db.close()


def _toast(title: str, body: str) -> bool:
    """Show a native Windows toast via PowerShell WinRT (no extra deps)."""
    ps = r"""
$ErrorActionPreference = 'Stop'
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null
[Windows.UI.Notifications.ToastNotification, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null
$tmpl = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$texts = $tmpl.GetElementsByTagName('text')
$texts.Item(0).AppendChild($tmpl.CreateTextNode($env:MDB_TITLE)) | Out-Null
$texts.Item(1).AppendChild($tmpl.CreateTextNode($env:MDB_BODY)) | Out-Null
$toast = [Windows.UI.Notifications.ToastNotification]::new($tmpl)
$appId = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId).Show($toast)
"""
    env = dict(os.environ, MDB_TITLE=title[:120], MDB_BODY=body[:250])
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            env=env, check=True, capture_output=True, timeout=30,
        )
        return True
    except Exception as exc:
        print(f"[toast failed] {exc}", file=sys.stderr)
        return False


def main():
    briefing = _build_briefing()
    if "error" in briefing:
        print(f"[briefing error] {briefing['error']}", file=sys.stderr)
        sys.exit(1)

    objective = briefing.get("objective") or briefing.get("headline") or "Revisa tu día en MyDay."
    n_stalls = len(briefing.get("stalls") or [])
    title = "✦ Tu objetivo de hoy"
    body = objective
    if n_stalls:
        body += f"\n⏳ {n_stalls} tarea(s) llevan mucho en tu plato — ciérralas."

    if "--print" in sys.argv:
        print("TITLE:", title)
        print("BODY:", body)
        print("HEADLINE:", briefing.get("headline"))
        return

    _toast(title, body)


if __name__ == "__main__":
    main()
