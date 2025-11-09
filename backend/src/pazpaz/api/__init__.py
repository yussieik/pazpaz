"""API routes."""

from fastapi import APIRouter

from pazpaz.api.ai_agent import router as ai_agent_router
from pazpaz.api.appointments import router as appointments_router
from pazpaz.api.audit import router as audit_router
from pazpaz.api.auth import router as auth_router
from pazpaz.api.client_attachments import router as client_attachments_router
from pazpaz.api.clients import router as clients_router
from pazpaz.api.google_calendar_integration import (
    router as google_calendar_integration_router,
)
from pazpaz.api.locations import router as locations_router
from pazpaz.api.notification_settings import router as notification_settings_router
from pazpaz.api.payments import router as payments_router
from pazpaz.api.platform_admin import router as platform_admin_router
from pazpaz.api.services import router as services_router
from pazpaz.api.session_attachments import router as session_attachments_router
from pazpaz.api.sessions import router as sessions_router
from pazpaz.api.treatment_recommendations import (
    router as treatment_recommendations_router,
)
from pazpaz.api.workspaces import router as workspaces_router

api_router = APIRouter()

# Include authentication router (no auth required)
api_router.include_router(auth_router)

# Include platform admin router (platform admin auth required)
api_router.include_router(platform_admin_router)

# Include resource routers (auth required)
api_router.include_router(clients_router)
api_router.include_router(appointments_router)
api_router.include_router(sessions_router)
api_router.include_router(session_attachments_router)
api_router.include_router(client_attachments_router)
api_router.include_router(services_router)
api_router.include_router(locations_router)
api_router.include_router(workspaces_router)
api_router.include_router(notification_settings_router)
api_router.include_router(google_calendar_integration_router)
api_router.include_router(payments_router)
api_router.include_router(audit_router)
api_router.include_router(ai_agent_router)
api_router.include_router(treatment_recommendations_router)
