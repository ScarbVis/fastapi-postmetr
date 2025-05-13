# Path: main.py

from fastapi import FastAPI
from fastapi.responses import JSONResponse
import os, json, re, time
from datetime import datetime
from httpx import AsyncClient

from mongodb import store_data
from utils.youtube_utils import (
    fetch_video_info, fetch_channel_info,
    fetch_all_comments, fetch_top_comments,
    filter_video_info, filter_channel_info
)

app = FastAPI()

@app.get("/videos/{video_id}/details")
async def get_video_details(video_id: str):
    start = time.time()
    async with AsyncClient() as client:
        video_raw = await fetch_video_info(client, video_id)
        video_info = filter_video_info(video_raw)
        channel_raw = await fetch_channel_info(client, video_raw["snippet"]["channelId"])
        channel_info = filter_channel_info(channel_raw)
        comments = await fetch_all_comments(client, video_id)
        result = {
            "video_id": video_id,
            "video_info": video_info,
            "channel_info": channel_info,
            "comments": comments
        }
    duration = time.time() - start
    await store_data(result, duration)

    # write JSON file
    today = datetime.now().strftime("%Y-%m-%d")
    slug = re.sub(r"[^\w\-]+", "_", video_info.get("title", "video"))
    folder = "./data/json"; os.makedirs(folder, exist_ok=True)
    filename = f"{today}_{slug}.json"
    path = os.path.join(folder, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    resp = JSONResponse(content=result)
    resp.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return resp

@app.get("/videos/{video_id}/top-comments")
async def get_top_comments(video_id: str):
    """
    Returns up to 100 comments sorted by YouTube's 'relevance', plus JSON file download.
    """
    start = time.time()
    async with AsyncClient() as client:
        video_raw = await fetch_video_info(client, video_id)
        video_info = filter_video_info(video_raw)
        channel_raw = await fetch_channel_info(client, video_raw["snippet"]["channelId"])
        channel_info = filter_channel_info(channel_raw)
        comments = await fetch_top_comments(client, video_id, limit=100)
        result = {
            "video_id": video_id,
            "video_info": video_info,
            "channel_info": channel_info,
            "comments": comments
        }
    duration = time.time() - start
    await store_data(result, duration)

    # write JSON file
    today = datetime.now().strftime("%Y-%m-%d")
    slug = re.sub(r"[^\w\-]+", "_", video_info.get("title", "video"))
    folder = "./data/json"; os.makedirs(folder, exist_ok=True)
    filename = f"{today}_{slug}_top_comments.json"
    path = os.path.join(folder, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    resp = JSONResponse(content=result)
    resp.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return resp
