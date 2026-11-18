"""
Celery configuration and application factory integrated with Flask app context.
"""
import os
from celery import Celery


def make_celery(app=None):
    """Factory to create and configure Celery instance."""
    always_eager = False
    if app:
        broker = app.config.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
        backend = app.config.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
        always_eager = app.config.get("CELERY_ALWAYS_EAGER", False)
    else:
        broker = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
        backend = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
        always_eager = os.getenv("CELERY_ALWAYS_EAGER", "False").lower() in ("true", "1", "yes")

    celery_instance = Celery(
        "ai_document_intelligence",
        broker=broker,
        backend=backend,
        include=[
            "backend.app.tasks.upload_tasks",
            "backend.app.tasks.processing_tasks",
            "backend.app.tasks.retry_tasks",
            "backend.app.tasks.export_tasks"
        ]
    )

    celery_instance.conf.update(
        task_always_eager=always_eager,
        task_eager_propagates=True,
        broker_connection_retry_on_startup=False,
        broker_connection_max_retries=1,
        broker_transport_options={"max_retries": 1, "socket_timeout": 2},
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
    )

    if app:
        celery_instance.conf.task_always_eager = app.config.get("CELERY_ALWAYS_EAGER", False)
        class ContextTask(celery_instance.Task):
            def __call__(self, *args, **kwargs):
                with app.app_context():
                    return self.run(*args, **kwargs)

        celery_instance.Task = ContextTask

    return celery_instance


celery_app = make_celery()
