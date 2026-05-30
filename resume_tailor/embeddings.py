"""Embedding providers behind a single small interface.

The gap analyzer only needs one capability: turn a list of texts into vectors it
can compare with cosine similarity. By hiding that behind a Protocol we can run
a zero-dependency TF-IDF backend in tests / CI and swap in a real semantic model
(sentence-transformers) in production without touching the analysis code.

This is also the honest engineering story: TF-IDF matches on shared *words*,
while a sentence model matches on *meaning* ("shipped a REST API" vs "built and
deployed web services"). Start with TF-IDF to prove the pipeline, then upgrade.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from typing import TYPE_CHECKING, Protocol, runtime_checkable

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity as _sk_cosine

if TYPE_CHECKING:
    import httpx


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Anything that can turn texts into a (n, d) float matrix of row vectors."""

    def embed(self, texts: Sequence[str]) -> np.ndarray: ...


class TfidfEmbeddingProvider:
    """Zero-dependency baseline: fits a TF-IDF space over the given corpus.

    Note this is *corpus-relative*: it must see all texts it will compare in a
    single ``embed`` call, because the vector space is defined by that corpus.
    That's fine for our use — we embed all resume bullets and JD requirements
    together — and it keeps tests fast and fully offline.
    """

    def __init__(self) -> None:
        self._vectorizer = TfidfVectorizer(
            lowercase=True,
            stop_words="english",
            ngram_range=(1, 2),
        )

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, 0), dtype=float)
        matrix = self._vectorizer.fit_transform(list(texts))
        return np.asarray(matrix.toarray(), dtype=float)


class SentenceTransformerProvider:
    """Real semantic embeddings. Lazy-imports so the heavy dep is optional.

    Install with ``pip install sentence-transformers`` and pass a model name
    such as ``"all-MiniLM-L6-v2"`` (small, fast, good enough for this task).
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - depends on optional dep
            raise ImportError(
                "SentenceTransformerProvider requires the 'sentence-transformers' "
                "package. Install it with: pip install sentence-transformers"
            ) from exc
        self._model = SentenceTransformer(model_name)

    def embed(self, texts: Sequence[str]) -> np.ndarray:  # pragma: no cover
        if not texts:
            return np.empty((0, 0), dtype=float)
        return np.asarray(
            self._model.encode(list(texts), normalize_embeddings=True),
            dtype=float,
        )


class ApiEmbeddingProvider:
    """Hosted embeddings via an HTTP API — no PyTorch, tiny deploy footprint.

    Defaults to OpenAI's ``text-embedding-3-small`` (cheap, strong). Because the
    deployed container ships none of the multi-gigabyte ML stack, builds are fast
    and cold starts are short. Privacy note: only bullet text and JD requirement
    text are ever embedded — never the candidate's identity fields.

    The key is read from the environment so it's never hard-coded. An httpx
    client can be injected for testing (pass a MockTransport) so CI never makes a
    real network call.
    """

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        api_key_env: str = "OPENAI_API_KEY",
        base_url: str = "https://api.openai.com/v1",
        client: httpx.Client | None = None,
    ) -> None:
        import httpx

        self._model = model
        self._key = os.environ[api_key_env]
        self._base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=30)

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, 0), dtype=float)
        resp = self._client.post(
            f"{self._base_url}/embeddings",
            headers={"Authorization": f"Bearer {self._key}"},
            json={"model": self._model, "input": list(texts)},
        )
        resp.raise_for_status()
        rows = resp.json()["data"]
        # Order by the API's index field so vectors line up with input order.
        rows = sorted(rows, key=lambda r: r.get("index", 0))
        return np.asarray([r["embedding"] for r in rows], dtype=float)


def cosine_similarity_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Cosine similarity between every row of ``a`` and every row of ``b``.

    Returns an (len(a), len(b)) matrix. Empty inputs yield an empty matrix
    rather than raising, so callers don't need to special-case empty resumes.
    """
    if a.size == 0 or b.size == 0:
        return np.zeros((a.shape[0] if a.ndim == 2 else 0,
                         b.shape[0] if b.ndim == 2 else 0), dtype=float)
    return np.asarray(_sk_cosine(a, b), dtype=float)
