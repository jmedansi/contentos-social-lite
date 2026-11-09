import os
import sys
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Ajout du dossier racine au PATH
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

from services.db import init_db, execute_query
from routes.oauth_routes import router as oauth_router
from routes.publish_routes import router as publish_router
from routes.inbox_routes import router as inbox_router
from routes.webhook_routes import router as webhook_router

app = FastAPI(
    title="ContentOS Social Lite",
    description="Version allégée sans IA pour testeurs de réseaux sociaux (Publication directe, Webhooks, Inbox DM/Commentaires)",
    version="1.0.0"
)

# Initialisation des tables à l'amorçage
@app.on_event("startup")
def on_startup():
    init_db()

# Montage des routes
app.include_router(oauth_router)
app.include_router(publish_router)
app.include_router(inbox_router)
app.include_router(webhook_router)

# Templates
templates_dir = ROOT_DIR / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

# Dashboard principal
@app.get("/", response_class=HTMLResponse)
def index_page(request: Request):
    accounts = execute_query("SELECT * FROM social_accounts WHERE is_active = 1 ORDER BY created_at DESC")
    publications = execute_query("SELECT * FROM social_publications ORDER BY created_at DESC LIMIT 10")
    messages = execute_query(
        """SELECT m.*, a.account_name FROM inbox_messages m 
           LEFT JOIN social_accounts a ON m.account_id = a.id 
           ORDER BY m.created_at DESC LIMIT 30"""
    )
    webhook_logs = execute_query("SELECT * FROM webhook_logs ORDER BY created_at DESC LIMIT 20")
    app_url = os.getenv("APP_URL", str(request.base_url).rstrip("/"))

    return templates.TemplateResponse("index.html", {
        "request": request,
        "accounts": accounts,
        "publications": publications,
        "messages": messages,
        "webhook_logs": webhook_logs,
        "app_url": app_url
    })

@app.get("/health")
def health_check():
    return {"status": "ok", "app": "ContentOS-Social-Lite", "ai_enabled": False, "scheduling_enabled": False}
