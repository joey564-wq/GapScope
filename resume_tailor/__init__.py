"""resume_tailor: truthfully re-present a resume against a job description.

Public surface:
    - models: structured Resume / JobDescription / TailoredResume
    - embeddings: swappable EmbeddingProvider backends
    - gap_analysis.analyze_gap: explainable coverage report
    - grounding.GroundingValidator: anti-fabrication checks on tailored output
    - recommendations.recommend_for_gaps: LLM suggestions to close gaps
"""

from __future__ import annotations

from .embeddings import (
    ApiEmbeddingProvider,
    EmbeddingProvider,
    SentenceTransformerProvider,
    TfidfEmbeddingProvider,
)
from .export import resume_to_docx_bytes
from .gap_analysis import CoverageStatus, GapReport, analyze_gap
from .grounding import GroundingReport, GroundingValidator, ViolationKind
from .models import (
    Bullet,
    ContactInfo,
    Entry,
    EntryKind,
    JobDescription,
    JobRequirement,
    Resume,
    SkillGroup,
    TailoredBullet,
    TailoredResume,
)

# Imported after gap_analysis and models because recommendations.py imports
# GapReport (from gap_analysis) and JobDescription (from models) at module load.
from .recommendations import RecommendationReport, recommend_for_gaps
from .tailoring import (
    GeminiClient,
    LLMClient,
    OllamaClient,
    rebuild_resume,
    tailor_resume,
)

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
    "GroundingReport",
    "GroundingValidator",
    "JobDescription",
    "JobRequirement",
    "LLMClient",
    "OllamaClient",
    "RecommendationReport",
    "Resume",
    "SentenceTransformerProvider",
    "SkillGroup",
    "TailoredBullet",
    "TailoredResume",
    "TfidfEmbeddingProvider",
    "ViolationKind",
    "analyze_gap",
    "rebuild_resume",
    "recommend_for_gaps",
    "resume_to_docx_bytes",
    "tailor_resume",
]