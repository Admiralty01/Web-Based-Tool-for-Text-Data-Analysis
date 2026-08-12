from celery import Celery
from app.core.config import settings

# Initialize Celery app
celery_app = Celery(
    "text_analysis_tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

# Apply settings
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    imports=["app.tasks.analysis_tasks"],
)
