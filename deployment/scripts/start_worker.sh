#!/usr/bin/env bash
set -e

echo "Starting Celery Background Processing Worker..."
celery -A backend.app.tasks.celery_app.celery_app worker --loglevel=info --concurrency=4

