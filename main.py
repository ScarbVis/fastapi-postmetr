from typing import Union
from fastapi import FastAPI, Query
import os
from dotenv import load_dotenv
from commentThread import get_video_comments
import sentry_sdk
from sentry_sdk.integrations.asgi import SentryAsgiMiddleware

sentry_sdk.init(
    dsn=os.getenv('SENTRY_KEY'),
    traces_sample_rate=1.0
)

app = FastAPI()
app.add_middleware(SentryAsgiMiddleware)

@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/items/{item_id}")
def read_item(item_id: int, q: Union[str, None] = None):
    return {"item_id": item_id, "q": q}

@app.get("/youtube")
def read_comments(video_id: str = Query(...)):
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        return {"error": "API key not found in environment variables."}
    
    comments = get_video_comments(api_key, video_id)
    return {"comments": comments}
