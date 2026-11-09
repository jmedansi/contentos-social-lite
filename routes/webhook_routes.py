import os
import json
import logging
from typing import Optional
from fastapi import APIRouter, Request, Response, HTTPException
from services.db import execute_insert, execute_query

logger = logging.getLogger("webhook_routes")
router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

META_VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN", "contentos_secret_token_123")

# ----------------- META WEBHOOK (Instagram & Facebook) -----------------
@router.get("/meta")
def verify_meta_webhook(request: Request):
    """Validation de l'URL par Meta (challenge)."""
    params = request.query_params
    hub_mode = params.get("hub.mode")
    hub_challenge = params.get("hub.challenge")
    hub_verify_token = params.get("hub.verify_token")

    if hub_mode == "subscribe" and hub_verify_token == META_VERIFY_TOKEN:
        logger.info("Webhook Meta vérifié avec succès.")
        return Response(content=hub_challenge, media_type="text/plain")

    raise HTTPException(status_code=403, detail="Verification token invalide.")

@router.post("/meta")
async def receive_meta_webhook(request: Request):
    """Réception des événements Meta (Commentaires, DM Messenger, DM Instagram)."""
    try:
        body = await request.json()
    except Exception:
        body = {}

    execute_insert(
        """INSERT INTO webhook_logs (platform, event_type, payload) VALUES (?, ?, ?)""",
        ("meta", body.get("object", "unknown"), json.dumps(body))
    )

    # Analyse des événements entrants
    entries = body.get("entry", [])
    for entry in entries:
        # Événements Instagram / Page messaging
        messaging_events = entry.get("messaging", [])
        for event in messaging_events:
            sender_id = event.get("sender", {}).get("id")
            recipient_id = event.get("recipient", {}).get("id")
            message_obj = event.get("message", {})
            text = message_obj.get("text")
            mid = message_obj.get("mid")

            if text and sender_id:
                execute_insert(
                    """INSERT INTO inbox_messages (platform, thread_id, sender_id, recipient_id, remote_id, content, message_type)
                       VALUES (?, ?, ?, ?, ?, ?, 'dm')""",
                    ("instagram" if "instagram" in body.get("object", "") else "facebook",
                     sender_id, sender_id, recipient_id, mid, text)
                )

        # Événements Changements de Feed (Commentaires Facebook/Instagram)
        changes = entry.get("changes", [])
        for change in changes:
            field = change.get("field")
            val = change.get("value", {})
            if field in ("comments", "feed"):
                comment_id = val.get("comment_id") or val.get("id")
                msg = val.get("message") or val.get("text")
                sender = val.get("from", {})
                post_id = val.get("post_id")

                if msg:
                    execute_insert(
                        """INSERT INTO inbox_messages (platform, sender_id, sender_name, thread_id, remote_id, parent_id, content, message_type)
                           VALUES (?, ?, ?, ?, ?, ?, ?, 'comment')""",
                        ("instagram" if "instagram" in body.get("object", "") else "facebook",
                         sender.get("id"), sender.get("name"), post_id, comment_id, post_id, msg)
                    )

    return {"status": "ok"}

# ----------------- TIKTOK / LINKEDIN WEBHOOKS -----------------
@router.post("/generic/{platform}")
async def generic_webhook(platform: str, request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}

    execute_insert(
        """INSERT INTO webhook_logs (platform, event_type, payload) VALUES (?, ?, ?)""",
        (platform, "incoming", json.dumps(body))
    )
    return {"status": "received"}
