"""Gap analysis: how well does this resume cover this job description?

The core move is to embed every resume bullet and every JD requirement into the
same space, then for each requirement find the resume bullet that matches it
best. A requirement with a strong match is "covered"; a weak best-match means
the candidate has a gap. We also do a plain keyword check on the JD's skills,
because sometimes the literal token ("Kubernetes") is what an ATS screens for.

Nothing here calls an LLM. This is the deterministic, explainable layer — you
can point at the similarity matrix and justify every number. The LLM only comes
in later, for *rephrasing* (see tailoring + grounding).
"""

from __future__ import annotations

import re
from enum import StrEnum

import numpy as np
from pydantic import BaseModel, Field

from .embeddings import EmbeddingProvider, cosine_similarity_matrix
from .models import JobDescription, Resume


class CoverageStatus(StrEnum):
    covered = "covered"
    partial = "partial"
    uncovered = "uncovered"


class RequirementCoverage(BaseModel):
    requirement_id: str
    requirement_text: str
    status: CoverageStatus
    best_score: float
    best_bullet_id: str | None = None
    best_bullet_text: str | None = None


class GapReport(BaseModel):
    """The full explainable result of comparing a resume to a job posting."""

    overall_score: float = Field(
        description="Mean best-match score across all requirements, 0..1."
    )
    coverages: list[RequirementCoverage] = Field(default_factory=list)
    missing_skills: list[str] = Field(
        default_factory=list,
        description="Skill keywords named in the JD that the resume never claims.",
    )

    @property
    def uncovered(self) -> list[RequirementCoverage]:
        return [c for c in self.coverages if c.status is CoverageStatus.uncovered]

    @property
    def partial(self) -> list[RequirementCoverage]:
        return [c for c in self.coverages if c.status is CoverageStatus.partial]


_WORD = re.compile(r"[a-zA-Z][a-zA-Z0-9+#.\-]*")


def _tokens(text: str) -> set[str]:
    return {m.group(0).lower() for m in _WORD.finditer(text)}


def find_missing_skills(resume: Resume, jd: JobDescription) -> list[str]:
    """Skills the resume declares vs. skill-like tokens that appear in the JD.

    Deliberately simple and literal: this is the ATS-keyword view, complementary
    to the semantic view. We only flag a JD token as 'missing' if it matches one
    of the candidate's *own* declared skill vocabulary shape but isn't present —
    i.e. we compare against the union of known skills, not the whole dictionary,
    to avoid drowning the user in noise.
    """
    have = resume.all_skills()
    jd_text = " ".join(r.text for r in jd.requirements)
    if jd.raw_text:
        jd_text = f"{jd_text} {jd.raw_text}"
    jd_tokens = _tokens(jd_text)
    # A skill is "missing" if the candidate declares it nowhere but the JD names
    # it. We check multi-word skills by substring and single tokens by set.
    missing: list[str] = []
    # Surface declared-but-absent: any known skill vocabulary the JD asks for.
    # Build a candidate skill list from JD tokens that look like tech terms.
    for token in sorted(jd_tokens):
        if len(token) < 2:
            continue
        looks_technical = any(c.isupper() for c in token) or token in {
            "python", "java", "sql", "react", "aws", "docker", "kubernetes",
            "go", "rust", "typescript", "node", "graphql", "redis", "kafka",
        }
        if looks_technical and token not in have and not any(
            token in skill for skill in have
        ):
            missing.append(token)
    return missing


def analyze_gap(
    resume: Resume,
    jd: JobDescription,
    provider: EmbeddingProvider,
    *,
    covered_threshold: float = 0.45,
    partial_threshold: float = 0.20,
) -> GapReport:
    """Compute per-requirement coverage and an overall score.

    Args:
        resume: the candidate's structured resume.
        jd: the target job description, decomposed into requirements.
        provider: embedding backend (TF-IDF in tests, semantic in prod).
        covered_threshold: best-match score at/above which a requirement counts
            as covered.
        partial_threshold: best-match score at/above which a requirement counts
            as partially covered (below it is uncovered).

    Note on thresholds: the defaults are tuned for *semantic* embeddings
    (sentence-transformers), where a faithful match scores ~0.5-0.8. The TF-IDF
    baseline produces much smaller absolute cosines on short bullets (often
    <0.1) even when the *ranking* is correct, so absolute status buckets are
    only meaningful with a semantic backend. Ranking (which bullet matches a
    requirement best) is robust across both backends.
    """
    bullets = resume.all_bullets()
    requirements = jd.requirements

    if not requirements:
        return GapReport(overall_score=0.0, coverages=[], missing_skills=[])

    if not bullets:
        empty_coverages = [
            RequirementCoverage(
                requirement_id=req.id,
                requirement_text=req.text,
                status=CoverageStatus.uncovered,
                best_score=0.0,
            )
            for req in requirements
        ]
        return GapReport(
            overall_score=0.0,
            coverages=empty_coverages,
            missing_skills=find_missing_skills(resume, jd),
        )

    bullet_texts = [b.text for b in bullets]
    req_texts = [r.text for r in requirements]

    # Embed everything in one corpus so the TF-IDF space is shared.
    combined = provider.embed([*bullet_texts, *req_texts])
    bullet_vecs = combined[: len(bullet_texts)]
    req_vecs = combined[len(bullet_texts):]

    # (n_requirements, n_bullets) similarity matrix.
    sim = cosine_similarity_matrix(req_vecs, bullet_vecs)

    coverages: list[RequirementCoverage] = []
    for i, req in enumerate(requirements):
        row = sim[i]
        best_idx = int(np.argmax(row))
        best_score = float(row[best_idx])
        if best_score >= covered_threshold:
            status = CoverageStatus.covered
        elif best_score >= partial_threshold:
            status = CoverageStatus.partial
        else:
            status = CoverageStatus.uncovered
        coverages.append(
            RequirementCoverage(
                requirement_id=req.id,
                requirement_text=req.text,
                status=status,
                best_score=round(best_score, 4),
                best_bullet_id=bullets[best_idx].id,
                best_bullet_text=bullets[best_idx].text,
            )
        )

    overall = round(float(np.mean([c.best_score for c in coverages])), 4)
    return GapReport(
        overall_score=overall,
        coverages=coverages,
        missing_skills=find_missing_skills(resume, jd),
    )
