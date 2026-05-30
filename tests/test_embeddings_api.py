"""Tests for ApiEmbeddingProvider using an injected mock transport (no network)."""

from __future__ import annotations

import json

import httpx
import numpy as np

from resume_tailor.embeddings import ApiEmbeddingProvider, cosine_similarity_matrix


def _mock_client() -> httpx.Client:
    """Return an httpx client whose transport fakes the embeddings endpoint:
    each input text gets a deterministic 3-d vector."""

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        inputs = payload["input"]
        data = [
            {"embedding": [float(len(t)), 0.0, 1.0]} for t in inputs
        ]
        return httpx.Response(200, json={"data": data})

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_embed_returns_one_vector_per_text(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    provider = ApiEmbeddingProvider(client=_mock_client())
    vecs = provider.embed(["abc", "de"])
    assert vecs.shape == (2, 3)
    # Deterministic handler encodes text length in the first component.
    assert vecs[0][0] == 3.0
    assert vecs[1][0] == 2.0


def test_embed_empty_returns_empty(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    provider = ApiEmbeddingProvider(client=_mock_client())
    assert provider.embed([]).size == 0


def test_vectors_are_comparable_with_cosine(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    provider = ApiEmbeddingProvider(client=_mock_client())
    a = provider.embed(["abc"])
    b = provider.embed(["xyz"])  # same length -> identical mock vector
    sim = cosine_similarity_matrix(a, b)
    assert sim.shape == (1, 1)
    assert np.isclose(sim[0][0], 1.0)
