"""Tests for the Telegram webhook: secret verification and update parsing.

CI-safe: no database access. Accepted POSTs use text-only updates so the background
task returns before any DB access.
"""

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.core.settings import settings
from app.services.telegram import parse_inbound, send_text_message, verify_webhook_secret
from main import app

client = TestClient(app)


def _headers() -> dict[str, str]:
    if settings.telegram_webhook_secret == "change-me":
        return {}
    return {"X-Telegram-Bot-Api-Secret-Token": settings.telegram_webhook_secret}


def test_post_accepts_text_update() -> None:
    payload = {
        "update_id": 1,
        "message": {
            "message_id": 10,
            "from": {"id": 42, "is_bot": False, "first_name": "Test"},
            "chat": {"id": 42, "type": "private", "first_name": "Test"},
            "date": 1_700_000_000,
            "text": "oi",
        },
    }
    response = client.post("/webhook/telegram", json=payload, headers=_headers())
    assert response.status_code == 200


def test_parse_inbound_extracts_photo() -> None:
    payload = {
        "message": {
            "message_id": 11,
            "from": {"id": 99, "is_bot": False},
            "chat": {"id": 99, "type": "private"},
            "photo": [{"file_id": "small"}, {"file_id": "LARGE"}],
        }
    }
    message = parse_inbound(payload)
    assert message is not None
    assert message.message_type == "image"
    assert message.image_media_ref == "LARGE"
    assert message.session_key == "tg:99"
    assert message.message_id == "tg:99:11"


def test_parse_inbound_extracts_location() -> None:
    payload = {
        "message": {
            "message_id": 12,
            "from": {"id": 88, "is_bot": False},
            "chat": {"id": 88, "type": "private"},
            "location": {"latitude": -26.9, "longitude": -49.0},
        }
    }
    message = parse_inbound(payload)
    assert message is not None
    assert message.message_type == "location"
    assert message.has_location is True


def test_parse_inbound_ignores_group_chat() -> None:
    payload = {
        "message": {
            "message_id": 13,
            "from": {"id": 1, "is_bot": False},
            "chat": {"id": -100, "type": "group"},
            "text": "oi",
        }
    }
    assert parse_inbound(payload) is None


def test_verify_webhook_secret_dev_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "telegram_webhook_secret", "change-me")
    assert verify_webhook_secret(None) is True
    assert verify_webhook_secret("wrong") is True


def test_verify_webhook_secret_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "telegram_webhook_secret", "my-secret")
    assert verify_webhook_secret(None) is False
    assert verify_webhook_secret("wrong") is False
    assert verify_webhook_secret("my-secret") is True


def test_send_text_message_dev_bypass_is_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "telegram_bot_token", "change-me")
    asyncio.run(send_text_message("tg:42", "hello"))
