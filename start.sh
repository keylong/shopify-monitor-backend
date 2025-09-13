#!/bin/bash

# Leapcell startup script

# Set default values if not provided
export HOST=${HOST:-0.0.0.0}
export PORT=${PORT:-8000}

echo "Starting Shopify Monitor API on $HOST:$PORT"

# Start uvicorn with proper settings
exec uvicorn app.main:app \
    --host $HOST \
    --port $PORT \
    --workers 1 \
    --log-level info \
    --access-log