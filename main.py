from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.settings import settings

app = FastAPI(
    title=settings.app_name,
    description="Backend API for Limcity Platform",
)

app.include_router(api_router)

_STATIC_DIR = Path(__file__).parent / "app" / "static"
app.mount("/dashboard", StaticFiles(directory=_STATIC_DIR, html=True), name="dashboard")
app.mount("/admin", StaticFiles(directory=_STATIC_DIR / "admin", html=True), name="admin")


@app.get("/")
def main_route() -> dict[str, str]:
    return {"message": "Welcome to Limcity Platform"}
