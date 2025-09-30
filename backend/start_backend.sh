#!/bin/bash
# Start PazPaz Backend Server
# Usage: ./start_backend.sh

set -e

cd "$(dirname "$0")"

echo "Starting PazPaz backend server..."
echo "Server will be available at: http://localhost:8000"
echo "API documentation: http://localhost:8000/docs"
echo ""

PYTHONPATH=src uv run uvicorn pazpaz.main:app --reload --host 0.0.0.0 --port 8000
