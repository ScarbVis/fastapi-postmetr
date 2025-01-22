import requests
import os
from dotenv import load_dotenv

load_dotenv()

# Simple global usage counters
api_usage = {
    "commentThreads_calls": 0,
    "comments_calls": 0
}

def get_video_comments_with_conditional_replies(api_key, video_id):
    """
    Retrieve all top-level comments from a YouTube video using the 'commentThreads' endpoint.
    Fetch up to 5 replies for each top-level comment from the same call.
    If totalReplyCount is more than those 5 replies, fetch the remaining replies 
    via the 'comments' endpoint (in get_remaining_replies).
    """
    endpoint = "https://www.googleapis.com/youtube/v3/commentThreads"
    params = {
        "key": api_key,
        "part": "snippet,replies",
        "videoId": video_id,
        "textFormat": "plainText",
        "maxResults": 100,
        "order": "time"
    }

    all_comments = []

    while True:
        # Count this call
        api_usage["commentThreads_calls"] += 1
        
        response = requests.get(endpoint, params=params)
        data = response.json()

        if response.status_code != 200:
            print(f"Error fetching commentThreads: {data}")
            break

        items = data.get("items", [])

        for item in items:
            snippet = item.get("snippet", {})
            top_level_comment = snippet.get("topLevelComment", {})
            top_level_snippet = top_level_comment.get("snippet", {})

            # Top-level comment info
            author = top_level_snippet.get("authorDisplayName", "Unknown")
            text = top_level_snippet.get("textDisplay", "")
            published_at = top_level_snippet.get("publishedAt", "N/A")
            total_reply_count = snippet.get("totalReplyCount", 0)
            parent_comment_id = top_level_comment.get("id")

            # Add the top-level comment
            all_comments.append({
                "author": author,
                "text": text,
                "published_at": published_at,
                "is_reply": False
            })

            # Grab the (up to 5) replies included in the current response
            existing_replies = item.get("replies", {}).get("comments", [])
            for reply_item in existing_replies:
                reply_snippet = reply_item.get("snippet", {})
                r_author = reply_snippet.get("authorDisplayName", "Unknown")
                r_text = reply_snippet.get("textDisplay", "")
                r_published_at = reply_snippet.get("publishedAt", "N/A")

                all_comments.append({
                    "author": r_author,
                    "text": r_text,
                    "published_at": r_published_at,
                    "is_reply": True
                })

            # If the totalReplyCount is more than the (up to) 5 we already got, fetch the rest
            if total_reply_count > len(existing_replies):
                extra_replies = get_remaining_replies(api_key, parent_comment_id)
                all_comments.extend(extra_replies)

        # Paginate if there's a next page
        next_page_token = data.get("nextPageToken")
        if next_page_token:
            params["pageToken"] = next_page_token
        else:
            break

    return all_comments


def get_remaining_replies(api_key, parent_id):
    """
    Fetch additional replies (beyond the 5 included in the 'commentThreads' call) 
    for a given top-level comment. Uses the 'comments' endpoint, paginated if needed.
    """
    endpoint = "https://www.googleapis.com/youtube/v3/comments"
    params = {
        "key": api_key,
        "part": "snippet",
        "parentId": parent_id,
        "textFormat": "plainText",
        "maxResults": 100
    }

    all_replies = []
    while True:
        # Count this call
        api_usage["comments_calls"] += 1
        
        response = requests.get(endpoint, params=params)
        data = response.json()

        if response.status_code != 200:
            print(f"Error fetching remaining replies: {data}")
            break

        for item in data.get("items", []):
            reply_snippet = item.get("snippet", {})
            author = reply_snippet.get("authorDisplayName", "Unknown")
            text = reply_snippet.get("textDisplay", "")
            published_at = reply_snippet.get("publishedAt", "N/A")

            all_replies.append({
                "author": author,
                "text": text,
                "published_at": published_at,
                "is_reply": True
            })

        # Check for a next page
        next_page_token = data.get("nextPageToken")
        if next_page_token:
            params["pageToken"] = next_page_token
        else:
            break

    return all_replies


if __name__ == "__main__":
    API_KEY = os.getenv("GOOGLE_API_KEY")
    VIDEO_ID = "gLVLTT-kNrw"

    comments = get_video_comments_with_conditional_replies(API_KEY, VIDEO_ID)

    # Print all comments
    for idx, comment in enumerate(comments, start=1):
        ctype = "Reply" if comment["is_reply"] else "Top-Level"
        print(f"{idx}. [{ctype}] {comment['author']}:")
        print(f"   {comment['text']}")
        print(f"   (published at {comment['published_at']})\n")

    # Show total usage
    print("=== API Usage Summary ===")
    print(f"commentThreads endpoint calls: {api_usage['commentThreads_calls']}")
    print(f"comments endpoint calls      : {api_usage['comments_calls']}")
    total_calls = api_usage["commentThreads_calls"] + api_usage["comments_calls"]
    print(f"Total API calls used         : {total_calls}")
