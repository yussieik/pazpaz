# PazPaz Quick Start

## Prerequisites

- Docker & Docker Compose (for PostgreSQL)
- Python 3.13.5 with `uv` installed
- Node.js 20.11+ with `npm`

## Start Development Servers

### Backend Startup

**Using startup script:**
```bash
cd backend
./start_backend.sh
```

**Manual command:**

```bash
cd backend
PYTHONPATH=src uv run uvicorn pazpaz.main:app --reload --host 0.0.0.0 --port 8000
```

Backend will be available at:
- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- OpenAPI: http://localhost:8000/api/v1/openapi.json

### Frontend Startup

```bash
cd frontend
npm run dev
```

Frontend will be available at: http://localhost:5173

## Database Setup

If this is your first time running the project:

```bash
cd backend

# Start PostgreSQL (Docker)
docker compose up -d db

# Run migrations
uv run alembic upgrade head

# (Optional) Create test data
PYTHONPATH=src uv run python create_test_workspace.py
```

## Regenerate API Client

After backend API changes:

```bash
cd frontend
npm run generate-api
```

## Run Tests

```bash
cd backend
PYTHONPATH=src uv run pytest tests/ -v
```

## Troubleshooting

### Backend: ModuleNotFoundError: No module named 'pazpaz'
**Solution:** Always set `PYTHONPATH=src` when running backend commands, or use the startup script.

### Frontend: Type errors after backend changes
**Solution:** Regenerate the API client types: `cd frontend && npm run generate-api`

### Database connection errors
**Solution:** Ensure Docker PostgreSQL is running: `cd backend && docker compose up -d db`

### Port already in use
**Solution:**
- Backend (8000): Check if another process is using port 8000
- Frontend (5173): Check if another Vite dev server is running
- PostgreSQL (5432): Ensure local PostgreSQL is not running (use cleanup_local_postgres.sh if needed)
