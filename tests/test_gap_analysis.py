"""Tests for gap analysis."""

from __future__ import annotations

from resume_tailor import (
    CoverageStatus,
    JobDescription,
    Resume,
    TfidfEmbeddingProvider,
    analyze_gap,
)


def test_requirements_match_the_right_bullets(
    resume: Resume,
    job_description: JobDescription,
    provider: TfidfEmbeddingProvider,
) -> None:
    """Ranking is the backend-robust signal: the right bullet wins.

    Absolute status buckets depend on the embedding backend (see analyze_gap's
    threshold note), so we assert the property that holds for both TF-IDF and
    semantic models: each requirement's best match is the correct bullet.
    """
    report = analyze_gap(resume, job_description, provider)
    by_id = {c.requirement_id: c for c in report.coverages}

    # "Build and ship REST APIs in Python" -> the Pulse shipping bullet.
    assert by_id["r_api"].best_bullet_id == "pulse1"
    # "Write automated tests" -> the testing bullet.
    assert by_id["r_test"].best_bullet_id == "pulse2"


def test_real_matches_outrank_genuine_gaps(
    resume: Resume,
    job_description: JobDescription,
    provider: TfidfEmbeddingProvider,
) -> None:
    """The requirements the candidate can speak to should score above the
    Kubernetes requirement they genuinely cannot."""
    report = analyze_gap(resume, job_description, provider)
    by_id = {c.requirement_id: c for c in report.coverages}
    assert by_id["r_api"].best_score > by_id["r_k8s"].best_score
    assert by_id["r_test"].best_score > by_id["r_k8s"].best_score


def test_support_requirement_maps_to_geeksquad(
    resume: Resume,
    job_description: JobDescription,
    provider: TfidfEmbeddingProvider,
) -> None:
    report = analyze_gap(resume, job_description, provider)
    by_id = {c.requirement_id: c for c in report.coverages}
    support = by_id["r_support"]
    assert support.best_bullet_id in {"gs1", "gs2"}


def test_kubernetes_is_a_real_gap(
    resume: Resume,
    job_description: JobDescription,
    provider: TfidfEmbeddingProvider,
) -> None:
    report = analyze_gap(resume, job_description, provider)
    by_id = {c.requirement_id: c for c in report.coverages}
    # The candidate has no container/k8s experience; this should score low.
    assert by_id["r_k8s"].status is CoverageStatus.uncovered
    # And kubernetes should show up as a missing skill keyword.
    assert "kubernetes" in report.missing_skills


def test_overall_score_is_a_unit_mean(
    resume: Resume,
    job_description: JobDescription,
    provider: TfidfEmbeddingProvider,
) -> None:
    report = analyze_gap(resume, job_description, provider)
    assert 0.0 <= report.overall_score <= 1.0
    expected = sum(c.best_score for c in report.coverages) / len(report.coverages)
    assert abs(report.overall_score - expected) < 1e-3


def test_empty_resume_yields_all_uncovered(
    job_description: JobDescription,
    provider: TfidfEmbeddingProvider,
) -> None:
    empty = Resume(name="Nobody")
    report = analyze_gap(empty, job_description, provider)
    assert report.overall_score == 0.0
    assert all(c.status is CoverageStatus.uncovered for c in report.coverages)
