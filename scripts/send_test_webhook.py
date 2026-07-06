"""Send a signed, realistic WhatsApp webhook to the local server for manual testing.

Builds a Meta-style inbound message (image + GPS around Blumenau), signs the raw body
with ``whatsapp_app_secret`` (matching what Meta sends in ``X-Hub-Signature-256``), and
POSTs it. With no real WhatsApp token configured, the pipeline uses the dev media
bypass, so the report is created and CLASSIFIED by the placeholder classifier.

Usage:
    venv\\Scripts\\python -m scripts.send_test_webhook
    venv\\Scripts\\python -m scripts.send_test_webhook --lat -26.92 --lng -49.07
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


def build_payload(lat: float, lng: float) -> dict[str, object]:
    message_id = f"wamid.TEST-{uuid.uuid4()}"
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
                            "messages": [
                                {
                                    "id": message_id,
                                    "from": f"5547{random.randint(90000000, 99999999)}",
                                    "timestamp": "1700000000",
                                    "type": "image",
                                    "image": {"id": f"MEDIA-{uuid.uuid4()}"},
                                    "location": {"latitude": lat, "longitude": lng},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


def sign(raw_body: bytes) -> str:
    digest = hmac.new(
        key=settings.whatsapp_app_secret.encode(),
        msg=raw_body,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return f"sha256={digest}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Send a signed test WhatsApp webhook.")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--lat", type=float, default=None)
    parser.add_argument("--lng", type=float, default=None)
    args = parser.parse_args()

    lat = args.lat if args.lat is not None else BLUMENAU[0] + random.gauss(0, 0.01)
    lng = args.lng if args.lng is not None else BLUMENAU[1] + random.gauss(0, 0.01)

    payload = build_payload(lat, lng)
    raw_body = json.dumps(payload).encode()
    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": sign(raw_body),
    }

    endpoint = f"{args.url.rstrip('/')}/webhook/whatsapp"
    response = httpx.post(endpoint, content=raw_body, headers=headers, timeout=15.0)
    print(f"POST {endpoint} -> {response.status_code}")
    print(f"Sent report at ({lat:.5f}, {lng:.5f}).")
    if not settings.whatsapp_configured:
        print("WhatsApp token not configured: dev media bypass active (report will classify).")


if __name__ == "__main__":
    main()
