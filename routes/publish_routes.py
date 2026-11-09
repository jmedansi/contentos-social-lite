import os
import json
import logging
from typing import Optional
from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from services.db import execute_query, execute_insert
from services.social_service import publish_direct, SocialPublishError

logger = logging.getLogger("publish_routes")
router = APIRouter(prefix="/publish", tags=["Publication"])

@router.post("/direct")
def publish_post_direct(
    account_id: int = Form(...),
    message: str = Form(...),
    media_url: Optional[str] = Form(None)
):
    """Effectue la publication directe et synchrone sans aucune file d'attente ni planification."""
    accounts = execute_query("SELECT * FROM social_accounts WHERE id = ? AND is_active = 1", (account_id,))
    if not accounts:
        raise HTTPException(status_code=404, detail="Compte social introuvable ou inactif.")

    account = accounts[0]
    message = (message or "").strip()
    if not message and not media_url:
        raise HTTPException(status_code=400, detail="Veuillez fournir au moins un message ou un média.")

    try:
        result = publish_direct(account, message=message, media_url=media_url)
        remote_id = result.get("remote_id")

        # Enregistrer dans l'historique
        execute_insert(
            """INSERT INTO social_publications (account_id, platform, message, media_url, remote_post_id, status)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (account_id, account["platform"], message, media_url, remote_id, "published")
        )
        return RedirectResponse(url="/?published=success", status_code=303)

    except SocialPublishError as e:
        execute_insert(
            """INSERT INTO social_publications (account_id, platform, message, media_url, status, error_detail)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (account_id, account["platform"], message, media_url, "failed", str(e))
        )
        return JSONResponse({"ok": False, "error": str(e), "detail": getattr(e, 'detail', '')}, status_code=400)
    except Exception as e:
        logger.exception("Erreur inattendue lors de la publication directe")
        return JSONResponse({"ok": False, "error": f"Erreur serveur: {str(e)}"}, status_code=500)
