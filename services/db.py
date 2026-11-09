import os
import sqlite3
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

DATABASE_URL = os.getenv("DATABASE_URL", "")

def get_connection():
    """Fournit une connexion soit PostgreSQL (si DATABASE_URL configurée pour Neon/Supabase),
    soit SQLite local pour le développement et test hors-ligne."""
    if DATABASE_URL.startswith("postgres://") or DATABASE_URL.startswith("postgresql://"):
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    else:
        # Fallback local SQLite
        db_path = os.getenv("SQLITE_DB_PATH", "/tmp/social_lite.db" if os.name != "nt" else "social_lite.db")
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

def is_postgres() -> bool:
    return DATABASE_URL.startswith("postgres://") or DATABASE_URL.startswith("postgresql://")

_DB_INITIALIZED = False

def ensure_initialized():
    global _DB_INITIALIZED
    if not _DB_INITIALIZED:
        init_db()
        _DB_INITIALIZED = True

def execute_query(query: str, params: tuple = ()) -> List[Dict[str, Any]]:
    ensure_initialized()
    conn = get_connection()
    try:
        if is_postgres():
            import psycopg2.extras
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Adapter ? vers %s pour postgres
                pg_query = query.replace("?", "%s")
                cur.execute(pg_query, params)
                if cur.description:
                    rows = cur.fetchall()
                    return [dict(r) for r in rows]
                conn.commit()
                return []
        else:
            cur = conn.cursor()
            cur.execute(query, params)
            if cur.description:
                rows = cur.fetchall()
                return [dict(r) for r in rows]
            conn.commit()
            return []
    finally:
        conn.close()

def execute_insert(query: str, params: tuple = ()) -> int:
    ensure_initialized()
    conn = get_connection()
    try:
        if is_postgres():
            import psycopg2.extras
            # Si pas de RETURNING id dans la requete, on l'ajoute si INSERT
            pg_query = query.replace("?", "%s")
            if "RETURNING" not in pg_query.upper() and pg_query.strip().upper().startswith("INSERT"):
                pg_query += " RETURNING id;"
            with conn.cursor() as cur:
                cur.execute(pg_query, params)
                inserted_id = cur.fetchone()[0] if cur.description else 0
                conn.commit()
                return inserted_id
        else:
            cur = conn.cursor()
            cur.execute(query, params)
            inserted_id = cur.lastrowid
            conn.commit()
            return inserted_id
    finally:
        conn.close()

def init_db():
    """Initialise les tables indispensables pour les testeurs réseaux sociaux."""
    conn = get_connection()
    try:
        if is_postgres():
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS social_accounts (
                        id SERIAL PRIMARY KEY,
                        platform VARCHAR(50) NOT NULL,
                        account_name VARCHAR(255),
                        page_id VARCHAR(255),
                        access_token TEXT NOT NULL,
                        refresh_token TEXT,
                        token_expires_at TIMESTAMP,
                        settings JSONB DEFAULT '{}'::jsonb,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );

                    CREATE TABLE IF NOT EXISTS social_publications (
                        id SERIAL PRIMARY KEY,
                        account_id INTEGER REFERENCES social_accounts(id) ON DELETE CASCADE,
                        platform VARCHAR(50) NOT NULL,
                        message TEXT NOT NULL,
                        media_url TEXT,
                        remote_post_id VARCHAR(255),
                        status VARCHAR(50) DEFAULT 'published',
                        error_detail TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );

                    CREATE TABLE IF NOT EXISTS inbox_messages (
                        id SERIAL PRIMARY KEY,
                        platform VARCHAR(50) NOT NULL,
                        account_id INTEGER,
                        thread_id VARCHAR(255),
                        sender_id VARCHAR(255),
                        sender_name VARCHAR(255),
                        recipient_id VARCHAR(255),
                        message_type VARCHAR(50) DEFAULT 'dm', -- 'dm' ou 'comment'
                        remote_id VARCHAR(255),
                        parent_id VARCHAR(255),
                        content TEXT,
                        is_from_me BOOLEAN DEFAULT FALSE,
                        status VARCHAR(50) DEFAULT 'received',
                        raw_payload JSONB DEFAULT '{}'::jsonb,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );

                    CREATE TABLE IF NOT EXISTS webhook_logs (
                        id SERIAL PRIMARY KEY,
                        platform VARCHAR(50) NOT NULL,
                        event_type VARCHAR(100),
                        payload JSONB,
                        status VARCHAR(50) DEFAULT 'processed',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                conn.commit()
        else:
            cur = conn.cursor()
            cur.executescript("""
                CREATE TABLE IF NOT EXISTS social_accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL,
                    account_name TEXT,
                    page_id TEXT,
                    access_token TEXT NOT NULL,
                    refresh_token TEXT,
                    token_expires_at TIMESTAMP,
                    settings TEXT DEFAULT '{}',
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS social_publications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id INTEGER,
                    platform TEXT NOT NULL,
                    message TEXT NOT NULL,
                    media_url TEXT,
                    remote_post_id TEXT,
                    status TEXT DEFAULT 'published',
                    error_detail TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS inbox_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL,
                    account_id INTEGER,
                    thread_id TEXT,
                    sender_id TEXT,
                    sender_name TEXT,
                    recipient_id TEXT,
                    message_type TEXT DEFAULT 'dm',
                    remote_id TEXT,
                    parent_id TEXT,
                    content TEXT,
                    is_from_me INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'received',
                    raw_payload TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS webhook_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL,
                    event_type TEXT,
                    payload TEXT,
                    status TEXT DEFAULT 'processed',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()
    finally:
        conn.close()

