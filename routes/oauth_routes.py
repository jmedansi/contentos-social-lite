import os
import json
import logging
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Form
from fastapi.responses import RedirectResponse, JSONResponse
import httpx
from services.db import execute_query, execute_insert

logger = logging.getLogger("oauth_routes")
router = APIRouter(prefix="/oauth", tags=["OAuth"])

APP_URL = os.getenv("APP_URL", "http://localhost:8000")
META_CLIENT_ID = os.getenv("META_CLIENT_ID", "")
META_CLIENT_SECRET = os.getenv("META_CLIENT_SECRET", "")
META_REDIRECT_URI = f"{APP_URL}/oauth/meta/callback"

LINKEDIN_CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID", "")
LINKEDIN_CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET", "")
LINKEDIN_REDIRECT_URI = f"{APP_URL}/oauth/linkedin/callback"

# ---------------- META (Facebook & Instagram) ----------------
@router.get("/meta/login")
def meta_login():
    if not META_CLIENT_ID:
        raise HTTPException(status_code=500, detail="META_CLIENT_ID non configuré.")
    scopes = [
        "pages_show_list",
        "pages_read_engagement",
        "pages_manage_posts",
        "pages_manage_engagement",
        "pages_messaging",
        "instagram_basic",
        "instagram_content_publish",
        "instagram_manage_comments",
        "instagram_manage_messages"
    ]
    url = (
        f"https://www.facebook.com/v21.0/dialog/oauth?"
        f"client_id={META_CLIENT_ID}&redirect_uri={META_REDIRECT_URI}&scope={','.join(scopes)}"
    )
    return RedirectResponse(url)

@router.get("/meta/callback")
async def meta_callback(code: Optional[str] = None, error: Optional[str] = None):
    if error or not code:
        return JSONResponse({"ok": False, "error": error or "Code manquant"}, status_code=400)

    # 1. Échange du code contre User Token
    async with httpx.AsyncClient() as client:
        token_url = "https://graph.facebook.com/v21.0/oauth/access_token"
        resp = await client.get(token_url, params={
            "client_id": META_CLIENT_ID,
            "client_secret": META_CLIENT_SECRET,
            "redirect_uri": META_REDIRECT_URI,
            "code": code
        })
        token_data = resp.json()
        user_access_token = token_data.get("access_token")
        if not user_access_token:
            return JSONResponse({"ok": False, "detail": token_data}, status_code=400)

        # 2. Récupération des Pages Facebook gérées
        pages_resp = await client.get("https://graph.facebook.com/v21.0/me/accounts", params={
            "access_token": user_access_token,
            "fields": "id,name,access_token,instagram_business_account"
        })
        pages_data = pages_resp.json().get("data", [])

        saved_accounts = []
        for page in pages_data:
            page_id = page.get("id")
            page_name = page.get("name")
            page_token = page.get("access_token")
            ig_account = page.get("instagram_business_account", {})
            ig_id = ig_account.get("id") if ig_account else None

            # Enregistrer la Page Facebook
            execute_insert(
                """INSERT INTO social_accounts (platform, account_name, page_id, access_token, settings)
                   VALUES (?, ?, ?, ?, ?)""",
                ("facebook", page_name, page_id, page_token, json.dumps({"page_id": page_id}))
            )
            saved_accounts.append(f"Facebook: {page_name}")

            # Si Instagram Business lié, enregistrer le compte Instagram
            if ig_id:
                execute_insert(
                    """INSERT INTO social_accounts (platform, account_name, page_id, access_token, settings)
                       VALUES (?, ?, ?, ?, ?)""",
                    ("instagram", f"{page_name} (Instagram)", page_id, page_token, json.dumps({"ig_user_id": ig_id}))
                )
                saved_accounts.append(f"Instagram (lié à {page_name})")

    return RedirectResponse(url="/?oauth_success=meta")

# ---------------- LINKEDIN ----------------
@router.get("/linkedin/login")
def linkedin_login():
    if not LINKEDIN_CLIENT_ID:
        raise HTTPException(status_code=500, detail="LINKEDIN_CLIENT_ID non configuré.")
    scopes = ["openid", "profile", "w_member_social"]
    url = (
        f"https://www.linkedin.com/oauth/v2/authorization?"
        f"response_type=code&client_id={LINKEDIN_CLIENT_ID}&redirect_uri={LINKEDIN_REDIRECT_URI}&scope={' '.join(scopes)}"
    )
    return RedirectResponse(url)

@router.get("/linkedin/callback")
async def linkedin_callback(code: Optional[str] = None, error: Optional[str] = None):
    if error or not code:
        return JSONResponse({"ok": False, "error": error or "Code manquant"}, status_code=400)

    async with httpx.AsyncClient() as client:
        token_url = "https://www.linkedin.com/oauth/v2/accessToken"
        resp = await client.post(token_url, data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": LINKEDIN_REDIRECT_URI,
            "client_id": LINKEDIN_CLIENT_ID,
            "client_secret": LINKEDIN_CLIENT_SECRET
        })
        token_data = resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            return JSONResponse({"ok": False, "detail": token_data}, status_code=400)

        # Profil
        userinfo_resp = await client.get("https://api.linkedin.com/v2/userinfo", headers={
            "Authorization": f"Bearer {access_token}"
        })
        userinfo = userinfo_resp.json()
        sub = userinfo.get("sub")
        name = userinfo.get("name") or "LinkedIn User"

        execute_insert(
            """INSERT INTO social_accounts (platform, account_name, page_id, access_token, settings)
               VALUES (?, ?, ?, ?, ?)""",
            ("linkedin", name, sub, access_token, json.dumps({"author_urn": f"urn:li:person:{sub}"}))
        )

    return RedirectResponse(url="/?oauth_success=linkedin")

# ---------------- AJOUT MANUEL DE TOKEN (POUR LES TESTS RAPIDES) ----------------
@router.post("/manual/add")
def add_manual_account(
    platform: str = Form(...),
    account_name: str = Form(...),
    page_id: str = Form(""),
    access_token: str = Form(...),
    ig_user_id: str = Form("")
):
    settings = {}
    if ig_user_id:
        settings["ig_user_id"] = ig_user_id
    if platform == "linkedin":
        settings["author_urn"] = f"urn:li:person:{page_id}"

    execute_insert(
        """INSERT INTO social_accounts (platform, account_name, page_id, access_token, settings)
           VALUES (?, ?, ?, ?, ?)""",
        (platform.lower(), account_name, page_id, access_token, json.dumps(settings))
    )
    return RedirectResponse(url="/?account_added=1", status_code=303)
