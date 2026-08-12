from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Text Analysis and Visualization Platform"
    API_V1_STR: str = "/api/v1"
    
    # JWT Auth Configuration
    JWT_SECRET: str = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    
    # Relational Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/text_analysis"
    
    # Redis Broker/Cache
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Elasticsearch / Vector Store
    ELASTICSEARCH_HOST: str = "http://localhost:9200"
    
    # S3 Object Storage Settings
    S3_ENDPOINT_URL: Optional[str] = None  # None for real AWS S3, set for MinIO
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET_NAME: str = "text-analysis-artifacts"
    S3_REGION: str = "us-east-1"
    
    # Configurations configuration
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8", 
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()
