from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import httpx
import os

app = FastAPI()

# Load the API key from the environment variable "YOUTUBE_DATA_API_KEY"
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

def filter_comment(comment: dict) -> dict:
    snippet = comment.get("snippet", {})
    return {
        "id": comment.get("id"),
        "author": snippet.get("authorDisplayName"),
        "text": snippet.get("textDisplay"),
        "publishedAt": snippet.get("publishedAt"),
        "likeCount": snippet.get("likeCount")
    }

@app.get("/videos/{video_id}/details")
async def get_video_details(video_id: str):
    """
    Fetches filtered video details, channel information, and up to 100 top-level comments (with available replies)
    for the specified YouTube video. The response is returned as a downloadable JSON file.
    """
    async with httpx.AsyncClient() as client:
        # 1. Fetch video information
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
        video_info = video_data["items"][0]
        filtered_video_info = filter_video_info(video_info)
        
        # 2. Fetch channel information using the channelId from video info
        channel_id = video_info.get("snippet", {}).get("channelId")
        if not channel_id:
            raise HTTPException(status_code=404, detail="Channel ID not found in video information")
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
        channel_info = channel_data["items"][0]
        filtered_channel_info = filter_channel_info(channel_info)
        
        # 3. Fetch up to 100 top-level comments (with available replies) in one call
        comments_url = "https://www.googleapis.com/youtube/v3/commentThreads"
        comment_params = {
            "key": YOUTUBE_DATA_API_KEY,
            "textFormat": "plainText",
            "part": "snippet,replies",  # include replies if available
            "videoId": video_id,
            "maxResults": 100
        }
        comment_response = await client.get(comments_url, params=comment_params)
        if comment_response.status_code != 200:
            raise HTTPException(status_code=comment_response.status_code, detail="Error fetching comments")
        comment_data = comment_response.json()
        
        grouped_comments = []
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
            grouped_comments.append({
                "comment": filtered_top_comment,
                "replies": replies
            })
        
        # Assemble the final result
        result = {
            "video_id": video_id,
            "video_info": filtered_video_info,
            "channel_info": filtered_channel_info,
            "comments": grouped_comments
        }
    
    # Return the result as a downloadable JSON file
    response = JSONResponse(content=result)
    response.headers["Content-Disposition"] = "attachment; filename=video_details.json"
    return response
