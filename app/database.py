from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings

client = AsyncIOMotorClient(settings.mongo_uri)
db = client[settings.mongo_db_name]

users_collection = db["users"]
sessions_collection = db["sessions"]


async def ensure_indexes():
    """Se llama una vez al arrancar la app (ver main.py)."""
    await users_collection.create_index("email", unique=True)
    await sessions_collection.create_index("session_id", unique=True)
    # TTL de respaldo: si una sesion queda huerfana, Mongo la borra sola
    # a las 24h (mismo valor que la expiracion dura del JWT).
    await sessions_collection.create_index("created_at", expireAfterSeconds=60 * 60 * 24)
