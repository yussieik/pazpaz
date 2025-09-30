#!/bin/bash
# Start PazPaz Frontend Dev Server
# Usage: ./start_frontend.sh

set -e

cd "$(dirname "$0")"

echo "Starting PazPaz frontend dev server..."
echo "Frontend will be available at: http://localhost:5173"
echo ""

npm run dev
