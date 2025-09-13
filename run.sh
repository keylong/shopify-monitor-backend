#!/bin/bash

# Shopify Monitor API Startup Script

echo "🚀 Starting Shopify Monitor API..."

# Create logs directory if it doesn't exist
mkdir -p logs

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Run database migrations (if using alembic)
# alembic upgrade head

# Start the application
if [ "$ENVIRONMENT" = "production" ]; then
    echo "Starting in production mode..."
    uvicorn app.main:app \
        --host $HOST \
        --port $PORT \
        --workers $WORKERS \
        --log-level ${LOG_LEVEL,,}
else
    echo "Starting in development mode..."
    uvicorn app.main:app \
        --host $HOST \
        --port $PORT \
        --reload \
        --log-level ${LOG_LEVEL,,}
fi