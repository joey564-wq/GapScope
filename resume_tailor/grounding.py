"""Grounding validation — the integrity core of the tool.

Tailoring an LLM-rephrased resume is easy. Tailoring one that is *guaranteed not
to invent experience* is the actual engineering problem, and it's the thing
worth talking about in an interview.

A tailored bullet passes grounding only if it clears three gates:

1. STRUCTURAL — it names a ``source_bullet_id`` that exists in the real resume.
   No source, or an unknown source, means the content has no origin: reject.

2. METRIC — every number in the tailored text must also appear in its source
   bullet. This catches the single most common (and most damaging) fabrication:
   invented metrics like "improved performance by 40%" bolted onto a bullet
   that never quantified anything.

3. SEMANTIC — the tailored text must stay close in meaning to its source
   (cosine similarity above a floor). Rephrasing is allowed; drifting into a
   different claim is not.

The validator never edits text. It reports violations so the UI can flag or
reject suggestions and the LLM step can be re-prompted. Fail closed: anything
the checks can't vouch for is treated as ungrounded.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from enum import StrEnum

from pydantic import BaseModel, Field

from .embeddings import EmbeddingProvider, cosine_similarity_matrix
from .models import Bullet, Resume, TailoredBullet, TailoredResume


class ViolationKind(StrEnum):
    missing_source = "missing_source"
    unknown_source = "unknown_source"
    fabricated_metric = "fabricated_metric"
    semantic_drift = "semantic_drift"


class GroundingViolation(BaseModel):
    kind: ViolationKind
    tailored_text: str
    source_bullet_id: str | None = None
    detail: str


class GroundingResult(BaseModel):
    """Per-bullet pass/fail plus the list of reasons anything failed."""

    is_grounded: bool
    tailored_text: str
    source_bullet_id: str | None = None
    violations: list[GroundingViolation] = Field(default_factory=list)


class GroundingReport(BaseModel):
    all_grounded: bool
    results: list[GroundingResult] = Field(default_factory=list)

    @property
    def violations(self) -> list[GroundingViolation]:
        return [v for r in self.results for v in r.violations]

    @property
    def grounded_bullets(self) -> list[GroundingResult]:
        return [r for r in self.results if r.is_grounded]


# Numbers like 40, 40%, 4, 1.5, 2,000, $3, 12k — the stuff people fake.
_NUMBER = re.compile(r"\$?\d[\d,]*\.?\d*\s*%?\+?k?", re.IGNORECASE)


def _numbers(text: str) -> set[str]:
    """Normalised numeric tokens found in text (digits only, for comparison)."""
    found: set[str] = set()
    for m in _NUMBER.finditer(text):
        digits = re.sub(r"[^\d]", "", m.group(0))
        if digits:
            found.add(digits)
    return found


class GroundingValidator:
    """Validates tailored bullets against the candidate's real resume.

    Args:
        provider: embedding backend used for the semantic-drift check.
        semantic_floor: minimum cosine similarity between a tailored bullet and
            its source bullet. Below this, the rephrase is treated as drift.
    """

    def __init__(
        self,
        provider: EmbeddingProvider,
        *,
        semantic_floor: float = 0.30,
    ) -> None:
        self._provider = provider
        self._semantic_floor = semantic_floor

    def _check_one(
        self,
        tailored: TailoredBullet,
        resume_index: Mapping[str, Bullet],
    ) -> GroundingResult:
        violations: list[GroundingViolation] = []

        # Gate 1: structural provenance.
        if not tailored.source_bullet_id:
            violations.append(
                GroundingViolation(
                    kind=ViolationKind.missing_source,
                    tailored_text=tailored.text,
                    detail="Tailored bullet names no source bullet.",
                )
            )
            return GroundingResult(
                is_grounded=False,
                tailored_text=tailored.text,
                source_bullet_id=None,
                violations=violations,
            )

        source = resume_index.get(tailored.source_bullet_id)
        if source is None:
            violations.append(
                GroundingViolation(
                    kind=ViolationKind.unknown_source,
                    tailored_text=tailored.text,
                    source_bullet_id=tailored.source_bullet_id,
                    detail=(
                        f"source_bullet_id '{tailored.source_bullet_id}' does "
                        "not exist in the original resume."
                    ),
                )
            )
            return GroundingResult(
                is_grounded=False,
                tailored_text=tailored.text,
                source_bullet_id=tailored.source_bullet_id,
                violations=violations,
            )

        source_text: str = source.text

        # Gate 2: no invented numbers.
        new_numbers = _numbers(tailored.text) - _numbers(source_text)
        if new_numbers:
            violations.append(
                GroundingViolation(
                    kind=ViolationKind.fabricated_metric,
                    tailored_text=tailored.text,
                    source_bullet_id=tailored.source_bullet_id,
                    detail=(
                        "Tailored text introduces numbers not in the source: "
                        + ", ".join(sorted(new_numbers))
                    ),
                )
            )

        # Gate 3: semantic closeness to the source.
        vecs = self._provider.embed([tailored.text, source_text])
        sim = float(cosine_similarity_matrix(vecs[:1], vecs[1:])[0][0])
        if sim < self._semantic_floor:
            violations.append(
                GroundingViolation(
                    kind=ViolationKind.semantic_drift,
                    tailored_text=tailored.text,
                    source_bullet_id=tailored.source_bullet_id,
                    detail=(
                        f"Similarity to source {sim:.2f} is below floor "
                        f"{self._semantic_floor:.2f}; rephrase drifted too far."
                    ),
                )
            )

        return GroundingResult(
            is_grounded=not violations,
            tailored_text=tailored.text,
            source_bullet_id=tailored.source_bullet_id,
            violations=violations,
        )

    def validate(
        self, tailored: TailoredResume, resume: Resume
    ) -> GroundingReport:
        """Validate every tailored bullet against the real resume."""
        index = resume.bullet_index()
        results = [self._check_one(b, index) for b in tailored.bullets]
        return GroundingReport(
            all_grounded=all(r.is_grounded for r in results),
            results=results,
        )
