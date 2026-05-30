"""One-command demo: gap analysis + grounding on a real-shaped resume.

Run with:  python demo.py

Uses the offline TF-IDF backend so it works with no model download. Swap in
SentenceTransformerProvider() for meaningful absolute coverage scores.
"""

from __future__ import annotations

from resume_tailor import (
    Bullet,
    Entry,
    EntryKind,
    JobDescription,
    JobRequirement,
    Resume,
    SkillGroup,
    TailoredBullet,
    TailoredResume,
    TfidfEmbeddingProvider,
    analyze_gap,
)
from resume_tailor.grounding import GroundingValidator


def build_resume() -> Resume:
    return Resume(
        name="Joseph Dolan",
        summary="Business Information Systems student who ships software.",
        entries=[
            Entry(
                kind=EntryKind.experience,
                title="Consultation Agent",
                organization="Geek Squad",
                bullets=[
                    Bullet(
                        id="gs1",
                        text=(
                            "Serve as first point of contact for tech support, "
                            "diagnosing hardware, software, OS, and network issues."
                        ),
                    ),
                ],
            ),
            Entry(
                kind=EntryKind.project,
                title="Pulse - Async Service Health Monitor",
                bullets=[
                    Bullet(
                        id="pulse1",
                        text=(
                            "Designed and shipped v1.0.0 of an async "
                            "service-health monitor: scheduled checks, SQLite "
                            "persistence, and a REST API."
                        ),
                        skills=["Python", "FastAPI"],
                    ),
                    Bullet(
                        id="pulse2",
                        text=(
                            "Hardened the codebase with 34 unit tests, strict "
                            "mypy type checking, and ruff linting."
                        ),
                    ),
                ],
            ),
        ],
        skill_groups=[SkillGroup(category="Languages", skills=["Python", "SQL"])],
    )


def build_jd() -> JobDescription:
    return JobDescription(
        title="Software Engineering Intern",
        requirements=[
            JobRequirement(text="Build and ship REST APIs in Python"),
            JobRequirement(text="Write automated tests and maintain code quality"),
            JobRequirement(text="Operate containerized services on Kubernetes"),
        ],
        raw_text="We use Python and Kubernetes in production.",
    )


def main() -> None:
    resume = build_resume()
    jd = build_jd()
    provider = TfidfEmbeddingProvider()

    print("=" * 70)
    print("GAP ANALYSIS")
    print("=" * 70)
    report = analyze_gap(resume, jd, provider)
    print(f"Overall coverage score: {report.overall_score:.3f}\n")
    for c in report.coverages:
        match = c.best_bullet_text[:55] + "..." if c.best_bullet_text else "(none)"
        print(f"  [{c.status.value:9}] {c.requirement_text}")
        print(f"              best match -> {match}\n")
    if report.missing_skills:
        print(f"  Missing skill keywords: {', '.join(report.missing_skills)}\n")

    print("=" * 70)
    print("GROUNDING VALIDATION (two tailored bullets: one honest, one faked)")
    print("=" * 70)
    tailored = TailoredResume(
        bullets=[
            # Faithful rephrase of pulse1 -> should pass.
            TailoredBullet(
                text=(
                    "Built and shipped a Python REST API for an async "
                    "service-health monitor with scheduled checks."
                ),
                source_bullet_id="pulse1",
            ),
            # Invents a metric pulse1 never claimed -> should be rejected.
            TailoredBullet(
                text=(
                    "Built a Python REST API that improved system uptime "
                    "by 99% across the org."
                ),
                source_bullet_id="pulse1",
            ),
        ]
    )
    grounding = GroundingValidator(provider, semantic_floor=0.10).validate(
        tailored, resume
    )
    for result in grounding.results:
        verdict = "GROUNDED" if result.is_grounded else "REJECTED"
        print(f"\n  [{verdict}] {result.tailored_text}")
        for v in result.violations:
            print(f"      - {v.kind.value}: {v.detail}")
    print()


if __name__ == "__main__":
    main()
