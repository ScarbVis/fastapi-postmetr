# Path: utils/youtube_utils.py

import os
import certifi
import nltk
from textblob import TextBlob
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import httpx
from fastapi import HTTPException

# ensure cert and vader are ready
os.environ["SSL_CERT_FILE"] = certifi.where()
nltk.download("vader_lexicon", quiet=True)
_sia = SentimentIntensityAnalyzer()

# load API key once
YOUTUBE_DATA_API_KEY = os.getenv("YOUTUBE_DATA_API_KEY")
if not YOUTUBE_DATA_API_KEY:
    raise RuntimeError("YOUTUBE_DATA_API_KEY environment variable not set.")

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
    # TextBlob
    blob = TextBlob(text)
    tb = {"polarity": blob.sentiment.polarity, "subjectivity": blob.sentiment.subjectivity}
    # VADER
    vd = _sia.polarity_scores(text)
    return {"textblob": tb, "vader": vd}

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

async def fetch_video_info(client: httpx.AsyncClient, video_id: str) -> dict:
    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {
        "key": YOUTUBE_DATA_API_KEY,
        "part": "snippet,contentDetails,statistics",
        "id": video_id
    }
    resp = await client.get(url, params=params)
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="Error fetching video information")
    items = resp.json().get("items") or []
    if not items:
        raise HTTPException(status_code=404, detail="Video not found")
    return items[0]

async def fetch_channel_info(client: httpx.AsyncClient, channel_id: str) -> dict:
    url = "https://www.googleapis.com/youtube/v3/channels"
    params = {"key": YOUTUBE_DATA_API_KEY, "part": "snippet,statistics", "id": channel_id}
    resp = await client.get(url, params=params)
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="Error fetching channel information")
    items = resp.json().get("items") or []
    if not items:
        raise HTTPException(status_code=404, detail="Channel not found")
    return items[0]

async def fetch_all_comments(client: httpx.AsyncClient, video_id: str) -> list:
    # (unchanged – returns every comment, sorted by default order)
    url = "https://www.googleapis.com/youtube/v3/commentThreads"
    params = {
        "key": YOUTUBE_DATA_API_KEY,
        "textFormat": "plainText",
        "part": "snippet,replies",
        "videoId": video_id,
        "maxResults": 100
    }
    all_comments = []
    token = None
    while True:
        if token:
            params["pageToken"] = token
        resp = await client.get(url, params=params)
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail="Error fetching comments")
        data = resp.json()
        for item in data.get("items", []):
            top = item.get("snippet", {}).get("topLevelComment")
            if not top:
                continue
            c = filter_comment(top)
            replies = [filter_comment(r) for r in item.get("replies", {}).get("comments", [])]
            all_comments.append({"comment": c, "replies": replies})
        token = data.get("nextPageToken")
        if not token:
            break
    return all_comments

async def fetch_top_comments(client: httpx.AsyncClient, video_id: str, limit: int = 100) -> list:
    """
    Fetch up to `limit` top‐level comments sorted by relevance.
    """
    url = "https://www.googleapis.com/youtube/v3/commentThreads"
    params = {
        "key": YOUTUBE_DATA_API_KEY,
        "textFormat": "plainText",
        "part": "snippet,replies",
        "videoId": video_id,
        "order": "relevance",      # built-in relevance ordering
        "maxResults": min(limit, 100)
    }
    resp = await client.get(url, params=params)
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="Error fetching top comments")
    items = resp.json().get("items", [])[:limit]
    top_comments = []
    for item in items:
        top = item.get("snippet", {}).get("topLevelComment")
        if not top:
            continue
        c = filter_comment(top)
        replies = [filter_comment(r) for r in item.get("replies", {}).get("comments", [])]
        top_comments.append({"comment": c, "replies": replies})
    return top_comments
