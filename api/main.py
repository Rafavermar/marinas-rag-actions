"""FastAPI application exposing ingestion and search endpoints."""
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient

from api.auth import verify_admin_token
from api.models import (
    FetchRequest,
    FetchResponse,
    HealthResponse,
    IngestRequest,
    IngestResponse,
    SearchRequest,
    SearchResponse,
)
from api.storage_mongo import MongoStorage
from ingest.ingest_runner import run_ingest

load_dotenv()

app = FastAPI(title="Marinas RAG Actions")


async def get_storage() -> MongoStorage:
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="MONGO_URI not configured")
    storage = MongoStorage(mongo_uri)
    await storage.ensure_indexes()
    return storage


@app.on_event("startup")
async def startup_event() -> None:
    mongo_uri = os.getenv("MONGO_URI")
    if mongo_uri:
        client = AsyncIOMotorClient(mongo_uri)
        await client.server_info()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse()


@app.post("/search", response_model=SearchResponse)
async def search(payload: SearchRequest, storage: MongoStorage = Depends(get_storage)) -> SearchResponse:
    results = await storage.search_chunks(payload.query, payload.marina_id, payload.k or 5)
    return SearchResponse(results=results)


@app.post("/fetch", response_model=FetchResponse)
async def fetch(payload: FetchRequest, storage: MongoStorage = Depends(get_storage)) -> FetchResponse:
    try:
        items = await storage.fetch_chunks(payload.ids)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return FetchResponse(items=items)


async def ingest_guard(storage: MongoStorage, marina_id: Optional[str]) -> Tuple[bool, Optional[datetime]]:
    last_ingest = await storage.get_last_ingest(marina_id)
    if not last_ingest:
        return False, None

    # Mongo puede devolver datetime "naive" (sin tzinfo). Normalizamos a UTC.
    if last_ingest.tzinfo is None:
        last_ingest = last_ingest.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)

    if now - last_ingest < timedelta(days=14):
        return True, last_ingest

    return False, last_ingest


@app.post("/admin/ingest", response_model=IngestResponse, dependencies=[Depends(verify_admin_token)])
async def admin_ingest(
    payload: IngestRequest,
    background_tasks: BackgroundTasks,
    storage: MongoStorage = Depends(get_storage),
) -> IngestResponse:
    marina_id = payload.marina_id
    should_skip = False
    last_ingest = None

    if not payload.force:
        should_skip, last_ingest = await ingest_guard(storage, marina_id)

    if should_skip:
        return IngestResponse(status="skipped", last_ingest_at=last_ingest)

    lock_name = f"ingest-{marina_id or 'all'}"
    acquired = await storage.acquire_ingest_lock(lock_name)
    if not acquired:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="ingest already running")

    started_at = datetime.now(timezone.utc)

    async def _run() -> None:
        try:
            await run_ingest(storage, marina_id)
            await storage.update_last_ingest(marina_id, datetime.now(timezone.utc))
        finally:
            await storage.release_ingest_lock(lock_name)

    background_tasks.add_task(_run)
    return IngestResponse(status="started", started_at=started_at)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api.main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8080")), reload=False)
