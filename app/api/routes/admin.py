"""Local admin endpoints for presentation setup. No authentication."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.schemas.admin import AdminConfigPublic, AdminConfigUpdate, AdminStatus, DemoDataResult
from app.services import report_service
from app.services.demo_data import clear_simulated, fill_simulated
from app.services.runtime_config import load_runtime_config, public_config, save_runtime_config

router = APIRouter(prefix="/api/admin", tags=["admin"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get("/config", response_model=AdminConfigPublic)
async def get_config() -> AdminConfigPublic:
    return public_config()


@router.put("/config", response_model=AdminConfigPublic)
async def put_config(update: AdminConfigUpdate) -> AdminConfigPublic:
    return public_config(save_runtime_config(update))


@router.get("/status", response_model=AdminStatus)
async def get_status(session: SessionDep) -> AdminStatus:
    cfg = load_runtime_config()
    counts = await report_service.status_counts(session)
    return AdminStatus(
        database_ok=True,
        by_status=counts,
        demo_mode=cfg.demo_mode,
        ai_provider=cfg.ai_provider,
    )


@router.post("/requeue")
async def requeue(session: SessionDep) -> dict[str, int]:
    """Move reports left in ``processing`` back to ``pending``."""
    moved = await report_service.requeue_processing(session)
    return {"requeued": moved}


@router.post("/demo-data", response_model=DemoDataResult)
async def post_demo_data(session: SessionDep) -> DemoDataResult:
    """Replace simulated map data with a fresh classified set around Blumenau."""
    inserted, removed = await fill_simulated(session)
    return DemoDataResult(inserted=inserted, removed=removed)


@router.post("/demo-data/clear", response_model=DemoDataResult)
async def post_demo_data_clear(session: SessionDep) -> DemoDataResult:
    """Delete simulated reports only. Citizen reports stay."""
    removed = await clear_simulated(session)
    return DemoDataResult(inserted=0, removed=removed)
