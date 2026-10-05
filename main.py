import logging
import os
import secrets

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from strava import get_activity, update_activity

logger = logging.getLogger(__name__)
app = FastAPI(title="Strava Activity Renamer")


class StravaWebhookEvent(BaseModel):
    object_type: str
    aspect_type: str
    object_id: int = Field(gt=0)


def generate_name(activity: dict[str, object]) -> str:
    """Temporary naming policy; replace with activity analysis when ready."""
    return f"AI-named activity {activity['id']} (placeholder)"


def rename_activity(activity_id: int) -> None:
    activity = get_activity(activity_id)
    new_name = generate_name(activity)
    update_activity(activity_id, new_name)
    logger.info("Renamed Strava activity %s", activity_id)


@app.get("/strava/webhook")
async def verify_strava_webhook(
    mode: str = Query(alias="hub.mode"),
    verify_token: str = Query(alias="hub.verify_token"),
    challenge: str = Query(alias="hub.challenge"),
) -> dict[str, str]:
    expected_token = os.environ.get("STRAVA_WEBHOOK_VERIFY_TOKEN")
    if not expected_token:
        raise HTTPException(
            status_code=500,
            detail="STRAVA_WEBHOOK_VERIFY_TOKEN is not configured",
        )
    if mode != "subscribe" or not secrets.compare_digest(
        verify_token, expected_token
    ):
        raise HTTPException(status_code=403, detail="Webhook verification failed")

    return {"hub.challenge": challenge}


@app.post("/strava/webhook")
async def strava_webhook(
    event: StravaWebhookEvent,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    if event.object_type == "activity" and event.aspect_type == "create":
        background_tasks.add_task(rename_activity, event.object_id)
        return {"status": "accepted"}

    return {"status": "ignored"}
