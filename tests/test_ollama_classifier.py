import asyncio

import httpx
import pytest

from app.services.classifier.ollama import OllamaWasteClassifier


def test_ollama_classifier_sends_image_and_returns_structured_result(
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
                "total_duration": 123,
                "message": {
                    "content": '{"is_valid_report":true,"category":"bulky","confidence":0.91}'
                },
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    result = asyncio.run(
        OllamaWasteClassifier("http://localhost:11434/", "gemma3").classify(b"image")
    )

    assert result.category == "bulky"
    assert result.is_valid_report is True
    assert result.confidence == 0.91
    assert result.raw == {"provider": "ollama", "model": "gemma3", "total_duration_ns": 123}
    assert captured["url"] == "http://localhost:11434/api/chat"
    payload = captured["json"]
    assert isinstance(payload, dict)
    assert payload["stream"] is False
    assert payload["messages"][0]["images"] == ["aW1hZ2U="]
    assert payload["options"] == {"temperature": 0}
