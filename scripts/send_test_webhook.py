"""Send signed WhatsApp webhooks to the local server for manual testing.

Signs the raw body with ``whatsapp_app_secret`` (matching Meta's ``X-Hub-Signature-256``)
and POSTs it. With no real WhatsApp token configured the pipeline uses the dev media
bypass, so reports are created and CLASSIFIED by the placeholder classifier and replies
are logged (not sent).

Two modes:
  * default (combined): one message carrying both image + location -> completes at once.
  * --split: two messages (image, then location) from the same phone -> exercises the
    real two-step conversation flow and the ConversationSession correlation.

Usage:
    venv\\Scripts\\python -m scripts.send_test_webhook
    venv\\Scripts\\python -m scripts.send_test_webhook --split
    venv\\Scripts\\python -m scripts.send_test_webhook --split --lat -26.92 --lng -49.07
    venv\\Scripts\\python -m scripts.send_test_webhook --url http://127.0.0.1:8000
"""

import argparse
import hashlib
import hmac
import json
import random
import uuid

import httpx

from app.core.settings import settings

BLUMENAU = (-26.9194, -49.0661)


def _envelope(message: dict[str, object]) -> dict[str, object]:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "0",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "5547999999999",
                                "phone_number_id": "TEST_PHONE_ID",
                            },
                            "messages": [message],
                        },
                    }
                ],
            }
        ],
    }


def combined_payload(phone: str, lat: float, lng: float) -> dict[str, object]:
    return _envelope(
        {
            "id": f"wamid.TEST-{uuid.uuid4()}",
            "from": phone,
            "timestamp": "1700000000",
            "type": "image",
            "image": {"id": f"MEDIA-{uuid.uuid4()}"},
            "location": {"latitude": lat, "longitude": lng},
        }
    )


def image_payload(phone: str) -> dict[str, object]:
    return _envelope(
        {
            "id": f"wamid.TEST-{uuid.uuid4()}",
            "from": phone,
            "timestamp": "1700000000",
            "type": "image",
            "image": {"id": f"MEDIA-{uuid.uuid4()}"},
        }
    )


def location_payload(phone: str, lat: float, lng: float) -> dict[str, object]:
    return _envelope(
        {
            "id": f"wamid.TEST-{uuid.uuid4()}",
            "from": phone,
            "timestamp": "1700000001",
            "type": "location",
            "location": {"latitude": lat, "longitude": lng},
        }
    )


def sign(raw_body: bytes) -> str:
    digest = hmac.new(
        key=settings.whatsapp_app_secret.encode(),
        msg=raw_body,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return f"sha256={digest}"


def post(endpoint: str, payload: dict[str, object]) -> None:
    raw_body = json.dumps(payload).encode()
    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": sign(raw_body),
    }
    response = httpx.post(endpoint, content=raw_body, headers=headers, timeout=15.0)
    print(f"POST {endpoint} -> {response.status_code}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Send signed test WhatsApp webhooks.")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--lat", type=float, default=None)
    parser.add_argument("--lng", type=float, default=None)
    parser.add_argument(
        "--split",
        action="store_true",
        help="Send image and location as two separate messages (two-step flow).",
    )
    args = parser.parse_args()

    lat = args.lat if args.lat is not None else BLUMENAU[0] + random.gauss(0, 0.01)
    lng = args.lng if args.lng is not None else BLUMENAU[1] + random.gauss(0, 0.01)
    phone = f"5547{random.randint(90000000, 99999999)}"
    endpoint = f"{args.url.rstrip('/')}/webhook/whatsapp"

    if args.split:
        print(f"[split] phone {phone}: sending image, then location.")
        post(endpoint, image_payload(phone))
        post(endpoint, location_payload(phone, lat, lng))
    else:
        post(endpoint, combined_payload(phone, lat, lng))

    print(f"Sent report at ({lat:.5f}, {lng:.5f}).")
    if not settings.whatsapp_configured:
        print("WhatsApp token not configured: dev media bypass active (report will classify).")


if __name__ == "__main__":
    main()
