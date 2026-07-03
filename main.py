from fastapi import FastAPI

from app.api.router import api_router
from app.core.settings import settings

app = FastAPI(
    title=settings.app_name,
    description="Backend API for Limcity Platform",
)

app.include_router(api_router)


@app.get("/")
def main_route() -> dict[str, str]:
    return {"message": "Welcome to Limcity Platform"}
