from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.core.database import Base


class ProvenanceManifest(Base):
    __tablename__ = "provenance_manifests"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    manifest_s3_key = Column(String, nullable=False)  # S3 location of the raw JSON manifest
    pipeline_version = Column(String, nullable=False)
    parameters = Column(JSON, nullable=True)  # Copy of runtime analysis parameters
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    document = relationship("Document", back_populates="analyses")
