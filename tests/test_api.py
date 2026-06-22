"""API integration tests using FastAPI's TestClient and dependency overrides.

No network and no real LLM: get_provider is overridden with a deterministic
embedding double so /analyze is testable offline.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pytest
from fastapi.testclient import TestClient

from api.main import app, get_provider
from resume_tailor import JobDescription, Resume


class ConstEmbeddings:
    """Every text maps to the same unit vector -> cosine similarity 1.0.

    A deterministic embedding double so coverage scoring is reproducible
    without a real semantic model.
    """

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        return np.ones((len(texts), 1), dtype=float)


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
