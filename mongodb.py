# mongodb.py

import os
import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get MongoDB connection info from environment variables
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "mydatabase")
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION", "records")

# Initialize the MongoDB client and select the database and collection
client = AsyncIOMotorClient(MONGO_URI)
db = client[MONGO_DB]
collection = db[MONGO_COLLECTION]

async def store_data(data: dict, processing_time: float) -> None:
    """
    Stores the provided data in the MongoDB collection, adding a processing time and timestamp.
    
    Args:
        data (dict): The data to be stored.
        processing_time (float): The time taken to process the data (in seconds).
    
    This extra processing_time field will only be stored in the database, not sent to the frontend.
    """
    # Create a copy of the data to store, so the original data for the frontend is not modified.
    data_to_store = data.copy()
    data_to_store["processing_time"] = processing_time
    data_to_store["stored_at"] = datetime.datetime.utcnow()
    
    # Insert the document into the MongoDB collection
    await collection.insert_one(data_to_store)
