import logging

from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings

logger = logging.getLogger("si-backend")

client = AsyncIOMotorClient(settings.mongo_uri)
db = client[settings.mongo_db_name]

users_collection = db["users"]
sessions_collection = db["sessions"]
login_history_collection = db["login_history"]
conversations_collection = db["conversations"]
messages_collection = db["messages"]


async def _safe_create_index(collection, *args, **kwargs):
    """Crea un indice sin tumbar el arranque de la app si Mongo lo rechaza
    (por ejemplo, por falta de espacio en disco en un plan gratuito de Railway).
    La app sigue funcionando sin ese indice hasta que se pueda crear."""
    try:
        await collection.create_index(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "No se pudo crear el indice %s en %s: %s. "
            "La app sigue arrancando, pero revisa el espacio en disco de Mongo.",
            args,
            collection.name,
            exc,
        )


async def ensure_indexes():
    """Se llama una vez al arrancar la app (ver main.py)."""
    await _safe_create_index(users_collection, "email", unique=True)
    await _safe_create_index(sessions_collection, "session_id", unique=True)
    # TTL de respaldo: si una sesion queda huerfana, Mongo la borra sola
    # a las 24h (mismo valor que la expiracion dura del JWT).
    await _safe_create_index(sessions_collection, "created_at", expireAfterSeconds=60 * 60 * 24)

    # Historial de logeos: nunca se borra automaticamente (es auditoria).
    # Indices para poder consultar rapido por usuario o por fecha.
    await _safe_create_index(login_history_collection, [("email", 1), ("timestamp", -1)])
    await _safe_create_index(login_history_collection, "timestamp")

    # Conversaciones y mensajes: consultas frecuentes por conversation_id y por usuario.
    await _safe_create_index(conversations_collection, "conversation_id", unique=True)
    await _safe_create_index(conversations_collection, [("user_id", 1), ("project_id", 1)])
    await _safe_create_index(messages_collection, [("conversation_id", 1), ("created_at", 1)])
