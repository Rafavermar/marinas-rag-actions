"""MongoDB storage helpers."""
import hashlib
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from datetime import timezone

class MongoStorage:
    """Wrapper around Motor client for application collections."""

    def __init__(self, mongo_uri: str, db_name: str = "marinas") -> None:
        # tz_aware=True hace que los datetimes que vienen de Mongo tengan tzinfo
        self.client = AsyncIOMotorClient(mongo_uri, tz_aware=True, tzinfo=timezone.utc)
        self.db = self.client[db_name]
    async def ensure_indexes(self) -> None:
        await self.db.chunks.create_index([("content", "text")])
        await self.db.chunks.create_index([("marina_id", 1), ("created_at", -1)])
        await self.db.chunks.create_index([("marina_id", 1), ("content_hash", 1)], unique=True)
        await self.db.ingest_lock.create_index("locked_until", expireAfterSeconds=0)

    async def upsert_marina(self, marina: Dict[str, Any]) -> ObjectId:
        now = datetime.now(timezone.utc)
        result = await self.db.marinas.update_one(
            {"_id": marina["id"]},
            {
                "$set": {
                    "name": marina["name"],
                    "urls": marina["urls"],
                    "updated_at": now,
                }
            },
            upsert=True,
        )
        if result.upserted_id:
            return result.upserted_id
        return marina["id"]

    async def upsert_chunk(self, chunk: Dict[str, Any]) -> None:
        await self.db.chunks.update_one(
            {
                "marina_id": chunk["marina_id"],
                "content_hash": chunk["content_hash"],
            },
            {"$set": chunk},
            upsert=True,
        )

    async def search_chunks(self, query: str, marina_id: Optional[str], limit: int) -> List[Dict[str, Any]]:
        filter_query: Dict[str, Any] = {"$text": {"$search": query}}
        if marina_id:
            filter_query["marina_id"] = marina_id
        cursor = self.db.chunks.find(
            filter_query,
            {
                "score": {"$meta": "textScore"},
                "title": 1,
                "marina_id": 1,
                "source_url": 1,
                "kind": 1,
                "order": 1,
                "created_at": 1,
            },
        )
        cursor = cursor.sort([("score", {"$meta": "textScore"})]).limit(limit)
        results: List[Dict[str, Any]] = []
        async for doc in cursor:
            results.append(
                {
                    "id": str(doc.get("_id")),
                    "title": doc.get("title") or "",
                    "marina_id": doc.get("marina_id"),
                    "source_url": doc.get("source_url"),
                    "kind": doc.get("kind"),
                    "score": float(doc.get("score", 0.0)),
                }
            )
        return results

    async def fetch_chunks(self, ids: List[str]) -> List[Dict[str, Any]]:
        object_ids: List[ObjectId] = []
        for raw in ids:
            try:
                object_ids.append(ObjectId(raw))
            except Exception as exc:  # noqa: BLE001
                raise ValueError(f"Invalid id: {raw}") from exc
        cursor = self.db.chunks.find({"_id": {"$in": object_ids}})
        items: List[Dict[str, Any]] = []
        async for doc in cursor:
            items.append(
                {
                    "id": str(doc.get("_id")),
                    "title": doc.get("title") or "",
                    "content": doc.get("content", ""),
                    "source_url": doc.get("source_url", ""),
                    "metadata": {
                        "kind": doc.get("kind"),
                        "order": doc.get("order"),
                        "created_at": doc.get("created_at"),
                        "marina_id": doc.get("marina_id"),
                    },
                }
            )
        return items

    async def acquire_ingest_lock(self, lock_name: str, ttl_minutes: int = 120) -> bool:
        now = datetime.now(timezone.utc)
        locked_until = now + timedelta(minutes=ttl_minutes)
        existing = await self.db.ingest_lock.find_one({"_id": lock_name})
        if existing:
            expires = existing.get("locked_until")
            if expires and expires > now:
                return False
        await self.db.ingest_lock.update_one(
            {"_id": lock_name},
            {"$set": {"locked_until": locked_until}},
            upsert=True,
        )
        return True

    async def release_ingest_lock(self, lock_name: str) -> None:
        await self.db.ingest_lock.delete_one({"_id": lock_name})

    async def get_last_ingest(self, marina_id: Optional[str]) -> Optional[datetime]:
        filter_query: Dict[str, Any] = {"_id": marina_id or "global"}
        doc = await self.db.ingest_state.find_one(filter_query)
        if doc:
            return doc.get("last_ingest_at")
        return None

    async def update_last_ingest(self, marina_id: Optional[str], when: datetime) -> None:
        filter_query: Dict[str, Any] = {"_id": marina_id or "global"}
        await self.db.ingest_state.update_one(filter_query, {"$set": {"last_ingest_at": when}}, upsert=True)

    @staticmethod
    def hash_content(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()
