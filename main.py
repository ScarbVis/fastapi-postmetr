# Path: main.py

import os
import json
import re
import time
import secrets
from datetime import datetime

# Load .env and .env.local
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request, Response, HTTPException, Depends, status
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from httpx import AsyncClient
from mongodb import store_data
from utils.youtube_utils import (
    fetch_video_info,
    fetch_channel_info,
    fetch_all_comments,
    fetch_top_comments,
    filter_video_info,
    filter_channel_info,
)

# ─── Environment & Configuration ─────────────────────────────────────────────
ENVIRONMENT = os.getenv("ENVIRONMENT", "production").lower()

raw_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "https://socialdataextract.com,chrome-extension://bahalfjjniacefhcbdlchohjcnbkmakl,chrome-extension://ncokmpbnihimbgepjinkmhdiiapokgel"
)
ALLOWED_ORIGINS = [o.strip() for o in raw_origins.split(",") if o.strip()]

if ENVIRONMENT != "production":
    # auto-whitelist for development
    ALLOWED_ORIGINS += ["http://localhost:8000", "http://127.0.0.1:8000"]

SESSION_WINDOW = int(os.getenv("SESSION_WINDOW", "60"))  # seconds
SESSION_LIMIT  = int(os.getenv("SESSION_LIMIT",  "30"))  # requests per window

# in-memory session buckets (use Redis in prod)
_session_store = {}

# ─── FastAPI Setup ────────────────────────────────────────────────────────────
app = FastAPI()

# 1) CORS: allow GET, OPTIONS for whitelisted origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=True,
    expose_headers=["Content-Disposition"],
)

# 2) Global IP rate-limit
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ─── Helpers ─────────────────────────────────────────────────────────────────
def _get_session(request: Request, response: Response) -> str:
    """Create/retrieve an HttpOnly 'anon_session' cookie and reset its bucket."""
    sid = request.cookies.get("anon_session")
    now = time.time()
    bucket = _session_store.get(sid)

    if not sid or not bucket:
        sid = secrets.token_urlsafe(32)
        _session_store[sid] = {"count": 0, "ts": now}
        response.set_cookie(
            "anon_session", sid,
            httponly=True,
            secure=(ENVIRONMENT == "production"),
            samesite="lax",
            max_age=31536000,
        )
    else:
        if now - bucket["ts"] > SESSION_WINDOW:
            bucket["count"] = 0
            bucket["ts"]    = now

    return sid

def verify_client(request: Request, response: Response):
    """
    1) If Origin header present, enforce it matches ALLOWED_ORIGINS.
    2) If Referer header present, enforce it starts with ALLOWED_ORIGINS.
    3) Throttle per-session via anon_session cookie.
    """
    origin  = request.headers.get("origin")
    referer = request.headers.get("referer")

    if origin and origin not in ALLOWED_ORIGINS:
        raise HTTPException(status_code=403, detail="Forbidden origin")
    if referer and not any(referer.startswith(o) for o in ALLOWED_ORIGINS):
        raise HTTPException(status_code=403, detail="Forbidden referer")

    sid = _get_session(request, response)
    bucket = _session_store[sid]
    if bucket["count"] >= SESSION_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests, please wait."
        )
    bucket["count"] += 1
    return True

# ─── Endpoints ────────────────────────────────────────────────────────────────
@app.get("/videos/{video_id}/details")
@limiter.limit("10/minute")
async def get_video_details(
    request: Request,
    response: Response,
    video_id: str,
    _: bool = Depends(verify_client),
):
    start = time.time()
    async with AsyncClient(timeout=10.0) as client:
        video_raw    = await fetch_video_info(client, video_id)
        video_info   = filter_video_info(video_raw)
        channel_raw  = await fetch_channel_info(client, video_raw["snippet"]["channelId"])
        channel_info = filter_channel_info(channel_raw)
        comments     = await fetch_all_comments(client, video_id)

    result = {
        "video_id": video_id,
        "video_info": video_info,
        "channel_info": channel_info,
        "comments": comments,
    }
    duration = time.time() - start
    await store_data(result, duration)

    # prepare filename
    today    = datetime.now().strftime("%Y-%m-%d")
    slug     = re.sub(r"[^\w\-]+", "_", video_info.get("title", "video"))
    filename = f"{today}_{slug}.json"

    def iter_json():
        yield json.dumps(result, ensure_ascii=False, indent=2)

    headers = {"Content-Disposition": f"attachment; filename=\"{filename}\""}
    return StreamingResponse(iter_json(), media_type="application/json", headers=headers)

@app.get("/videos/{video_id}/top-comments")
@limiter.limit("10/minute")
async def get_top_comments(
    request: Request,
    response: Response,
    video_id: str,
    _: bool = Depends(verify_client),
):
    start = time.time()
    async with AsyncClient(timeout=10.0) as client:
        video_raw    = await fetch_video_info(client, video_id)
        video_info   = filter_video_info(video_raw)
        channel_raw  = await fetch_channel_info(client, video_raw["snippet"]["channelId"])
        channel_info = filter_channel_info(channel_raw)
        comments     = await fetch_top_comments(client, video_id, limit=100)

    result = {
        "video_id": video_id,
        "video_info": video_info,
        "channel_info": channel_info,
        "comments": comments,
    }
    duration = time.time() - start
    await store_data(result, duration)

    today    = datetime.now().strftime("%Y-%m-%d")
    slug     = re.sub(r"[^\w\-]+", "_", video_info.get("title", "video"))
    filename = f"{today}_{slug}_top_comments.json"

    def iter_json():
        yield json.dumps(result, ensure_ascii=False, indent=2)

    headers = {"Content-Disposition": f"attachment; filename=\"{filename}\""}
    return StreamingResponse(iter_json(), media_type="application/json", headers=headers)
