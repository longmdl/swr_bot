from typing import List, Optional, Tuple, Dict, Any
from uuid import UUID
from datetime import datetime
from pymongo.errors import PyMongoError
import logging
from bson.objectid import ObjectId

from db.connection import db

logger = logging.getLogger(__name__)

class BotRepository:
    
    @staticmethod
    async def create_swr_event(event_data: Dict[str, Any]) -> str:
        """
        Creates a new SWR event and an empty attendance record.
        """
        try:
            # Insert the main event document
            result = await db.events.insert_one(event_data)
            event_id = str(result.inserted_id)
            
            # Initialize empty attendance record for this event
            await db.attendance.insert_one({
                "event_id": event_id,
                "attending_users": [],
                "absent_users": []
            })
            
            return event_id
        except PyMongoError as e:
            logger.error(f"Database error during create_swr_event: {e}")
            raise

    @staticmethod
    async def get_swr_event(event_id: str) -> Optional[Dict[str, Any]]:
        try:
            return await db.events.find_one({"_id": ObjectId(event_id)})
        except PyMongoError as e:
            logger.error(f"Database error during get_swr_event: {e}")
            return None

    @staticmethod
    async def get_all_active_swr_events() -> List[str]:
        try:
            cursor = db.events.find({"status": "active"})
            return [str(doc["_id"]) async for doc in cursor]
        except PyMongoError as e:
            logger.error(f"Database error during get_all_active_swr_events: {e}")
            return []

    @staticmethod
    async def update_attendance(event_id: str, user_id: int, status: str) -> Tuple[List[int], List[int]]:
        """
        Atomically updates the attendance record using $addToSet and $pull.
        status should be 'attending' or 'absent'.
        Returns a tuple of (attending_users, absent_users).
        """
        try:
            if status == "attending":
                update_query = {
                    "$addToSet": {"attending_users": user_id},
                    "$pull": {"absent_users": user_id}
                }
            elif status == "absent":
                update_query = {
                    "$addToSet": {"absent_users": user_id},
                    "$pull": {"attending_users": user_id}
                }
            else:
                raise ValueError("Invalid status. Must be 'attending' or 'absent'.")

            # Perform the atomic update and return the NEW document
            from pymongo import ReturnDocument
            updated_doc = await db.attendance.find_one_and_update(
                {"event_id": event_id},
                update_query,
                return_document=ReturnDocument.AFTER
            )
            
            if not updated_doc:
                raise ValueError(f"Attendance record for event {event_id} not found.")
                
            return updated_doc.get("attending_users", []), updated_doc.get("absent_users", [])
            
        except PyMongoError as e:
            logger.error(f"Database error during update_attendance: {e}")
            raise
        
    @staticmethod
    async def get_attendance(event_id: str) -> Tuple[List[int], List[int]]:
        try:
            doc = await db.attendance.find_one({"event_id": event_id})
            if doc:
                return doc.get("attending_users", []), doc.get("absent_users", [])
            return [], []
        except PyMongoError as e:
            logger.error(f"Database error during get_attendance: {e}")
            return [], []