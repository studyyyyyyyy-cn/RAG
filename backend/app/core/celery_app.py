"""Celery application for background task processing.

Used for async document chunking/embedding to avoid blocking the web server.
"""
from celery import Celery

from app.config import settings

celery_app = Celery(
    "ragapp",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# Auto-discover tasks (future: app.core.tasks module)
# celery_app.autodiscover_tasks(["app.core.tasks"])
