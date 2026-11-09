import os
import json
import logging
from typing import Any, Dict, Optional
import httpx

logger = logging.getLogger("social_publishers")

GRAPH_VERSION = "v21.0"
FACEBOOK_GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"

class SocialPublishError(Exception):
    def __init__(self, message: str, detail: Optional[str] = None):
        super().__init__(message)
        self.detail = detail or ""

def get_settings(account: Dict[str, Any]) -> Dict[str, Any]:
    raw = account.get("settings")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return {}
    return {}

# -------------------------------------------------------------
# 1. PUBLICATION DIRECTE (POSTS)
# -------------------------------------------------------------

def publish_facebook_direct(account: Dict[str, Any], message: str, media_url: Optional[str] = None, client: Optional[httpx.Client] = None) -> Dict[str, Any]:
    """Publie directement sur une Page Facebook."""
    page_id = account.get("page_id")
    token = account.get("access_token")
    if not page_id or not token:
        raise SocialPublishError("Page ID ou Access Token Facebook manquant.")

    own_client = client is None
    c = client or httpx.Client(timeout=30.0)
    try:
        if media_url:
            # Publication avec photo
            endpoint = f"{FACEBOOK_GRAPH_BASE}/{page_id}/photos"
            resp = c.post(endpoint, data={"url": media_url, "caption": message, "access_token": token})
        else:
            # Publication simple statut texte
            endpoint = f"{FACEBOOK_GRAPH_BASE}/{page_id}/feed"
            resp = c.post(endpoint, data={"message": message, "access_token": token})

        data = resp.json()
        if resp.status_code >= 400:
            error_msg = data.get("error", {}).get("message", "Erreur Facebook inconnue")
            raise SocialPublishError(f"Erreur Facebook: {error_msg}", detail=str(data))
        
        post_id = data.get("id") or data.get("post_id")
        return {"ok": True, "remote_id": str(post_id), "platform": "facebook"}
    finally:
        if own_client:
            c.close()

def publish_instagram_direct(account: Dict[str, Any], message: str, media_url: str, client: Optional[httpx.Client] = None) -> Dict[str, Any]:
    """Publie directement sur Instagram (exige une image/vidéo)."""
    settings = get_settings(account)
    ig_user_id = settings.get("ig_user_id") or account.get("page_id")
    token = account.get("access_token")
    if not ig_user_id or not token:
        raise SocialPublishError("Instagram Business ID ou Access Token manquant.")
    if not media_url:
        raise SocialPublishError("Instagram exige impérativement une URL de média (image ou vidéo).")

    own_client = client is None
    c = client or httpx.Client(timeout=45.0)
    try:
        # Étape 1 : Créer le conteneur média
        container_url = f"{FACEBOOK_GRAPH_BASE}/{ig_user_id}/media"
        is_video = any(media_url.lower().endswith(ext) for ext in [".mp4", ".mov"])
        payload = {
            "caption": message,
            "access_token": token
        }
        if is_video:
            payload["media_type"] = "REELS"
            payload["video_url"] = media_url
        else:
            payload["image_url"] = media_url

        resp = c.post(container_url, data=payload)
        data = resp.json()
        if resp.status_code >= 400:
            raise SocialPublishError(f"Erreur création conteneur Instagram: {data.get('error', {}).get('message')}")
        creation_id = data.get("id")

        # Étape 2 : Publier le conteneur
        publish_url = f"{FACEBOOK_GRAPH_BASE}/{ig_user_id}/media_publish"
        pub_resp = c.post(publish_url, data={"creation_id": creation_id, "access_token": token})
        pub_data = pub_resp.json()
        if pub_resp.status_code >= 400:
            raise SocialPublishError(f"Erreur publication Instagram: {pub_data.get('error', {}).get('message')}")

        return {"ok": True, "remote_id": str(pub_data.get("id")), "platform": "instagram"}
    finally:
        if own_client:
            c.close()

def publish_linkedin_direct(account: Dict[str, Any], message: str, client: Optional[httpx.Client] = None) -> Dict[str, Any]:
    """Publie directement sur un profil ou organisation LinkedIn via l'API v2 Posts."""
    token = account.get("access_token")
    settings = get_settings(account)
    author_urn = settings.get("author_urn") or f"urn:li:person:{account.get('page_id')}"
    if not token:
        raise SocialPublishError("Access Token LinkedIn manquant.")

    own_client = client is None
    c = client or httpx.Client(timeout=30.0)
    try:
        endpoint = "https://api.linkedin.com/v2/posts"
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json"
        }
        body = {
            "author": author_urn,
            "commentary": message,
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": []
            },
            "lifecycleState": "PUBLISHED"
        }
        resp = c.post(endpoint, json=body, headers=headers)
        if resp.status_code not in (200, 201):
            raise SocialPublishError(f"Erreur LinkedIn ({resp.status_code}): {resp.text}")
        post_urn = resp.headers.get("x-restli-id") or "published"
        return {"ok": True, "remote_id": str(post_urn), "platform": "linkedin"}
    finally:
        if own_client:
            c.close()

def publish_direct(account: Dict[str, Any], message: str, media_url: Optional[str] = None) -> Dict[str, Any]:
    platform = str(account.get("platform") or "").lower()
    if platform == "facebook":
        return publish_facebook_direct(account, message, media_url)
    elif platform == "instagram":
        return publish_instagram_direct(account, message, media_url)
    elif platform == "linkedin":
        return publish_linkedin_direct(account, message)
    else:
        raise SocialPublishError(f"Plateforme '{platform}' non supportée pour la publication directe.")

# -------------------------------------------------------------
# 2. RÉPONSES AUX COMMENTAIRES ET DM (MANUELLES)
# -------------------------------------------------------------

def reply_to_comment(account: Dict[str, Any], comment_id: str, message: str) -> Dict[str, Any]:
    """Répond à un commentaire Facebook ou Instagram."""
    token = account.get("access_token")
    if not token:
        raise SocialPublishError("Access token requis.")

    with httpx.Client(timeout=25.0) as client:
        url = f"{FACEBOOK_GRAPH_BASE}/{comment_id}/comments"
        resp = client.post(url, data={"message": message, "access_token": token})
        data = resp.json()
        if resp.status_code >= 400:
            raise SocialPublishError(f"Erreur réponse commentaire: {data.get('error', {}).get('message')}")
        return {"ok": True, "reply_id": str(data.get("id"))}

def send_social_dm(account: Dict[str, Any], recipient_id: str, message: str) -> Dict[str, Any]:
    """Envoie un Message Privé (DM) via Messenger ou Instagram Graph API."""
    platform = str(account.get("platform") or "").lower()
    token = account.get("access_token")
    settings = get_settings(account)
    
    with httpx.Client(timeout=25.0) as client:
        if platform == "instagram":
            ig_user_id = settings.get("ig_user_id") or account.get("page_id")
            url = f"{FACEBOOK_GRAPH_BASE}/{ig_user_id}/messages"
        elif platform == "facebook":
            page_id = account.get("page_id")
            url = f"{FACEBOOK_GRAPH_BASE}/{page_id}/messages"
        else:
            raise SocialPublishError(f"DM direct non supporté pour {platform}")

        body = {
            "recipient": {"id": str(recipient_id)},
            "message": {"text": str(message)}
        }
        resp = client.post(url, json=body, params={"access_token": token})
        data = resp.json()
        if resp.status_code >= 400:
            raise SocialPublishError(f"Erreur envoi DM: {data.get('error', {}).get('message')}")
        return {"ok": True, "message_id": str(data.get("message_id") or data.get("id"))}
