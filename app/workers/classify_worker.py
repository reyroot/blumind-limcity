"""Classify queued waste reports.

Demo mode saves the photo and leaves the report ``pending``. This loop claims those
reports and classifies them with whatever provider the admin panel selected. When the
provider is ``cursor``, that call runs the Cursor CLI.

``run.py`` starts this loop next to the API. To watch it in its own terminal, set
``LIMCITY_EMBED_WORKER=0`` and run ``python -m app.workers.classify_worker``.
"""

import argparse
import asyncio
import logging
import sys

from app.db.session import SessionLocal
from app.models.report import ReportStatus
from app.schemas.classification import ClassificationResult
from app.services import report_service
from app.services.classifier.dependencies import get_classifier
from app.services.image_store import get_image_store
from app.services.reporter_notify import notify_outcome
from app.services.runtime_config import load_runtime_config

logger = logging.getLogger(__name__)

_POLL_IDLE_SECONDS = 2.0
_POLL_BUSY_SECONDS = 0.4


async def process_one() -> bool:
    """Classify the oldest pending report. Returns False when the queue is empty."""
    async with SessionLocal() as session:
        report = await report_service.claim_next_pending(session)
        if report is None:
            return False
        report_id = report.id
        await session.commit()

    cfg = load_runtime_config()
    logger.info("Classifying report %s with %s", report_id, cfg.ai_provider)
    result: ClassificationResult | None
    try:
        image = get_image_store().read(report_id) or b""
        result = await get_classifier().classify(image)
    except Exception:
        logger.exception("Classification failed for report %s", report_id)
        result = None

    async with SessionLocal() as session:
        stored = await report_service.get_by_id(session, report_id)
        if stored is None:
            return True
        if result is None:
            stored.status = ReportStatus.FAILED
        else:
            report_service.record_result(stored, result)
        await session.commit()
        logger.info(
            "Report %s -> %s (%s)",
            report_id,
            stored.status,
            stored.waste_category or "—",
        )
        await notify_outcome(stored, result)
    return True


async def run_forever() -> None:
    """Poll until cancelled."""
    cfg = load_runtime_config()
    logger.info(
        "Classification worker started (provider=%s, demo_mode=%s)",
        cfg.ai_provider,
        cfg.demo_mode,
    )
    while True:
        try:
            worked = await process_one()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Classification worker iteration failed")
            worked = False
        await asyncio.sleep(_POLL_BUSY_SECONDS if worked else _POLL_IDLE_SECONDS)


async def run_until_idle() -> int:
    """Drain the queue once and return how many reports were classified."""
    count = 0
    while await process_one():
        count += 1
    return count


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description="Classify pending Limcity waste reports.")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process the current queue and exit.",
    )
    args = parser.parse_args()
    try:
        if args.once:
            classified = asyncio.run(run_until_idle())
            logger.info("Classified %s report(s)", classified)
        else:
            asyncio.run(run_forever())
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
