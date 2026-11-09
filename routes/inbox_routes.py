import logging
from typing import Optional
from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from services.db import execute_query, execute_insert
from services.social_service import reply_to_comment, send_social_dm, SocialPublishError

logger = logging.getLogger("inbox_routes")
router = APIRouter(prefix="/inbox", tags=["Inbox"])

@router.get("/conversations")
def get_conversations():
    """Liste tous les messages et commentaires reçus ordonnés du plus récent au plus ancien."""
    messages = execute_query(
        """SELECT m.*, a.account_name, a.platform as account_platform 
           FROM inbox_messages m
           LEFT JOIN social_accounts a ON m.account_id = a.id
           ORDER BY m.created_at DESC LIMIT 100"""
    )
    return {"ok": True, "messages": messages}

@router.post("/reply/comment")
def reply_comment(
    message_id: int = Form(...),
    reply_text: str = Form(...)
):
    """Réponse manuelle à un commentaire."""
    records = execute_query("SELECT * FROM inbox_messages WHERE id = ?", (message_id,))
    if not records:
        raise HTTPException(status_code=404, detail="Message ou commentaire introuvable.")

    msg = records[0]
    remote_comment_id = msg.get("remote_id")
    account_id = msg.get("account_id")

    accounts = execute_query("SELECT * FROM social_accounts WHERE id = ?", (account_id,))
    if not accounts:
        # Essayer de trouver un compte pour la même plateforme
        accounts = execute_query("SELECT * FROM social_accounts WHERE platform = ? LIMIT 1", (msg.get("platform"),))
        if not accounts:
            raise HTTPException(status_code=400, detail="Aucun compte social configuré pour répondre à ce commentaire.")

    account = accounts[0]

    try:
        res = reply_to_comment(account, comment_id=remote_comment_id, message=reply_text)
        # Enregistrer la réponse
        execute_insert(
            """INSERT INTO inbox_messages (platform, account_id, thread_id, parent_id, content, is_from_me, message_type)
               VALUES (?, ?, ?, ?, ?, 1, 'comment')""",
            (account["platform"], account["id"], msg.get("thread_id"), remote_comment_id, reply_text)
        )
        return RedirectResponse(url="/#inbox", status_code=303)
    except SocialPublishError as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)

@router.post("/reply/dm")
def reply_dm(
    recipient_id: str = Form(...),
    platform: str = Form(...),
    reply_text: str = Form(...),
    account_id: Optional[int] = Form(None)
):
    """Envoi manuel d'un DM."""
    if account_id:
        accounts = execute_query("SELECT * FROM social_accounts WHERE id = ?", (account_id,))
    else:
        accounts = execute_query("SELECT * FROM social_accounts WHERE platform = ? LIMIT 1", (platform,))

    if not accounts:
        raise HTTPException(status_code=400, detail="Aucun compte configuré pour cette plateforme.")

    account = accounts[0]

    try:
        res = send_social_dm(account, recipient_id=recipient_id, message=reply_text)
        # Sauvegarder dans la DB
        execute_insert(
            """INSERT INTO inbox_messages (platform, account_id, recipient_id, content, is_from_me, message_type)
               VALUES (?, ?, ?, ?, 1, 'dm')""",
            (account["platform"], account["id"], recipient_id, reply_text)
        )
        return RedirectResponse(url="/#inbox", status_code=303)
    except SocialPublishError as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)

