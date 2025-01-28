# main.py
import os
import requests
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from youtube_comments import get_youtube_comments

# Replace with your valid YouTube Data API key, or load it from an environment variable
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "YOUR_API_KEY_HERE")

app = FastAPI()

# Allow CORS from any origin (for demo; limit in production!)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



@app.get("/comments")
def fetch_comments(video_id: str = Query(..., description="YouTube Video ID")):
    """
    API endpoint that calls get_youtube_comments(video_id)
    and returns the results in JSON format.
    """
    return get_youtube_comments(video_id)
