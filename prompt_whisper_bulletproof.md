# Prompt para Claude Code: Auto-POST Bulletproof en Whisper App

Pega esto en Claude Code dentro de tu repo de la Whisper app:

---

> I need to make the auto-POST from my Whisper app to MyDay more reliable and give clear visual feedback.
>
> ## Context
>
> My Whisper app already has:
> - `post_to_myday(payload)` function that reads `MYDAY_URL` and `MYDAY_SEND_TO_MYDAY` env vars
> - `send_to_myday(url, payload)` that does a single HTTP POST
> - The function runs after each recording is processed
> - It logs `[MyDay] OK ...` or `[MyDay] FAIL ...` to console
>
> The MyDay endpoint is:
> ```
> POST {MYDAY_URL}/task-manager/inbox/ingest/whisper
> Content-Type: application/json
> ```
>
> ## What I need you to change
>
> ### 1. Add retry with exponential backoff
>
> When `send_to_myday()` fails (network error, timeout, non-2xx response), retry up to 3 times with delays:
> - Attempt 1: immediate
> - Attempt 2: wait 2 seconds
> - Attempt 3: wait 5 seconds
>
> After all 3 attempts fail, save the payload to a local file `failed_sends/` folder with timestamp filename, so I can manually retry later.
>
> Use a simple loop with `time.sleep()` — do NOT add a dependency like `tenacity` or `backoff`.
>
> ### 2. Add a timeout to the HTTP request
>
> Set `timeout=15` on the `requests.post()` call (15 seconds). If the server is down, I don't want the app to hang indefinitely.
>
> ### 3. Visual feedback in the UI
>
> After the POST completes (success or failure), update the Whisper app UI to show:
> - **Success**: A small green label or status text: "✓ Sent to MyDay" that appears near the save/extract area. It should appear for 8 seconds then fade out.
> - **Failure**: A small red label: "✕ MyDay send failed — saved locally" with a path to the failed JSON file. This stays visible until the user dismisses it or starts a new recording.
> - **Disabled**: If `MYDAY_SEND_TO_MYDAY` is false or `MYDAY_URL` is not set, show a subtle gray label: "MyDay auto-send: off"
>
> Implement this as a simple label widget update (I believe the UI is built with Gradio or Tkinter — check and adapt to whichever framework is in use).
>
> ### 4. Failed sends recovery
>
> Add a small utility function `retry_failed_sends()` that:
> - Scans `failed_sends/` folder for `.json` files
> - Tries to POST each one to MyDay
> - On success, moves the file to `failed_sends/sent/`
> - On failure, leaves it in place
>
> This function should be callable from the UI (a small "Retry failed" button, only visible when there are files in `failed_sends/`). Or optionally, run it automatically at app startup.
>
> ### 5. Keep it clean
>
> - Do NOT change the payload structure or the endpoint URL
> - Do NOT add new dependencies (use only `requests`, `time`, `os`, `json`, `pathlib` which should already be available)
> - Keep the retry logic in a single, testable helper function
> - Log every attempt to console with `[MyDay]` prefix for easy debugging
>
> ### Summary of behavior after changes
>
> 1. User records → Whisper processes → saves JSON + MD locally
> 2. `post_to_myday()` runs with 3 retry attempts
> 3. If success → green "✓ Sent to MyDay" label in UI
> 4. If all retries fail → save to `failed_sends/` → red error label in UI
> 5. At next app startup (or manual button click) → `retry_failed_sends()` processes the queue
> 6. Nothing ever gets lost — local files are always saved first

---
