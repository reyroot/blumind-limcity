"""Send a signed Telegram webhook update to the local server for manual testing.

Simulates the two-step citizen flow (photo, then location) or a single combined update.
With no real bot token configured, replies are logged and media download is skipped.

Usage:
    venv\\Scripts\\python -m scripts.send_test_telegram_webhook
    venv\\Scripts\\python -m scripts.send_test_telegram_webhook --split
    venv\\Scripts\\python -m scripts.send_test_telegram_webhook --chat-id 123456789
"""

import argparse
import json
import random
import uuid

import httpx

from app.core.settings import settings

BLUMENAU = (-26.9194, -49.0661)


def _private_chat(chat_id: int) -> dict[str, object]:
    return {"id": chat_id, "type": "private", "first_name": "Test"}


def _user(user_id: int) -> dict[str, object]:
    return {"id": user_id, "is_bot": False, "first_name": "Citizen"}


def photo_update(chat_id: int, message_id: int) -> dict[str, object]:
    return {
        "update_id": random.randint(1_000_000, 9_999_999),
        "message": {
            "message_id": message_id,
            "from": _user(chat_id),
            "chat": _private_chat(chat_id),
            "date": 1_700_000_000,
            "photo": [
                {"file_id": f"small-{uuid.uuid4()}", "width": 90, "height": 90},
                {"file_id": f"MEDIA-{uuid.uuid4()}", "width": 800, "height": 600},
            ],
        },
    }


def location_update(chat_id: int, message_id: int, lat: float, lng: float) -> dict[str, object]:
    return {
        "update_id": random.randint(1_000_000, 9_999_999),
        "message": {
            "message_id": message_id,
            "from": _user(chat_id),
            "chat": _private_chat(chat_id),
            "date": 1_700_000_001,
            "location": {"latitude": lat, "longitude": lng},
        },
    }


def combined_update(chat_id: int, lat: float, lng: float) -> dict[str, object]:
    payload = photo_update(chat_id, random.randint(1, 999_999))
    message = payload["message"]
    assert isinstance(message, dict)
    message["location"] = {"latitude": lat, "longitude": lng}
    return payload


def post(endpoint: str, payload: dict[str, object]) -> None:
    headers = {"Content-Type": "application/json"}
    if settings.telegram_webhook_secret != "change-me":
        headers["X-Telegram-Bot-Api-Secret-Token"] = settings.telegram_webhook_secret
    raw_body = json.dumps(payload).encode()
    response = httpx.post(endpoint, content=raw_body, headers=headers, timeout=15.0)
    print(f"POST {endpoint} -> {response.status_code}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Send test Telegram webhook updates.")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--chat-id", type=int, default=random.randint(100_000_000, 999_999_999))
    parser.add_argument("--lat", type=float, default=None)
    parser.add_argument("--lng", type=float, default=None)
    parser.add_argument(
        "--split",
        action="store_true",
        help="Send photo and location as two separate updates.",
    )
    args = parser.parse_args()

    lat = args.lat if args.lat is not None else BLUMENAU[0] + random.gauss(0, 0.01)
    lng = args.lng if args.lng is not None else BLUMENAU[1] + random.gauss(0, 0.01)
    endpoint = f"{args.url.rstrip('/')}/webhook/telegram"

    if args.split:
        print(f"[split] chat {args.chat_id}: sending photo, then location.")
        post(endpoint, photo_update(args.chat_id, random.randint(1, 999_999)))
        post(endpoint, location_update(args.chat_id, random.randint(1, 999_999), lat, lng))
    else:
        post(endpoint, combined_update(args.chat_id, lat, lng))

    print(f"Sent report at ({lat:.5f}, {lng:.5f}).")
    if not settings.telegram_configured:
        print("Telegram token not configured: dev file bypass active (report will classify).")


if __name__ == "__main__":
    main()
