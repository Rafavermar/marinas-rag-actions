"""Pydantic models for API requests and responses."""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"


class SearchRequest(BaseModel):
    query: str
    marina_id: Optional[str] = None
    k: Optional[int] = Field(default=5, ge=1, le=50)


class SearchResult(BaseModel):
    id: str
    title: str
    marina_id: str
    source_url: str
    kind: str
    score: float


class SearchResponse(BaseModel):
    results: List[SearchResult]


class FetchRequest(BaseModel):
    ids: List[str]


class FetchItem(BaseModel):
    id: str
    title: str
    content: str
    source_url: str
    metadata: dict


class FetchResponse(BaseModel):
    items: List[FetchItem]


class IngestRequest(BaseModel):
    marina_id: Optional[str] = None


class IngestResponse(BaseModel):
    status: str
    started_at: Optional[datetime] = None
    last_ingest_at: Optional[datetime] = None
