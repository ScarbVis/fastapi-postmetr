# Path: /main.py

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import httpx
import os
import certifi
import json  # for writing JSON files
from datetime import datetime  # for timestamping filenames
import re  # for slugifying titles
from textblob import TextBlob
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from mongodb import store_data  # custom MongoDB storage
import time

# Set the SSL_CERT_FILE environment variable to Certifi's certificate bundle.
os.environ["SSL_CERT_FILE"] = certifi.where()

# Download VADER lexicon (if not already present).
nltk.download("vader_lexicon", quiet=True)

# Initialize VADER sentiment analyzer.
sia = SentimentIntensityAnalyzer()

# Initialize FastAPI.
app = FastAPI()

# Load YouTube API key from environment.
YOUTUBE_DATA_API_KEY = os.getenv("YOUTUBE_DATA_API_KEY")
if not YOUTUBE_DATA_API_KEY:
    raise RuntimeError("YOUTUBE_DATA_API_KEY environment variable not set.")

# ---- Utility Functions ----

def filter_video_info(video_info: dict) -> dict:
    snippet = video_info.get("snippet", {})
    statistics = video_info.get("statistics", {})
    return {
        "id": video_info.get("id"),
        "title": snippet.get("title"),
        "description": snippet.get("description"),
        "publishedAt": snippet.get("publishedAt"),
        "viewCount": statistics.get("viewCount"),
        "likeCount": statistics.get("likeCount"),
        "commentCount": statistics.get("commentCount")
    }


def filter_channel_info(channel_info: dict) -> dict:
    snippet = channel_info.get("snippet", {})
    statistics = channel_info.get("statistics", {})
    return {
        "id": channel_info.get("id"),
        "title": snippet.get("title"),
        "description": snippet.get("description"),
        "publishedAt": snippet.get("publishedAt"),
        "subscriberCount": statistics.get("subscriberCount"),
        "videoCount": statistics.get("videoCount")
    }


def analyze_sentiment(text: str) -> dict:
    # TextBlob analysis
    blob = TextBlob(text)
    textblob_sentiment = {
        "polarity": blob.sentiment.polarity,
        "subjectivity": blob.sentiment.subjectivity
    }
    # VADER analysis
    vader_sentiment = sia.polarity_scores(text)
    return {"textblob": textblob_sentiment, "vader": vader_sentiment}


def filter_comment(comment: dict) -> dict:
    snippet = comment.get("snippet", {})
    text = snippet.get("textDisplay", "")
    return {
        "id": comment.get("id"),
        "author": snippet.get("authorDisplayName"),
        "text": text,
        "publishedAt": snippet.get("publishedAt"),
        "likeCount": snippet.get("likeCount"),
        "sentiment": analyze_sentiment(text)
    }

# ---- External Service Functions ----

async def fetch_video_info(client: httpx.AsyncClient, video_id: str) -> dict:
    video_url = "https://www.googleapis.com/youtube/v3/videos"
    params = {
        "key": YOUTUBE_DATA_API_KEY,
        "part": "snippet,contentDetails,statistics",
        "id": video_id
    }
    resp = await client.get(video_url, params=params)
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="Error fetching video information")
    data = resp.json()
    items = data.get("items")
    if not items:
        raise HTTPException(status_code=404, detail="Video not found")
    return items[0]

async def fetch_channel_info(client: httpx.AsyncClient, channel_id: str) -> dict:
    channel_url = "https://www.googleapis.com/youtube/v3/channels"
    params = {
        "key": YOUTUBE_DATA_API_KEY,
        "part": "snippet,statistics",
        "id": channel_id
    }
    resp = await client.get(channel_url, params=params)
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="Error fetching channel information")
    data = resp.json()
    items = data.get("items")
    if not items:
        raise HTTPException(status_code=404, detail="Channel not found")
    return items[0]

async def fetch_all_comments(client: httpx.AsyncClient, video_id: str) -> list:
    comments_url = "https://www.googleapis.com/youtube/v3/commentThreads"
    params = {
        "key": YOUTUBE_DATA_API_KEY,
        "textFormat": "plainText",
        "part": "snippet,replies",
        "videoId": video_id,
        "maxResults": 100
    }
    all_comments = []
    next_token = None
    while True:
        if next_token:
            params["pageToken"] = next_token
        resp = await client.get(comments_url, params=params)
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail="Error fetching comments")
        data = resp.json()
        for item in data.get("items", []):
            top = item.get("snippet", {}).get("topLevelComment")
            if not top:
                continue
            filtered = filter_comment(top)
            replies = []
            for reply in item.get("replies", {}).get("comments", []):
                replies.append(filter_comment(reply))
            all_comments.append({"comment": filtered, "replies": replies})
        next_token = data.get("nextPageToken")
        if not next_token:
            break
    return all_comments

# ---- FastAPI Endpoint ----
@app.get("/videos/{video_id}/details")
async def get_video_details(video_id: str):
    start_time = time.time()
    async with httpx.AsyncClient() as client:
        video_raw = await fetch_video_info(client, video_id)
        video_info = filter_video_info(video_raw)
        channel_id = video_raw["snippet"]["channelId"]
        channel_raw = await fetch_channel_info(client, channel_id)
        channel_info = filter_channel_info(channel_raw)
        comments = await fetch_all_comments(client, video_id)
        result = {
            "video_id": video_id,
            "video_info": video_info,
            "channel_info": channel_info,
            "comments": comments
        }
    processing_time = time.time() - start_time
    await store_data(result, processing_time)

    # Generate filename: yyyy-mm-dd_title.json
    today = datetime.now().strftime("%Y-%m-%d")
    title = video_info.get("title", "video")
    slug = re.sub(r"[^\w\-]+", "_", title)
    filename = f"{today}_{slug}.json"
    folder = "./data/json"
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    response = JSONResponse(content=result)
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response
