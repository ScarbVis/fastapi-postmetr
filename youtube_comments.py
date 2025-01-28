import requests
import os

# Replace with your valid YouTube Data API key, or load it from an environment variable
YOUTUBE_API_KEY = os.getenv("YOUTUBE_DATA_API_KEY", "YOUR_API_KEY_HERE")

def get_youtube_comments(video_id: str) -> dict:
    """
    Fetch comments for the given YouTube video_id using the YouTube Data API.
    Returns a dictionary with either:
      {"comments": [...]} or {"error": "..."}
    """
    if not YOUTUBE_API_KEY or YOUTUBE_API_KEY == "YOUR_API_KEY_HERE":
        return {"error": "You must provide a valid YouTube Data API key."}

    # Build the request URL for the YouTube commentThreads endpoint
    url = (
        "https://www.googleapis.com/youtube/v3/commentThreads"
        f"?part=snippet&videoId={video_id}&key={YOUTUBE_API_KEY}"
    )

    response = requests.get(url)
    data = response.json()

    # Basic error handling
    if response.status_code != 200:
        return {"error": data.get("error", {}).get("message", "Error fetching comments")}

    # Extract comment authors and texts
    comments_list = []
    for item in data.get("items", []):
        snippet = item["snippet"]["topLevelComment"]["snippet"]
        author = snippet.get("authorDisplayName")
        comment_text = snippet.get("textDisplay")
        comments_list.append({
            "author": author,
            "comment": comment_text
        })

    return {"comments": comments_list}