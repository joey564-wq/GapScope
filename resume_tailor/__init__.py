"""GapScope: analyze the gap between a resume and a job description.

Public surface:
    - models: structured Resume / JobDescription
    - embeddings: swappable EmbeddingProvider backends
    - gap_analysis.analyze_gap: explainable coverage report
    - recommendations.recommend_for_gaps: LLM suggestions to close gaps
    - llm: LLM clients (Gemini / Ollama) behind a small protocol
"""

from __future__ import annotations

from .embeddings import (
    ApiEmbeddingProvider,
    EmbeddingProvider,
    SentenceTransformerProvider,
    TfidfEmbeddingProvider,
)
from .gap_analysis import CoverageStatus, GapReport, analyze_gap
from .llm import GeminiClient, LLMClient, OllamaClient
from .models import (
    Bullet,
    ContactInfo,
    Entry,
    EntryKind,
    JobDescription,
    JobRequirement,
    Resume,
    SkillGroup,
)

# Imported after gap_analysis and models because recommendations.py imports
# from both at module load.
from .recommendations import RecommendationReport, recommend_for_gaps

__all__ = [
    "ApiEmbeddingProvider",
    "Bullet",
    "ContactInfo",
    "CoverageStatus",
    "EmbeddingProvider",
    "Entry",
    "EntryKind",
    "GapReport",
    "GeminiClient",
    "JobDescription",
    "JobRequirement",
    "LLMClient",
    "OllamaClient",
    "RecommendationReport",
    "Resume",
    "SentenceTransformerProvider",
    "SkillGroup",
    "TfidfEmbeddingProvider",
    "analyze_gap",
    "recommend_for_gaps",
]
