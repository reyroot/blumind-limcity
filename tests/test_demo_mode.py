"""Demo mode: saved photos, admin setup, and the Cursor CLI classifier."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.core.settings import settings
from app.db.session import get_session
from app.models.report import ReportStatus, SourceChannel, WasteReport
from app.schemas.classification import ClassificationResult
from app.services.classifier.cursor_cli import (
    CursorCliWasteClassifier,
    parse_cursor_output,
)
from app.services.image_store import ImageStore, sniff_suffix
from app.services.report_conversation import _complete_report
from app.services.report_service import record_result
from app.services.reporter_notify import reply_invalid, reply_queued
from main import app

client = TestClient(app)

_JPEG = b"\xff\xd8\xff\xd9"


def test_placeholder_png_is_a_png() -> None:
    from app.services.demo_data import is_simulated_message_id, placeholder_png

    image = placeholder_png("organic")
    assert image.startswith(b"\x89PNG\r\n\x1a\n")
    assert is_simulated_message_id("sim-1")
    assert is_simulated_message_id("seed-1")
    assert not is_simulated_message_id("tg:1:2")


def test_demo_data_routes_report_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_fill(session: object, count: int = 90) -> tuple[int, int]:
        return 90, 0

    async def fake_clear(session: object) -> int:
        return 4

    monkeypatch.setattr("app.api.routes.admin.fill_simulated", fake_fill)
    monkeypatch.setattr("app.api.routes.admin.clear_simulated", fake_clear)

    filled = client.post("/api/admin/demo-data")
    cleared = client.post("/api/admin/demo-data/clear")
    assert filled.status_code == 200
    assert filled.json() == {"inserted": 90, "removed": 0}
    assert cleared.status_code == 200
    assert cleared.json() == {"inserted": 0, "removed": 4}


def test_sniff_and_save_round_trip(tmp_path: object) -> None:
    from pathlib import Path

    root = Path(str(tmp_path))
    store = ImageStore(root)
    url = store.save(3, _JPEG)
    assert url == "/api/reports/3/image"
    assert sniff_suffix(_JPEG) == ".jpg"
    assert store.read(3) == _JPEG

    store.save(3, b"\x89PNG\r\n\x1a\nrest")
    assert store.path_for(3) is not None
    assert store.path_for(3).suffix == ".png"  # type: ignore[union-attr]
    assert not (root / "3.jpg").exists()
    store.delete(3)
    assert store.path_for(3) is None


def test_dashboard_and_admin_are_in_portuguese() -> None:
    dashboard = client.get("/dashboard/")
    admin = client.get("/admin/")
    assert dashboard.status_code == 200
    assert "Mapa de resíduos" in dashboard.text
    assert "Todas as categorias" in dashboard.text
    assert "Últimas fotos" in dashboard.text
    assert admin.status_code == 200
    assert "Configuração local da demonstração" in admin.text
    assert "Preencher demonstração" in admin.text
    assert "Limpar dados simulados" in admin.text
    assert "python -m app.workers.classify_worker" in admin.text
    assert 'type="password"' in admin.text


def test_admin_config_hides_api_key(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    from pathlib import Path

    monkeypatch.setattr(settings, "runtime_config_path", str(Path(str(tmp_path)) / "cfg.json"))
    secret = "sk-test-secret-do-not-leak"
    response = client.put(
        "/api/admin/config",
        json={
            "demo_mode": True,
            "ai_provider": "cursor",
            "openai_model": "gpt-5",
            "ollama_base_url": "http://localhost:11434",
            "ollama_model": "gemma3",
            "ollama_timeout_seconds": 30,
            "cursor_cli_bin": "agent",
            "cursor_model": "",
            "cursor_timeout_seconds": 90,
            "ai_api_key": secret,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ai_provider"] == "cursor"
    assert body["demo_mode"] is True
    assert body["ai_api_key_set"] is True
    assert secret not in response.text

    kept = client.put(
        "/api/admin/config",
        json={
            "demo_mode": False,
            "ai_provider": "ollama",
            "openai_model": "gpt-5",
            "ollama_base_url": "http://localhost:11434",
            "ollama_model": "gemma3",
            "ollama_timeout_seconds": 30,
            "cursor_cli_bin": "agent",
            "cursor_model": "",
            "cursor_timeout_seconds": 90,
        },
    )
    assert kept.status_code == 200
    assert kept.json()["ai_api_key_set"] is True
    assert secret not in kept.text

    rejected = client.put(
        "/api/admin/config",
        json={
            "demo_mode": True,
            "ai_provider": "cursor",
            "openai_model": "gpt-5",
            "ollama_base_url": "http://localhost:11434",
            "ollama_model": "gemma3",
            "ollama_timeout_seconds": 30,
            "cursor_cli_bin": "agent; rm -rf",
            "cursor_model": "",
            "cursor_timeout_seconds": 90,
        },
    )
    assert rejected.status_code == 422


def test_outcome_messages_include_the_case_number() -> None:
    assert "nº 12" in reply_queued(12)
    assert "nº 12" in reply_invalid(12)


def test_collect_notifies_and_rejects_a_closed_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[int] = []

    async def fake_notify(report: object) -> None:
        sent.append(report.id)  # type: ignore[attr-defined]

    monkeypatch.setattr("app.api.routes.reports.notify_collected", fake_notify)
    open_report = SimpleNamespace(
        id=5,
        status=ReportStatus.CLASSIFIED,
        reporter_phone="tg:1",
        source_channel=SourceChannel.TELEGRAM,
    )
    closed = SimpleNamespace(
        id=6,
        status=ReportStatus.FAILED,
        reporter_phone="tg:1",
        source_channel=SourceChannel.TELEGRAM,
    )

    class _Session:
        async def get(self, model: object, ident: int) -> object | None:
            if ident == 5:
                return open_report
            if ident == 6:
                return closed
            return None

    async def _override() -> object:
        yield _Session()

    app.dependency_overrides[get_session] = _override
    try:
        ok = client.post("/api/reports/5/collect")
        rejected = client.post("/api/reports/6/collect")
        missing = client.post("/api/reports/9/collect")
    finally:
        app.dependency_overrides.clear()

    assert ok.status_code == 200
    assert ok.json()["status"] == "collected"
    assert open_report.status == ReportStatus.COLLECTED
    assert sent == [5]
    assert rejected.status_code == 409
    assert missing.status_code == 404


def test_invalid_cursor_result_may_omit_category() -> None:
    from app.services.classifier.cursor_cli import classification_from_payload

    result = classification_from_payload(
        {"is_valid_report": False, "confidence": 0.2},
        "",
    )
    assert result.is_valid_report is False
    assert result.category == "general"
    assert result.confidence == 0.2


def test_cursor_output_parser_reads_cli_envelope() -> None:
    raw = (
        '{"type":"result","is_error":false,"result":'
        '"{\\"is_valid_report\\": true, \\"category\\": \\"Entulho\\", \\"confidence\\": 91}"}'
    )
    payload = parse_cursor_output(raw)
    assert payload["category"] == "Entulho"


def test_cursor_command_is_read_only(tmp_path: object) -> None:
    from pathlib import Path

    workspace = Path(str(tmp_path))
    clf = CursorCliWasteClassifier("agent", "", 30)
    command = clf._command(workspace, "Classify the photo.")
    assert command[0] == "agent"
    assert "--mode" in command and command[command.index("--mode") + 1] == "ask"
    assert "--sandbox" in command
    assert "--force" not in command
    assert "--yolo" not in command
    assert command[command.index("--workspace") + 1] == str(workspace)


def test_cursor_classifier_parses_agent_stdout(monkeypatch: pytest.MonkeyPatch) -> None:
    clf = CursorCliWasteClassifier("agent", "composer-2.5", 30)

    async def fake_run(workspace: object, prompt: str) -> str:
        assert "photo.jpg" in prompt
        return '{"is_valid_report": true, "category": "organic", "confidence": 0.66}'

    monkeypatch.setattr(clf, "_run_agent", fake_run)
    result = pytest.importorskip("asyncio").run(clf.classify(_JPEG))
    assert result.category == "organic"
    assert result.is_valid_report is True
    assert result.confidence == 0.66
    assert result.raw["provider"] == "cursor_cli"


def test_record_result_keeps_invalid_photo_visible() -> None:
    report = SimpleNamespace(
        status=ReportStatus.PENDING,
        waste_category="general",
        confidence=None,
    )
    record_result(
        report,  # type: ignore[arg-type]
        ClassificationResult(
            is_valid_report=False,
            category="general",
            confidence=0.2,
            raw={},
        ),
    )
    assert report.status == ReportStatus.FAILED
    assert report.waste_category is None
    assert report.confidence == 0.2


async def test_demo_mode_saves_photo_and_skips_inline_classify(
    tmp_path: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pathlib import Path

    monkeypatch.setattr(settings, "image_storage_dir", str(Path(str(tmp_path))))
    monkeypatch.setattr(
        "app.services.report_conversation.load_runtime_config",
        lambda: SimpleNamespace(demo_mode=True),
    )
    report = SimpleNamespace(id=7, image_url=None)
    monkeypatch.setattr(
        "app.services.report_conversation.report_service.get_by_message_id",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "app.services.report_conversation.report_service.create_report",
        AsyncMock(return_value=report),
    )
    apply = AsyncMock()
    monkeypatch.setattr(
        "app.services.report_conversation.report_service.apply_classification",
        apply,
    )
    classifier = AsyncMock()
    channel = AsyncMock()
    channel.source_channel = SourceChannel.TELEGRAM
    channel.download_image.return_value = _JPEG

    await _complete_report(
        AsyncMock(),
        classifier,
        channel,
        reporter_label="ana",
        session_key="ana",
        message_id="tg:1",
        media_ref="file-1",
        latitude=-26.91,
        longitude=-49.06,
    )

    classifier.classify.assert_not_called()
    apply.assert_not_called()
    assert report.image_url == "/api/reports/7/image"
    assert (Path(str(tmp_path)) / "7.jpg").is_file()
    channel.send_text.assert_awaited_with("ana", reply_queued(7))


def test_report_image_route(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    from pathlib import Path

    root = Path(str(tmp_path))
    monkeypatch.setattr(settings, "image_storage_dir", str(root))
    ImageStore(root).save(4, _JPEG)
    report = SimpleNamespace(id=4, image_url="/api/reports/4/image")

    class _Session:
        async def get(self, model: object, ident: int) -> object | None:
            return report if ident == 4 else None

    async def _override() -> object:
        yield _Session()

    app.dependency_overrides[get_session] = _override
    try:
        found = client.get("/api/reports/4/image")
        missing = client.get("/api/reports/9/image")
    finally:
        app.dependency_overrides.clear()

    assert found.status_code == 200
    assert found.content == _JPEG
    assert found.headers["content-type"].startswith("image/jpeg")
    assert missing.status_code == 404


async def test_simulated_fill_replaces_only_simulated_rows(
    tmp_path: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    import uuid
    from pathlib import Path

    from geoalchemy2.elements import WKTElement

    from app.db.session import SessionLocal
    from app.services.demo_data import clear_simulated, fill_simulated

    monkeypatch.setattr(settings, "image_storage_dir", str(tmp_path))
    async with SessionLocal() as session:
        real = WasteReport(
            whatsapp_message_id=f"tg:keep-{uuid.uuid4()}",
            reporter_phone="tg:keep",
            source_channel=SourceChannel.TELEGRAM,
            location=WKTElement("POINT(-49.0661 -26.9194)", srid=4326),
            latitude=-26.9194,
            longitude=-49.0661,
            status=ReportStatus.CLASSIFIED,
            waste_category="organic",
            confidence=0.9,
        )
        session.add(real)
        await session.flush()
        inserted, _removed = await fill_simulated(session, count=2)
        assert inserted == 2
        assert await session.get(WasteReport, real.id) is not None
        photos = list(Path(str(tmp_path)).glob("*"))
        assert len(photos) == 2
        removed = await clear_simulated(session)
        assert removed == 2
        assert await session.get(WasteReport, real.id) is not None
        assert list(Path(str(tmp_path)).glob("*")) == []
        await session.rollback()
