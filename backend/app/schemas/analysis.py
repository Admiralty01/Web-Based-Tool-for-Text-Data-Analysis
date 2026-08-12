from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class AnalysisTrigger(BaseModel):
    lda_topics: int = Field(default=5, ge=2, le=50, description="Number of topics for LDA")
    ngram_range_min: int = Field(default=1, ge=1, le=3, description="Minimum n-gram value")
    ngram_range_max: int = Field(default=2, ge=1, le=3, description="Maximum n-gram value")
    generate_dense_embeddings: bool = Field(default=True, description="Whether to extract dense embeddings")
    random_seed: int = Field(default=42, description="Seed for reproducibility")


class AnalysisStatusResponse(BaseModel):
    task_id: str
    status: str
    document_id: int
    created_at: datetime


class ProvenanceManifestOut(BaseModel):
    id: int
    document_id: int
    manifest_s3_key: str
    pipeline_version: str
    parameters: Optional[Dict[str, Any]] = None
    created_at: datetime
    manifest_url: str  # Pre-signed S3 URL to download the full manifest JSON directly

    class Config:
        from_attributes = True
