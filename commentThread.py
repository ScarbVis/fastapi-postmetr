import requests

def get_video_comments(api_key, video_id):
    """
    Ruft alle Kommentare (Top-Level und optional deren Antworten) 
    für ein gegebenes YouTube-Video ab.
    """

    # Endpoint für Kommentar-Threads (Top-Level-Kommentare)
    endpoint = "https://www.googleapis.com/youtube/v3/commentThreads"

    # Standard-Parameter für den ersten Request
    params = {
        "key": api_key,
        "part": "snippet",
        "videoId": video_id,
        "textFormat": "plainText",
        "maxResults": 100,  # maximal 100 pro Seite
        "order": "time"
    }

    all_comments = []

    while True:
        response = requests.get(endpoint, params=params)
        data = response.json()

        # Prüfen, ob die Anfrage erfolgreich war
        if response.status_code != 200:
            print(f"Fehler beim Abrufen: {data}")
            break

        # 'items' enthält die Kommentar-Threads
        items = data.get("items", [])

        for item in items:
            # An der "Snippet"-Ebene des Kommentar-Threads hängen Infos
            snippet = item.get("snippet", {})
            
            # Top-Level-Kommentar (eigentlicher Text)
            top_level_comment_data = snippet.get("topLevelComment", {}).get("snippet", {})
            author = top_level_comment_data.get("authorDisplayName", "Unbekannt")
            text = top_level_comment_data.get("textDisplay", "")
            published_at = top_level_comment_data.get("publishedAt", "N/A")

            all_comments.append({
                "author": author,
                "text": text,
                "published_at": published_at,
                "is_reply": False  # Kennzeichnung, dass es Top-Level ist
            })

            # Replies, falls vorhanden
            reply_count = snippet.get("totalReplyCount", 0)
            if reply_count > 0:
                # Top-Level-Kommentar-ID
                parent_id = item.get("snippet", {})\
                                .get("topLevelComment", {})\
                                .get("id", "")

                # Replies abrufen
                replies = get_comment_replies(api_key, parent_id)
                all_comments.extend(replies)

        # Gibt es noch weitere Seiten?
        if "nextPageToken" in data:
            params["pageToken"] = data["nextPageToken"]
        else:
            break

    return all_comments

def get_comment_replies(api_key, parent_id):
    """
    Holt alle Replies (Antworten) eines bestimmten Kommentar-Threads.
    """
    endpoint = "https://www.googleapis.com/youtube/v3/comments"
    params = {
        "key": api_key,
        "part": "snippet",
        "parentId": parent_id,
        "textFormat": "plainText",
        "maxResults": 100  # maximal 100 pro Seite
    }

    replies = []
    
    while True:
        response = requests.get(endpoint, params=params)
        data = response.json()

        # Prüfen, ob die Anfrage erfolgreich war
        if response.status_code != 200:
            print(f"Fehler beim Abrufen von Replies: {data}")
            break

        for item in data.get("items", []):
            snippet = item.get("snippet", {})
            author = snippet.get("authorDisplayName", "Unbekannt")
            text = snippet.get("textDisplay", "")
            published_at = snippet.get("publishedAt", "N/A")

            replies.append({
                "author": author,
                "text": text,
                "published_at": published_at,
                "is_reply": True
            })

        # Falls weitere Seiten existieren
        if "nextPageToken" in data:
            params["pageToken"] = data["nextPageToken"]
        else:
            break

    return replies

if __name__ == "__main__":
    API_KEY = "AIzaSyAg256OeOLt1nx5qqxvlZz8em-ZMZzg9Ko"
    VIDEO_ID = "gLVLTT-kNrw"

    comments = get_video_comments(API_KEY, VIDEO_ID)

    for idx, comment in enumerate(comments, start=1):
        typ = "Reply" if comment["is_reply"] else "Top-Level"
        print(f"{idx}. [{typ}] {comment['author']}:")
        print(f"   {comment['text']}")
        print(f"   (veröffentlicht am {comment['published_at']})\n")
