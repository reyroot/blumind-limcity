"""Aggregates all API sub-routers under a single versioned router."""

from fastapi import APIRouter

from app.api.routes import health, whatsapp

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(whatsapp.router)
