import motor.motor_asyncio
from config import config

client = motor.motor_asyncio.AsyncIOMotorClient(config.MONGO_URI)
db = client.get_database() # Uses the database specified in the URI

async def init_db() -> None:
    # MongoDB creates collections lazily, but we can set up unique indexes here
    await db.check_ins.create_index(
        [("event_id", 1), ("user_id", 1)], 
        unique=True
    )