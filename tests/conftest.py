"""Shared fixtures: a real-shaped resume and a sample job description.

The resume mirrors the candidate's actual content so test behaviour is concrete
rather than abstract — you can read a failing assertion and know what it means.
"""

from __future__ import annotations

import pytest

from resume_tailor import (
    Bullet,
    ContactInfo,
    Entry,
    EntryKind,
    JobDescription,
    JobRequirement,
    Resume,
    SkillGroup,
    TfidfEmbeddingProvider,
)
from resume_tailor.models import RequirementKind


@pytest.fixture
def provider() -> TfidfEmbeddingProvider:
    return TfidfEmbeddingProvider()


@pytest.fixture
def resume() -> Resume:
    return Resume(
        name="Joseph Dolan",
        contact=ContactInfo(
            location="San Francisco Bay Area",
            email="jdolan564@gmail.com",
            links=["github.com/joey564-wq"],
        ),
        summary="Business Information Systems student who ships software.",
        entries=[
            Entry(
                id="geeksquad",
                kind=EntryKind.experience,
                title="Consultation Agent",
                organization="Geek Squad",
                date_range="Aug 2025 - Present",
                bullets=[
                    Bullet(
                        id="gs1",
                        text=(
                            "Serve as first point of contact for tech support, "
                            "diagnosing hardware, software, OS, and network issues "
                            "across Windows, macOS, iOS, and Android devices."
                        ),
                    ),
                    Bullet(
                        id="gs2",
                        text=(
                            "Own active work orders end-to-end: reproduce defects, "
                            "document symptoms, and write handoff notes for in-store "
                            "technicians to reduce rework on escalated tickets."
                        ),
                    ),
                ],
            ),
            Entry(
                id="pulse",
                kind=EntryKind.project,
                title="Pulse - Async Service Health Monitor",
                bullets=[
                    Bullet(
                        id="pulse1",
                        text=(
                            "Designed and shipped v1.0.0 of an async service-health "
                            "monitor in 4 weeks: scheduled checks, SQLite persistence, "
                            "REST API, and a vanilla-JS dashboard."
                        ),
                        skills=["Python", "FastAPI", "SQLite"],
                    ),
                    Bullet(
                        id="pulse2",
                        text=(
                            "Hardened the codebase with 34 unit tests, strict mypy "
                            "type checking, and ruff linting."
                        ),
                        skills=["pytest", "mypy", "ruff"],
                    ),
                ],
            ),
            Entry(
                id="campus",
                kind=EntryKind.project,
                title="Campus Exchange - Student Marketplace",
                bullets=[
                    Bullet(
                        id="campus1",
                        text=(
                            "Built and deployed a full-stack student marketplace "
                            "across 3 sprints with React and AWS Lambda on a 3-role "
                            "Agile team."
                        ),
                        skills=["React", "AWS Lambda", "Agile"],
                    ),
                ],
            ),
        ],
        skill_groups=[
            SkillGroup(
                category="Languages",
                skills=["Python", "JavaScript", "Swift", "SQL"],
            ),
            SkillGroup(
                category="Cloud",
                skills=["AWS Lambda", "Supabase", "PostgreSQL"],
            ),
        ],
    )


@pytest.fixture
def job_description() -> JobDescription:
    return JobDescription(
        title="Software Engineering Intern",
        company="Acme",
        requirements=[
            JobRequirement(
                id="r_api",
                text="Build and ship REST APIs in Python",
                kind=RequirementKind.required,
            ),
            JobRequirement(
                id="r_test",
                text="Write automated tests and maintain code quality",
                kind=RequirementKind.required,
            ),
            JobRequirement(
                id="r_support",
                text="Provide technical support and troubleshoot customer issues",
                kind=RequirementKind.responsibility,
            ),
            JobRequirement(
                id="r_k8s",
                text="Operate containerized services on Kubernetes",
                kind=RequirementKind.preferred,
            ),
        ],
        raw_text="We use Python, React, and Kubernetes in production.",
    )
