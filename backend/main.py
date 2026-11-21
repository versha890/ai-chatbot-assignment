
import os
import json
import time
import sqlite3
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

import litellm
from litellm import completion, Cache

load_dotenv()

# Configuration
API_KEYS = [
    key.strip()
    for key in os.getenv("LLM_API_KEYS", "").split(",")
    if key.strip()
]

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")
MODEL = os.getenv("LLM_MODEL", "groq/openai/gpt-oss-20b")
ENABLE_SIMULATION = (
    os.getenv("ENABLE_FAILURE_SIMULATION", "false").lower() == "true"
)

DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful AI assistant. "
    "Give accurate, clear and concise answers."
)

# LiteLLM built-in local cache
litellm.cache = Cache(type="local")


def get_db_path():
    if not DATABASE_URL.startswith("sqlite:///"):
        raise RuntimeError("Only SQLite DATABASE_URL is supported")

    return DATABASE_URL.replace("sqlite:///", "", 1)


DB_PATH = get_db_path()


def get_connection():
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                system_prompt TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT,
                created_at TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_session
            ON messages(session_id, id)
        """)


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()

    if len(API_KEYS) < 2:
        raise RuntimeError("At least two API keys are required")

    yield


app = FastAPI(
    title="AI Chat with Smart Fallback",
    version="1.0.0",
    lifespan=lifespan
)

origins = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS", "http://localhost:3000"
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=4000)
    system_prompt: str | None = None

    @field_validator("session_id", "message")
    @classmethod
    def strip_strings(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Field cannot be empty")
        return value


def get_failure_map(header_value):
    failures = {}

    if not ENABLE_SIMULATION or not header_value:
        return failures

    for item in header_value.split(","):
        try:
            key_id, status = item.strip().split("=")
            if status not in {"429", "500", "502", "503"}:
                continue
            failures[key_id.strip()] = int(status)
        except ValueError:
            continue

    return failures


def save_message(session_id, role, content, metadata=None):
    created_at = datetime.now(timezone.utc).isoformat()

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO messages
            (session_id, role, content, metadata, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                session_id,
                role,
                content,
                json.dumps(metadata) if metadata else None,
                created_at
            )
        )


def get_session(session_id):
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?",
            (session_id,)
        ).fetchone()


def get_history(session_id):
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT role, content
            FROM messages
            WHERE session_id = ?
            ORDER BY id ASC
            """,
            (session_id,)
        ).fetchall()

    return [
        {"role": row["role"], "content": row["content"]}
        for row in rows
    ]


@app.get("/health")
def health():
    try:
        with get_connection() as conn:
            conn.execute("SELECT 1")

        if len(API_KEYS) < 2:
            raise RuntimeError("Key pool incomplete")

        return {
            "status": "ok",
            "keys_configured": len(API_KEYS),
            "cache_enabled": True
        }

    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Service unavailable"
        )


@app.post("/chat")
def chat(
    request: ChatRequest,
    x_simulate_failure: str | None = Header(default=None)
):
    start_time = time.perf_counter()

    session = get_session(request.session_id)

    if session:
        system_prompt = (
            request.system_prompt
            if request.system_prompt is not None
            else session["system_prompt"]
        )
        history = get_history(request.session_id)
    else:
        system_prompt = (
            request.system_prompt or DEFAULT_SYSTEM_PROMPT
        )
        history = []

    messages = [
        {"role": "system", "content": system_prompt},
        *history,
        {"role": "user", "content": request.message}
    ]

    failure_map = get_failure_map(x_simulate_failure)

    for index, api_key in enumerate(API_KEYS):
        key_id = f"key_{index + 1}"

        # Simulate a provider failure for this request only
        if key_id in failure_map or "*" in failure_map:
            continue

        try:
            response = completion(
                model=MODEL,
                messages=messages,
                api_key=api_key,
                caching=True,
                temperature=0.7
            )

            reply = response.choices[0].message.content

            if not reply or not reply.strip():
                raise ValueError("Empty model response")

            usage = response.usage
            hidden = getattr(response, "_hidden_params", {}) or {}

            cache_hit = bool(hidden.get("cache_hit", False))

            latency_ms = int(
                (time.perf_counter() - start_time) * 1000
            )

            metadata = {
                "resolution_source": (
                    "LLM_CACHE" if cache_hit
                    else "LIVE_INFERENCE"
                ),
                "model": MODEL,
                "latency_ms": latency_ms,
                "input_tokens": int(usage.prompt_tokens or 0),
                "output_tokens": int(usage.completion_tokens or 0),
                "key_id": None if cache_hit else key_id,
                "fallback_attempts": (
                    0 if cache_hit else index
                )
            }

            # Save only after a successful answer
            if not session:
                with get_connection() as conn:
                    conn.execute(
                        """
                        INSERT INTO sessions
                        (session_id, system_prompt)
                        VALUES (?, ?)
                        """,
                        (request.session_id, system_prompt)
                    )
            elif request.system_prompt is not None:
                with get_connection() as conn:
                    conn.execute(
                        """
                        UPDATE sessions
                        SET system_prompt = ?
                        WHERE session_id = ?
                        """,
                        (system_prompt, request.session_id)
                    )

            save_message(
                request.session_id, "user", request.message
            )
            save_message(
                request.session_id, "assistant", reply, metadata
            )

            return {
                "session_id": request.session_id,
                "reply": reply,
                "metadata": metadata
            }

        except Exception as e:
                print(f"\n[FAILOVER] {key_id} failed")
                print(f"[ERROR TYPE] {type(e).__name__}")
                print(f"[ERROR MESSAGE] {str(e)}")
                print("[FAILOVER] Trying next API key...\n")

                continue

    raise HTTPException(
        status_code=503,
        detail="all providers unavailable"
    )


@app.get("/sessions/{session_id}/messages")
def session_messages(session_id: str):
    session = get_session(session_id)

    if not session:
        raise HTTPException(
            status_code=404,
            detail="session not found"
        )

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT role, content, metadata
            FROM messages
            WHERE session_id = ?
            ORDER BY id ASC
            """,
            (session_id,)
        ).fetchall()

    messages = []

    for row in rows:
        item = {
            "role": row["role"],
            "content": row["content"]
        }

        if row["metadata"]:
            item["metadata"] = json.loads(row["metadata"])

        messages.append(item)

    return {
        "session_id": session_id,
        "messages": messages
    }
