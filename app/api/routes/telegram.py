"""Telegram Bot API webhook endpoint.

The controller stays thin: it verifies the optional secret token, hands parsing to the
service layer, and returns 200 OK immediately. Media download and AI classification run
in a background task.
"""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response

from app.services import telegram as telegram_service
from app.services.classifier.base import WasteClassifier
from app.services.classifier.dependencies import get_classifier
from app.services.telegram_pipeline import process_inbound_update

router = APIRouter(prefix="/webhook/telegram", tags=["telegram"])


@router.post("")
async def receive_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    classifier: Annotated[WasteClassifier, Depends(get_classifier)],
) -> Response:
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if not telegram_service.verify_webhook_secret(secret):
        return Response(status_code=403)

    payload = await request.json()
    message = telegram_service.parse_inbound(payload)
    if message is not None:
        background_tasks.add_task(process_inbound_update, message, classifier)

    return Response(status_code=200)
