"""Tests for grounding validation — proving fabrication is caught."""

from __future__ import annotations

from resume_tailor import (
    GroundingValidator,
    Resume,
    TailoredBullet,
    TailoredResume,
    TfidfEmbeddingProvider,
    ViolationKind,
)


def _validator(provider: TfidfEmbeddingProvider) -> GroundingValidator:
    # Floor kept modest because TF-IDF similarity on short rephrases is low;
    # a real sentence model scores far higher and the floor would rise.
    return GroundingValidator(provider, semantic_floor=0.15)


def test_faithful_rephrase_is_grounded(
    resume: Resume, provider: TfidfEmbeddingProvider
) -> None:
    tailored = TailoredResume(
        bullets=[
            TailoredBullet(
                text=(
                    "Shipped v1.0.0 of an async service-health monitor with "
                    "scheduled checks, SQLite persistence, and a REST API."
                ),
                source_bullet_id="pulse1",
            )
        ]
    )
    report = _validator(provider).validate(tailored, resume)
    assert report.all_grounded
    assert report.results[0].violations == []


def test_missing_source_is_rejected(
    resume: Resume, provider: TfidfEmbeddingProvider
) -> None:
    tailored = TailoredResume(
        bullets=[TailoredBullet(text="Did some great work.", source_bullet_id="")]
    )
    report = _validator(provider).validate(tailored, resume)
    assert not report.all_grounded
    assert report.results[0].violations[0].kind is ViolationKind.missing_source


def test_unknown_source_is_rejected(
    resume: Resume, provider: TfidfEmbeddingProvider
) -> None:
    tailored = TailoredResume(
        bullets=[
            TailoredBullet(text="Plausible-sounding bullet.", source_bullet_id="ghost")
        ]
    )
    report = _validator(provider).validate(tailored, resume)
    assert not report.all_grounded
    assert report.results[0].violations[0].kind is ViolationKind.unknown_source


def test_fabricated_metric_is_caught(
    resume: Resume, provider: TfidfEmbeddingProvider
) -> None:
    # pulse1 never claims a percentage; inventing "by 60%" must be flagged.
    tailored = TailoredResume(
        bullets=[
            TailoredBullet(
                text=(
                    "Designed and shipped an async service-health monitor, "
                    "improving uptime by 60%."
                ),
                source_bullet_id="pulse1",
            )
        ]
    )
    report = _validator(provider).validate(tailored, resume)
    kinds = {v.kind for v in report.results[0].violations}
    assert ViolationKind.fabricated_metric in kinds
    assert not report.results[0].is_grounded


def test_preserved_metric_is_allowed(
    resume: Resume, provider: TfidfEmbeddingProvider
) -> None:
    # pulse2 genuinely says "34 unit tests"; keeping that number is fine.
    tailored = TailoredResume(
        bullets=[
            TailoredBullet(
                text="Wrote 34 unit tests with strict mypy type checking.",
                source_bullet_id="pulse2",
            )
        ]
    )
    report = _validator(provider).validate(tailored, resume)
    kinds = {v.kind for v in report.results[0].violations}
    assert ViolationKind.fabricated_metric not in kinds


def test_semantic_drift_is_caught(
    resume: Resume, provider: TfidfEmbeddingProvider
) -> None:
    # Claims something unrelated to the support bullet it cites.
    tailored = TailoredResume(
        bullets=[
            TailoredBullet(
                text="Led a machine learning research team publishing papers.",
                source_bullet_id="gs1",
            )
        ]
    )
    report = GroundingValidator(provider, semantic_floor=0.30).validate(
        tailored, resume
    )
    kinds = {v.kind for v in report.results[0].violations}
    assert ViolationKind.semantic_drift in kinds
