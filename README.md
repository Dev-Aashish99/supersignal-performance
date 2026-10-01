# SuperSignal performance tracker

Reads the test-channel messages, classifies every trade with your rules, and serves
weekly/monthly tables (HTML, CSV, Excel).

## How data gets in
1. **Apps Script -> /ingest (recommended).** Your script already sends every signal and update
   through `idar_ka_udar_bot`. Run `patch_apps_script_v14.py` on your V13 script (see its header). It forwards
   each test-channel message (-1002940195231) to /ingest; URL and token live in Script Properties. Telegram never delivers a bot its own posts, and that bot already has a webhook,
   so the Apps Script copy is the reliable route. Do not delete the existing webhook.
2. **Backfill:** Telegram Desktop -> test channel -> Export chat history -> JSON, then
   `curl -X POST https://YOUR-APP/import-export -H "X-Token: $INGEST_TOKEN" -H "Content-Type: application/json" --data-binary @result.json`
   (or locally: `python import_telegram_export.py result.json`).
3. **Optional:** a *new* bot added as admin to the test channel can use `/webhook/telegram`
   (set the webhook with `secret_token=TG_WEBHOOK_SECRET`). Test that it sees your posts first.

## Run locally
    pip install -r requirements.txt
    INGEST_TOKEN=xxx VIEW_KEY=yyy uvicorn app:app --port 8770
    open http://127.0.0.1:8770/?key=yyy&period=2026-09      (weekly: period=2026-W40)

## Railway
Same pattern as the watcher: repo root has `Procfile`. Env vars: `INGEST_TOKEN`, `VIEW_KEY`,
`DB_PATH=/data/tracker.db` and **attach a volume at /data**, otherwise the database resets on redeploy
(raw messages can always be re-imported from an export).

## Rules (engine.py)
SL HIT = loss. TSL HIT > 0% = win. TSL HIT at 0% = excluded. Manual exit = excluded. INVALID or no update in 45 days
= dropped. Target hit but not exited by period end = provisional win at the LAST target %.
A trade is counted in the first period where it counts; a trade closing later is never counted twice.

## When a message is not understood
It goes to `/review` (and the report's review box). Fix the pattern in `msgparser.py`, then
`curl -X POST -H "X-Token: $INGEST_TOKEN" https://your-app/rebuild`. Nothing is lost because raw text is stored.
Corrections: `POST /api/manual-event {"symbol","date","kind","pct"}`.

## Tests
    python tests/test_engine.py     # replays your September report: 27/8/19, +12.0%
    python tests/test_pipeline.py   # export -> parser -> DB -> report
    python tests/test_real_formats.py  # messages exactly as your V13 script writes them
