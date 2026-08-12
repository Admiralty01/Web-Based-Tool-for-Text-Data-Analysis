from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    owner = relationship("User")
    documents = relationship("Document", back_populates="project", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    s3_key = Column(String, nullable=False)  # Key for raw text stored in S3
    status = Column(String, default="uploaded", nullable=False)  # "uploaded", "processing", "ready", "failed"
    error_message = Column(String, nullable=True)
    
    # Text profile metadata set during preprocessing
    language = Column(String, nullable=True)
    char_count = Column(Integer, nullable=True)
    word_count = Column(Integer, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    project = relationship("Project", back_populates="documents")
    analyses = relationship("ProvenanceManifest", back_populates="document", cascade="all, delete-orphan")
