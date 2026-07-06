"""Tests for the WhatsApp webhook: verification handshake, signature, and parsing.

These are CI-safe: they never touch the database. The one accepted POST uses a
non-actionable message (no image/location) so the background task returns before any
DB access.
"""

import hashlib
import hmac
import json

from fastapi.testclient import TestClient

from app.core.settings import settings
from app.services.whatsapp import parse_inbound, verify_signature
from main import app

client = TestClient(app)


def _sign(body: bytes) -> str:
    digest = hmac.new(
        settings.whatsapp_app_secret.encode(), body, hashlib.sha256
    ).hexdigest()
    return f"sha256={digest}"


def test_verify_handshake_success() -> None:
    response = client.get(
        "/webhook/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": settings.whatsapp_verify_token,
            "hub.challenge": "hello123",
        },
    )
    assert response.status_code == 200
    assert response.text == "hello123"


def test_verify_handshake_wrong_token() -> None:
    response = client.get(
        "/webhook/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong",
            "hub.challenge": "hello123",
        },
    )
    assert response.status_code == 403


def test_post_rejects_missing_signature() -> None:
    response = client.post("/webhook/whatsapp", json={"object": "x"})
    assert response.status_code == 403


def test_post_rejects_bad_signature() -> None:
    body = json.dumps({"object": "x"}).encode()
    response = client.post(
        "/webhook/whatsapp",
        content=body,
        headers={"X-Hub-Signature-256": "sha256=deadbeef"},
    )
    assert response.status_code == 403


def test_post_accepts_valid_signature() -> None:
    # Non-actionable message (no image/location) -> pipeline returns before DB access.
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [{"id": "wamid.TEST", "from": "5547999"}]
                        }
                    }
                ]
            }
        ]
    }
    body = json.dumps(payload).encode()
    response = client.post(
        "/webhook/whatsapp",
        content=body,
        headers={"X-Hub-Signature-256": _sign(body)},
    )
    assert response.status_code == 200


def test_verify_signature_unit() -> None:
    body = b'{"hello":"world"}'
    assert verify_signature(body, _sign(body)) is True
    assert verify_signature(body, "sha256=nope") is False
    assert verify_signature(body, None) is False


def test_parse_inbound_extracts_actionable_message() -> None:
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": "wamid.ABC",
                                    "from": "5547123",
                                    "image": {"id": "MEDIA1"},
                                    "location": {
                                        "latitude": -26.9,
                                        "longitude": -49.0,
                                    },
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }
    message = parse_inbound(payload)
    assert message is not None
    assert message.message_id == "wamid.ABC"
    assert message.is_actionable is True


def test_parse_inbound_returns_none_for_status_event() -> None:
    # A status callback has no "messages" array.
    payload: dict[str, object] = {
        "entry": [{"changes": [{"value": {"statuses": []}}]}]
    }
    assert parse_inbound(payload) is None
