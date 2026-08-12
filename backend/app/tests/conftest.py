import os
from typing import Generator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import MagicMock, patch

# Force test configuration
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://mock:6379/0"
os.environ["ELASTICSEARCH_HOST"] = "http://mock:9200"
os.environ["S3_BUCKET_NAME"] = "test-bucket"

from app.core.database import Base, get_db
from app.main import app

# In-memory SQLite for isolated, fast testing
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Create database tables in the in-memory database."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db() -> Generator:
    """Provide a clean database session for each test, rolling back changes afterward."""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(autouse=True)
def override_db_dependency(db):
    """Override the FastAPI database dependency for all router calls."""
    def get_test_db():
        yield db
    app.dependency_overrides[get_db] = get_test_db
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Provide a FastAPI TestClient."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def mock_external_services():
    """Globally mock S3, Elasticsearch, and Celery tasks to prevent external network requests."""
    # 1. Mock S3 Service
    with patch("app.core.s3.s3_service.s3_client") as mock_s3_client, \
         patch("app.core.s3.s3_service.ensure_bucket_exists") as mock_ensure:
        
        # Setup mock behavior
        mock_s3_client.get_object.return_value = {
            "Body": MagicMock(read=lambda: b"Mock text data for natural language processing testing.")
        }
        mock_s3_client.generate_presigned_url.return_value = "http://mock-s3-presigned-url/key"
        
        # 2. Mock Elasticsearch client and service
        with patch("app.core.elasticsearch.es_service.client") as mock_es_client:
            mock_es_client.indices.exists.return_value = True
            mock_es_client.search.return_value = {
                "hits": {
                    "hits": [
                        {
                            "_score": 1.5,
                            "_source": {
                                "document_id": "1",
                                "title": "Test File",
                                "content": "Mock text content",
                                "clean_content": "mock text content",
                            }
                        }
                    ]
                }
            }
            
            # 3. Mock Celery task dispatch
            with patch("app.tasks.analysis_tasks.run_nlp_and_representation_pipeline.delay") as mock_task:
                mock_task.return_value = MagicMock(id="mock-task-uuid-1234", status="PENDING")
                
                yield {
                    "s3_client": mock_s3_client,
                    "es_client": mock_es_client,
                    "celery_delay": mock_task
                }
