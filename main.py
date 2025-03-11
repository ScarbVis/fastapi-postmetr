from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import httpx
import os
import certifi
from textblob import TextBlob
import nltk

# Set the SSL_CERT_FILE environment variable to Certifi's certificate bundle.
os.environ["SSL_CERT_FILE"] = certifi.where()

# Now download the VADER lexicon without passing a custom context.
nltk.download("vader_lexicon")

from nltk.sentiment.vader import SentimentIntensityAnalyzer


# Download VADER lexicon if not already present
nltk.download('vader_lexicon', quiet=True)

# Initialize VADER sentiment analyzer
sia = SentimentIntensityAnalyzer()

app = FastAPI()

# Load the API key from the environment variable "YOUTUBE_DATA_API_KEY"
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
    """
    Performs sentiment analysis using both TextBlob and VADER.
    Returns a dictionary with results from each library.
    """
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
        "sentiment": analyze_sentiment(text)  # both TextBlob and VADER results
    }


# ---- External Service Functions ----
async def fetch_video_info(client: httpx.AsyncClient, video_id: str) -> dict:
    video_url = "https://www.googleapis.com/youtube/v3/videos"
    video_params = {
        "key": YOUTUBE_DATA_API_KEY,
        "part": "snippet,contentDetails,statistics",
        "id": video_id
    }
    video_response = await client.get(video_url, params=video_params)
    if video_response.status_code != 200:
        raise HTTPException(status_code=video_response.status_code, detail="Error fetching video information")
    video_data = video_response.json()
    if not video_data.get("items"):
        raise HTTPException(status_code=404, detail="Video not found")
    return video_data["items"][0]


async def fetch_channel_info(client: httpx.AsyncClient, channel_id: str) -> dict:
    channel_url = "https://www.googleapis.com/youtube/v3/channels"
    channel_params = {
        "key": YOUTUBE_DATA_API_KEY,
        "part": "snippet,statistics",
        "id": channel_id
    }
    channel_response = await client.get(channel_url, params=channel_params)
    if channel_response.status_code != 200:
        raise HTTPException(status_code=channel_response.status_code, detail="Error fetching channel information")
    channel_data = channel_response.json()
    if not channel_data.get("items"):
        raise HTTPException(status_code=404, detail="Channel not found")
    return channel_data["items"][0]


async def fetch_all_comments(client: httpx.AsyncClient, video_id: str) -> list:
    """
    Fetches all top-level comments (with available replies) for the specified video by handling pagination.
    Applies sentiment analysis (via TextBlob and VADER) to each comment and reply.
    """
    comments_url = "https://www.googleapis.com/youtube/v3/commentThreads"
    comment_params = {
        "key": YOUTUBE_DATA_API_KEY,
        "textFormat": "plainText",
        "part": "snippet,replies",
        "videoId": video_id,
        "maxResults": 100  # maximum allowed per request
    }
    
    all_comments = []
    next_page_token = None

    while True:
        if next_page_token:
            comment_params["pageToken"] = next_page_token
        else:
            comment_params.pop("pageToken", None)
        
        comment_response = await client.get(comments_url, params=comment_params)
        if comment_response.status_code != 200:
            raise HTTPException(
                status_code=comment_response.status_code, 
                detail="Error fetching comments"
            )
        comment_data = comment_response.json()
        
        # Process each comment thread
        for item in comment_data.get("items", []):
            top_comment_obj = item.get("snippet", {}).get("topLevelComment")
            if not top_comment_obj:
                continue
            filtered_top_comment = filter_comment(top_comment_obj)
            # Process available replies (if any)
            replies = []
            if "replies" in item:
                for reply in item["replies"].get("comments", []):
                    replies.append(filter_comment(reply))
            all_comments.append({
                "comment": filtered_top_comment,
                "replies": replies
            })
        
        # Check for pagination
        next_page_token = comment_data.get("nextPageToken")
        if not next_page_token:
            break

    return all_comments


# ---- FastAPI Endpoint ----
@app.get("/videos/{video_id}/details")
async def get_video_details(video_id: str):
    """
    Fetches filtered video details, channel information, and all top-level comments (with available replies)
    along with sentiment analytics (both TextBlob and VADER) for each comment, for the specified YouTube video.
    The response is returned as a downloadable JSON file.
    """
    async with httpx.AsyncClient() as client:
        # 1. Get video information and filter it
        video_info_raw = await fetch_video_info(client, video_id)
        filtered_video_info = filter_video_info(video_info_raw)

        # 2. Get channel information using channelId from video info
        channel_id = video_info_raw.get("snippet", {}).get("channelId")
        if not channel_id:
            raise HTTPException(status_code=404, detail="Channel ID not found in video information")
        channel_info_raw = await fetch_channel_info(client, channel_id)
        filtered_channel_info = filter_channel_info(channel_info_raw)

        # 3. Get all comments via pagination and perform sentiment analysis
        all_comments = await fetch_all_comments(client, video_id)

        # Assemble the final result
        result = {
            "video_id": video_id,
            "video_info": filtered_video_info,
            "channel_info": filtered_channel_info,
            "comments": all_comments
        }

    # Return the result as a downloadable JSON file
    response = JSONResponse(content=result)
    response.headers["Content-Disposition"] = "attachment; filename=video_details.json"
    return response
