import asyncio

import httpx
import pytest

from app.services.classifier.openai import OpenAIWasteClassifier


def test_openai_classifier_sends_image_and_returns_structured_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def fake_post(
        self: httpx.AsyncClient, url: str, **kwargs: object
    ) -> httpx.Response:
        captured["url"] = url
        captured.update(kwargs)
        return httpx.Response(
            200,
            json={
                "id": "resp_123",
                "output": [
                    {
                        "content": [
                            {
                                "type": "output_text",
                                "text": (
                                    '{"is_valid_report":true,"category":"recyclable",'
                                    '"confidence":0.85}'
                                ),
                            }
                        ]
                    }
                ],
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    result = asyncio.run(OpenAIWasteClassifier("test-key", "gpt-5").classify(b"image"))

    assert result.category == "recyclable"
    assert result.is_valid_report is True
    assert result.confidence == 0.85
    assert result.raw == {"provider": "openai", "model": "gpt-5", "response_id": "resp_123"}
    payload = captured["json"]
    assert isinstance(payload, dict)
    assert payload["model"] == "gpt-5"
    content = payload["input"][0]["content"]
    assert content[1]["image_url"] == "data:image/jpeg;base64,aW1hZ2U="


def test_openai_classifier_rejects_placeholder_key() -> None:
    with pytest.raises(ValueError, match="Set AI_API_KEY before using the OpenAI classifier."):
        OpenAIWasteClassifier("change-me", "gpt-5")
