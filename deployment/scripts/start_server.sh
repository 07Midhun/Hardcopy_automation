#!/usr/bin/env bash
set -e

echo "Starting AI Document Intelligence Web Server..."
python -m gunicorn --bind 0.0.0.0:5000 --workers 4 --timeout 180 backend.wsgi:app

