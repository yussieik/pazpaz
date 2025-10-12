# Development Authentication Guide

Quick reference for authenticating in development mode.

## Prerequisites

1. **Docker containers running:**
   ```bash
   docker-compose up -d
   ```

2. **Backend API running:**
   ```bash
   cd backend
   PYTHONPATH=src uv run uvicorn pazpaz.main:app --reload
   ```
   Backend will be available at: http://localhost:8000

3. **MailHog UI accessible:**
   - Web UI: http://localhost:8025
   - SMTP: localhost:1025

## Quick Start (3 Steps)

### Step 1: Seed Test Users

Create test workspace and users (only needed once):

```bash
cd backend
PYTHONPATH=src uv run python seed_dev_data.py
```

This creates:
- **Test Workspace**: "Test Workspace"
- **Owner User**: test@example.com
- **Assistant User**: assistant@example.com

### Step 2: Request Magic Link

Request a magic link for login:

```bash
cd backend
PYTHONPATH=src uv run python dev_login.py
```

Or for the assistant user:

```bash
PYTHONPATH=src uv run python dev_login.py assistant@example.com
```

### Step 3: Get Magic Link from MailHog

1. Open MailHog UI: http://localhost:8025
2. Find the email sent to your test user
3. Click the magic link in the email
4. You'll be redirected and logged in automatically

**Done!** Your JWT token is now stored in an HttpOnly cookie.

## Common Scenarios

### First Time Setup

```bash
# 1. Start Docker services
docker-compose up -d

# 2. Wait for services to be healthy (10-15 seconds)
docker-compose ps

# 3. Run database migrations
cd backend
PYTHONPATH=src uv run alembic upgrade head

# 4. Seed test users
PYTHONPATH=src uv run python seed_dev_data.py

# 5. Start backend
PYTHONPATH=src uv run uvicorn pazpaz.main:app --reload

# 6. Request magic link
PYTHONPATH=src uv run python dev_login.py

# 7. Open MailHog and click the magic link
open http://localhost:8025
```

### Daily Development Workflow

```bash
# Start services (if not already running)
docker-compose up -d

# Start backend
cd backend
PYTHONPATH=src uv run uvicorn pazpaz.main:app --reload

# Start frontend (in another terminal)
cd frontend
npm run dev

# Request magic link when needed
cd backend
PYTHONPATH=src uv run python dev_login.py

# Open MailHog to get the link
open http://localhost:8025
```

### Creating Additional Test Users

You can manually create users by modifying `seed_dev_data.py` or using the database directly:

```python
# Add to seed_dev_data.py:
new_user = User(
    id=uuid.uuid4(),
    workspace_id=workspace.id,
    email="therapist2@example.com",
    full_name="Second Therapist",
    role=UserRole.THERAPIST,
    is_active=True,
)
session.add(new_user)
```

## Testing with Different Users

```bash
# Login as owner (default)
PYTHONPATH=src uv run python dev_login.py

# Login as assistant
PYTHONPATH=src uv run python dev_login.py assistant@example.com

# Login as custom user
PYTHONPATH=src uv run python dev_login.py therapist2@example.com
```

## Magic Link Details

- **Token Length**: 32 bytes (256 bits of entropy)
- **Token Expiry**: 10 minutes
- **Single Use**: Tokens are deleted after successful verification
- **Rate Limit**: 3 requests per hour per IP address
- **Security**: Tokens stored in Redis with automatic expiration

## JWT Token Details

After clicking the magic link:
- **Storage**: HttpOnly cookie (XSS protection)
- **Expiry**: 7 days
- **Contents**: user_id, workspace_id, email, role
- **Cookie Name**: `access_token`
- **SameSite**: Lax (CSRF protection)

## Troubleshooting

### "Could not connect to backend API"

Backend is not running. Start it:
```bash
cd backend
PYTHONPATH=src uv run uvicorn pazpaz.main:app --reload
```

### "Rate limit exceeded"

You've requested too many magic links. Wait 1 hour or clear Redis:
```bash
docker-compose exec redis redis-cli -a your_redis_password FLUSHALL
```

### No email in MailHog

1. Check MailHog is running: `docker-compose ps`
2. Check backend logs for email sending errors
3. Verify user exists: `PYTHONPATH=src uv run python seed_dev_data.py`

### User doesn't exist

Run the seed script again:
```bash
cd backend
PYTHONPATH=src uv run python seed_dev_data.py
```

### Database doesn't exist

Create it manually:
```bash
docker-compose exec db psql -U pazpaz -c "CREATE DATABASE pazpaz;"
```

Then run migrations:
```bash
cd backend
PYTHONPATH=src uv run alembic upgrade head
```

## MailHog Features

- **Web UI**: http://localhost:8025
- **View all emails**: Sent during development
- **Search**: Find emails by recipient or subject
- **Delete**: Clear all emails
- **No actual email sending**: Everything stays local

## Security Notes (Development Only)

⚠️ **These scripts are for DEVELOPMENT ONLY**

- No password required (magic link only)
- MailHog captures all emails (nothing sent externally)
- Redis password is simple (not production-safe)
- Database credentials are simple (not production-safe)

In production:
- Users register with proper onboarding
- Emails sent via real SMTP (e.g., SendGrid, AWS SES)
- Redis and database have strong passwords
- All traffic over HTTPS with proper certificates

## Example Output

### seed_dev_data.py
```
✅ Test workspace already exists
   Workspace ID: 11111111-1111-1111-1111-111111111111
✅ Test user already exists
   Email: test@example.com
   User ID: 22222222-2222-2222-2222-222222222222
✅ Assistant user already exists
   Email: assistant@example.com
   User ID: 33333333-3333-3333-3333-333333333333

================================================================================
🎉 Development data seeded successfully!
================================================================================

You can now use dev_login.py to request a magic link:
   PYTHONPATH=src uv run python dev_login.py

Test users created:
   • test@example.com (Owner)
   • assistant@example.com (Assistant)

MailHog UI: http://localhost:8025
================================================================================
```

### dev_login.py
```
================================================================================
🔐 Requesting magic link for: test@example.com
================================================================================

✅ Magic link request sent!

📧 Next steps:
   1. Open MailHog UI: http://localhost:8025
   2. Find the email sent to: test@example.com
   3. Click the magic link in the email
   4. You'll be redirected and logged in automatically

💡 Tip: MailHog catches all emails sent in development
================================================================================
```

## API Endpoints Used

- **POST /api/v1/auth/magic-link**: Request magic link
- **GET /api/v1/auth/verify?token=...**: Verify token and get JWT
- **POST /api/v1/auth/logout**: Logout (blacklist JWT)

## Next Steps

Once authenticated, you can:
1. Access the frontend: http://localhost:5173
2. Make API requests with your JWT cookie
3. Test workspace isolation
4. Create clients, appointments, and SOAP notes

---

**Quick Reference:**
```bash
# One-time setup
PYTHONPATH=src uv run python seed_dev_data.py

# Daily login
PYTHONPATH=src uv run python dev_login.py
open http://localhost:8025
```
