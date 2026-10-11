from pymongo import MongoClient
from app.core.config import settings

_client = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(settings.mongo_uri, tz_aware=True, serverSelectionTimeoutMS=5000)
    return _client


def get_db():
    return get_client()[settings.mongo_db]
