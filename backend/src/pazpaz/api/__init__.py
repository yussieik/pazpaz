"""API routes."""

from fastapi import APIRouter

from pazpaz.api.appointments import router as appointments_router
from pazpaz.api.clients import router as clients_router

api_router = APIRouter()

# Include all API routers
api_router.include_router(clients_router)
api_router.include_router(appointments_router)