"""WhatsApp Cloud API webhook endpoints.

The controller stays thin: it verifies the request, hands parsing/processing to the
service layer, and returns 200 OK immediately so Meta does not retry. The slow work
(media download + AI classification) runs in a background task.
"""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, Response
from fastapi.responses import PlainTextResponse

from app.core.settings import settings
from app.services import whatsapp as whatsapp_service
from app.services.classifier.base import WasteClassifier
from app.services.classifier.dependencies import get_classifier
from app.services.pipeline import process_inbound_message

router = APIRouter(prefix="/webhook/whatsapp", tags=["whatsapp"])


@router.get("")
async def verify_webhook(
    mode: str = Query(alias="hub.mode", default=""),
    token: str = Query(alias="hub.verify_token", default=""),
    challenge: str = Query(alias="hub.challenge", default=""),
) -> Response:
    """Meta webhook verification handshake."""
    if mode == "subscribe" and token == settings.whatsapp_verify_token:
        return PlainTextResponse(content=challenge)
    return PlainTextResponse(content="verification failed", status_code=403)


@router.post("")
async def receive_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    classifier: Annotated[WasteClassifier, Depends(get_classifier)],
) -> Response:
    raw_body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")
    if not whatsapp_service.verify_signature(raw_body, signature):
        return Response(status_code=403)

    payload = await request.json()
    message = whatsapp_service.parse_inbound(payload)
    if message is not None:
        background_tasks.add_task(process_inbound_message, message, classifier)

    # Always ack quickly so Meta does not resend.
    return Response(status_code=200)
