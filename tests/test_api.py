"""API integration tests using FastAPI's TestClient and dependency overrides.

No network and no real LLM: get_provider is overridden with a deterministic
embedding double, and get_llm with a FakeLLM returning canned JSON.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import numpy as np
import pytest
from fastapi.testclient import TestClient

from api.main import app, get_llm, get_provider
from resume_tailor import JobDescription, Resume


class ConstEmbeddings:
    """Every text maps to the same unit vector -> cosine similarity 1.0.

    Makes grounding's semantic-drift gate pass deterministically, so the /tailor
    happy path is testable without a real semantic model.
    """

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        return np.ones((len(texts), 1), dtype=float)


class FakeLLM:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)

    def complete(self, system: str, user: str) -> str:
        return self._responses.pop(0)


def _payload(resume: Resume, jd: JobDescription) -> dict:
    return {
        "resume": resume.model_dump(),
        "job_description": jd.model_dump(),
    }


@pytest.fixture
def client(resume: Resume, job_description: JobDescription):
    app.dependency_overrides[get_provider] = lambda: ConstEmbeddings()
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_analyze_returns_coverage(
    client: TestClient, resume: Resume, job_description: JobDescription
) -> None:
    resp = client.post("/analyze", json=_payload(resume, job_description))
    assert resp.status_code == 200
    body = resp.json()
    assert "coverages" in body
    assert len(body["coverages"]) == len(job_description.requirements)


def test_tailor_happy_path(
    resume: Resume, job_description: JobDescription
) -> None:
    good = json.dumps({"bullets": [
        {"source_bullet_id": "pulse1",
         "text": "Shipped an async service-health monitor with a REST API.",
         "rationale": "faithful"}
    ]})
    app.dependency_overrides[get_provider] = lambda: ConstEmbeddings()
    app.dependency_overrides[get_llm] = lambda: FakeLLM([good])
    try:
        c = TestClient(app)
        resp = c.post("/tailor", json=_payload(resume, job_description))
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200
    body = resp.json()
    assert body["grounding"]["all_grounded"] is True
    assert body["tailored"]["bullets"][0]["source_bullet_id"] == "pulse1"


def test_tailor_returns_502_on_llm_failure(
    resume: Resume, job_description: JobDescription
) -> None:
    class BoomLLM:
        def complete(self, system: str, user: str) -> str:
            raise RuntimeError("model down")

    app.dependency_overrides[get_provider] = lambda: ConstEmbeddings()
    app.dependency_overrides[get_llm] = lambda: BoomLLM()
    try:
        c = TestClient(app)
        resp = c.post("/tailor", json=_payload(resume, job_description))
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 502
    # Internal error text must not leak.
    assert "model down" not in resp.text


def test_export_returns_docx(
    client: TestClient, resume: Resume
) -> None:
    resp = client.post("/export", json={"resume": resume.model_dump()})
    assert resp.status_code == 200
    assert resp.content[:2] == b"PK"
    assert "attachment" in resp.headers["content-disposition"]
