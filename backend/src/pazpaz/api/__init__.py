"""API routes."""

from fastapi import APIRouter

from pazpaz.api.appointments import router as appointments_router
from pazpaz.api.auth import router as auth_router
from pazpaz.api.clients import router as clients_router
from pazpaz.api.locations import router as locations_router
from pazpaz.api.services import router as services_router

api_router = APIRouter()

# Include authentication router (no auth required)
api_router.include_router(auth_router)

# Include resource routers (auth required)
api_router.include_router(clients_router)
api_router.include_router(appointments_router)
api_router.include_router(services_router)
api_router.include_router(locations_router)
