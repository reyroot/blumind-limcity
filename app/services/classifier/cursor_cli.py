"""Waste classifier that shells out to the Cursor CLI.

The agent runs in ask mode against a temporary workspace that contains only the
photo, so it can read the image and cannot edit the Limcity repository.
"""

import asyncio
import json
import re
import tempfile
from pathlib import Path
from typing import Any

from app.schemas.classification import WASTE_CATEGORIES, ClassificationResult
from app.services.classifier.base import WasteClassifier
from app.services.image_store import sniff_suffix

_PROMPT = """Classify the waste-report photo in this workspace. The only image file is named in
the next sentence. Read that file before answering.
Decide whether it is a valid public waste report: valid only when the image visibly shows
discarded garbage in an outdoor or public area. Invalid: indoor scenes, clean streets,
unrelated objects, people, animals, screenshots, images too unclear to verify waste, or a
correctly used garbage bin.
If it is valid, pick exactly one English category key:
organic, recyclable, construction_debris, electronic, bulky, hazardous, general.
Use general when waste is visible but no category dominates. Do not infer hazardous waste
unless it is visibly identifiable.
Reply with ONLY a JSON object and no markdown:
{"is_valid_report": true, "category": "general", "confidence": 0.8}
"""

_ALIASES = {
    "organico": "organic",
    "orgânico": "organic",
    "reciclavel": "recyclable",
    "reciclável": "recyclable",
    "entulho": "construction_debris",
    "construcao": "construction_debris",
    "construção": "construction_debris",
    "eletronico": "electronic",
    "eletrônico": "electronic",
    "volumoso": "bulky",
    "perigoso": "hazardous",
    "geral": "general",
}

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def _strip_fence(text: str) -> str:
    return _FENCE_RE.sub("", text.strip())


def _load_json(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("Cursor CLI did not return JSON") from None
        return json.loads(text[start : end + 1])


def parse_cursor_output(raw: str, depth: int = 0) -> dict[str, Any]:
    """Pull the classification object out of text or ``--output-format json`` envelopes."""
    if depth > 3:
        raise ValueError("Cursor CLI output nested too deeply")
    parsed = _load_json(_strip_fence(raw))
    if isinstance(parsed, list):
        texts = [
            item["result"]
            for item in parsed
            if isinstance(item, dict) and isinstance(item.get("result"), str)
        ]
        if not texts:
            raise ValueError("Cursor CLI output had no classification JSON")
        return parse_cursor_output(texts[-1], depth + 1)
    if not isinstance(parsed, dict):
        raise ValueError("Cursor CLI JSON was not an object")
    if "is_valid_report" in parsed:
        return parsed
    if parsed.get("is_error") is True:
        raise RuntimeError(str(parsed.get("result") or "Cursor CLI run failed"))
    result_text = parsed.get("result")
    if isinstance(result_text, str) and result_text.strip():
        return parse_cursor_output(result_text, depth + 1)
    raise ValueError("Cursor CLI output had no classification JSON")


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "sim", "1"}:
            return True
        if lowered in {"false", "no", "não", "nao", "0"}:
            return False
    raise ValueError("is_valid_report missing")


def _category(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("category missing")
    key = value.strip().lower()
    if key in WASTE_CATEGORIES:
        return key
    alias = _ALIASES.get(key)
    if alias is not None:
        return alias
    raise ValueError(f"Unknown waste category: {value}")


def _confidence(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError("confidence missing")
    number = float(value)
    if 1 < number <= 100:
        number = number / 100
    return max(0.0, min(1.0, number))


def classification_from_payload(payload: dict[str, Any], model: str) -> ClassificationResult:
    """Build a result. An invalid photo may omit the category."""
    is_valid = _as_bool(payload.get("is_valid_report"))
    if not is_valid:
        confidence = 0.0
        if payload.get("confidence") is not None:
            confidence = _confidence(payload.get("confidence"))
        return ClassificationResult(
            is_valid_report=False,
            category="general",
            confidence=confidence,
            raw={"provider": "cursor_cli", "model": model or "default"},
        )
    return ClassificationResult(
        is_valid_report=True,
        category=_category(payload.get("category")),
        confidence=_confidence(payload.get("confidence")),
        raw={"provider": "cursor_cli", "model": model or "default"},
    )


class CursorCliWasteClassifier(WasteClassifier):
    """Classify one photo by running the Cursor Agent CLI in read-only mode."""

    def __init__(self, cli_bin: str, model: str, timeout_seconds: float) -> None:
        self._cli_bin = cli_bin
        self._model = model
        self._timeout_seconds = timeout_seconds

    async def classify(self, image_bytes: bytes) -> ClassificationResult:
        if not image_bytes:
            raise ValueError("Cannot classify an empty image with Cursor CLI.")
        suffix = sniff_suffix(image_bytes)
        with tempfile.TemporaryDirectory(prefix="limcity-cursor-") as tmp:
            workspace = Path(tmp)
            image_path = workspace / f"photo{suffix}"
            image_path.write_bytes(image_bytes)
            prompt = f"{_PROMPT}\nImage file: {image_path.name}\n"
            stdout = await self._run_agent(workspace, prompt)
        payload = parse_cursor_output(stdout)
        return classification_from_payload(payload, self._model)

    def _command(self, workspace: Path, prompt: str) -> list[str]:
        command = [
            self._cli_bin,
            "-p",
            "--mode",
            "ask",
            "--trust",
            "--sandbox",
            "enabled",
            "--output-format",
            "json",
            "--workspace",
            str(workspace),
        ]
        if self._model:
            command.extend(["--model", self._model])
        command.append(prompt)
        return command

    async def _run_agent(self, workspace: Path, prompt: str) -> str:
        proc = await asyncio.create_subprocess_exec(
            *self._command(workspace, prompt),
            cwd=workspace,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self._timeout_seconds
            )
        except TimeoutError:
            proc.kill()
            await proc.communicate()
            raise TimeoutError(f"Cursor CLI exceeded {self._timeout_seconds:.0f}s") from None
        if proc.returncode != 0:
            detail = stderr.decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"Cursor CLI exited {proc.returncode}: {detail}")
        return stdout.decode("utf-8", errors="replace")
