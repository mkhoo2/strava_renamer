# Strava Activity Renamer

This FastAPI service verifies Strava webhook subscriptions and renames each newly
created activity to `AI-named activity (placeholder)`. The naming function is
deliberately simple so it can later be replaced with activity-statistics analysis
and AI-generated names.

## Configure and run

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Set the Strava application credentials and webhook verification token in the
service environment. The refresh token must belong to the Strava athlete who
authorized the app with `activity:read` and `activity:write` scopes.

```powershell
$env:STRAVA_CLIENT_ID = "your-client-id"
$env:STRAVA_CLIENT_SECRET = "your-client-secret"
$env:STRAVA_REFRESH_TOKEN = "your-initial-refresh-token"
$env:STRAVA_WEBHOOK_VERIFY_TOKEN = "a-random-verification-token"
uvicorn main:app --host 0.0.0.0 --port 8000
```

The service stores the latest access and rotated refresh tokens in
`~/.strava_bot/tokens.sqlite3` and refreshes access tokens automatically.
Set `STRAVA_TOKEN_DB` to use a different database path. Keep this database
private and persistent across restarts.

## Register the webhook

Deploy the service at a publicly reachable HTTPS URL, then create a Strava
webhook subscription with callback URL
`https://your-host/strava/webhook` and the same verification token configured in
`STRAVA_WEBHOOK_VERIFY_TOKEN`. Strava's subscription verification request is
handled by `GET /strava/webhook`; new activity events are handled by
`POST /strava/webhook`.

Activity renaming runs as an in-process background task so the webhook can be
acknowledged promptly. Use a durable job queue if activity events must survive
service restarts or be retried after processing failures.
