# PazPaz Backend

FastAPI-based backend for PazPaz practice management application.

## Setup

1. Install Python 3.13.5:
```bash
uv python install 3.13.5
uv python pin 3.13.5
```

2. Install dependencies:
```bash
uv sync
```

3. Configure environment:
```bash
cp .env.example .env
# Edit .env with your settings
```

## Development

Run the development server:
```bash
uv run fastapi dev src/pazpaz/main.py
```

Run tests:
```bash
uv run pytest
```

Lint and format:
```bash
uv run ruff check --fix
uv run ruff format
```

## Project Structure

```
backend/
├── src/pazpaz/
│   ├── api/          # API route handlers
│   ├── core/         # Core configuration
│   ├── db/           # Database setup
│   ├── models/       # SQLAlchemy models
│   ├── schemas/      # Pydantic schemas
│   ├── services/     # Business logic
│   └── main.py       # FastAPI app entry point
└── tests/            # Test suite
```