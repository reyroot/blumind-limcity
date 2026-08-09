"""Aggregates all API sub-routers under a single versioned router."""

from fastapi import APIRouter

from app.api.routes import health, reports, telegram, whatsapp

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(whatsapp.router)
api_router.include_router(telegram.router)
api_router.include_router(reports.router)
