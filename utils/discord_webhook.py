# Path: utils/discord_webhook.py

import os
import httpx
from datetime import datetime
from typing import Optional

# Get Discord webhook URL from environment
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

async def send_discord_webhook(
    video_name: str,
    comment_count: int,
    view_count: int,
    like_count: int,
    channel_name: str,
    subscriber_count: int,
    video_count: int,
    processing_time: float
) -> Optional[bool]:
    """
    Send a Discord webhook with YouTube video processing information.
    
    Args:
        video_name: Name of the processed video
        comment_count: Number of comments processed
        view_count: Number of views on the video
        like_count: Number of likes on the video
        channel_name: Name of the YouTube channel
        subscriber_count: Number of subscribers to the channel
        video_count: Total number of videos on the channel
        processing_time: Time taken to process the request in seconds
        
    Returns:
        True if webhook was sent successfully, False otherwise, None if no webhook URL
    """
    if not DISCORD_WEBHOOK_URL:
        print("Discord webhook URL not configured, skipping webhook")
        return None
    
    # Format numbers with commas for better readability
    def format_number(num: int) -> str:
        return f"{num:,}"
    
    # Create embed for Discord
    embed = {
        "title": "🎥 YouTube Video Processed",
        "description": f"**{video_name}**",
        "color": 0xFF0000,  # YouTube red
        "fields": [
            {
                "name": "📊 Video Stats",
                "value": f"**Comments:** {format_number(comment_count)}\n**Views:** {format_number(view_count)}\n**Likes:** {format_number(like_count)}",
                "inline": True
            },
            {
                "name": "📺 Channel Info",
                "value": f"**Channel:** {channel_name}\n**Subscribers:** {format_number(subscriber_count)}\n**Videos:** {format_number(video_count)}",
                "inline": True
            },
            {
                "name": "⏱️ Processing Time",
                "value": f"**{processing_time:.2f}** seconds",
                "inline": False
            }
        ],
        "timestamp": datetime.utcnow().isoformat(),
        "footer": {
            "text": "Social Data Extract API",
            "icon_url": "https://cdn.discordapp.com/attachments/1234567890/youtube-icon.png"
        }
    }
    
    # Discord webhook payload
    payload = {
        "embeds": [embed]
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(DISCORD_WEBHOOK_URL, json=payload)
            
            if response.status_code == 204:  # Discord webhook success
                print(f"Discord webhook sent successfully for video: {video_name}")
                return True
            else:
                print(f"Discord webhook failed with status {response.status_code}: {response.text}")
                return False
                
    except Exception as e:
        print(f"Error sending Discord webhook: {str(e)}")
        return False