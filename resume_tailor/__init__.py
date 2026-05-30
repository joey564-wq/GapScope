"""resume_tailor: truthfully re-present a resume against a job description.

Public surface:
    - models: structured Resume / JobDescription / TailoredResume
    - embeddings: swappable EmbeddingProvider backends
    - gap_analysis.analyze_gap: explainable coverage report
    - grounding.GroundingValidator: anti-fabrication checks on tailored output
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
    "Resume",
    "SentenceTransformerProvider",
    "SkillGroup",
    "TailoredBullet",
    "TailoredResume",
    "TfidfEmbeddingProvider",
    "ViolationKind",
    "analyze_gap",
    "rebuild_resume",
    "resume_to_docx_bytes",
    "tailor_resume",
]
