"""Core data model for the resume tailoring tool.

The whole design hangs off one idea: a resume is *structured data*, not a text
blob. Every bullet carries a stable ``id`` so that downstream steps — gap
analysis, tailoring, the accept/reject editor, and (most importantly) grounding
validation — can refer to a specific bullet rather than parsing strings.

Provenance is the heart of the anti-fabrication design: a ``TailoredBullet``
must point back to the ``id`` of a real ``Bullet`` from the candidate's actual
resume. A tailored bullet with no valid source is, by definition, fabricated.
"""

from __future__ import annotations

import uuid
from enum import StrEnum

from pydantic import BaseModel, Field


def _new_id() -> str:
    """Short, stable id for bullets, entries, and requirements."""
    return uuid.uuid4().hex[:8]


class EntryKind(StrEnum):
    """What part of a resume an entry belongs to."""

    experience = "experience"
    project = "project"
    education = "education"


class Bullet(BaseModel):
    """A single resume bullet — the atomic unit of the whole system.

    ``id`` is stable and is what tailored output references. ``skills`` is an
    optional set of tags used for keyword-coverage checks in gap analysis.
    """

    id: str = Field(default_factory=_new_id)
    text: str
    skills: list[str] = Field(default_factory=list)


class Entry(BaseModel):
    """A job, project, or degree, with its bullets."""

    id: str = Field(default_factory=_new_id)
    kind: EntryKind
    title: str
    organization: str | None = None
    location: str | None = None
    date_range: str | None = None
    bullets: list[Bullet] = Field(default_factory=list)


class SkillGroup(BaseModel):
    """A labelled cluster of skills, e.g. 'Languages' -> [Python, SQL]."""

    category: str
    skills: list[str] = Field(default_factory=list)


class ContactInfo(BaseModel):
    location: str | None = None
    phone: str | None = None
    email: str | None = None
    links: list[str] = Field(default_factory=list)


class Resume(BaseModel):
    """A complete, structured resume."""

    name: str
    contact: ContactInfo = Field(default_factory=ContactInfo)
    summary: str | None = None
    entries: list[Entry] = Field(default_factory=list)
    skill_groups: list[SkillGroup] = Field(default_factory=list)

    def all_bullets(self) -> list[Bullet]:
        """Flatten every bullet across every entry into one list."""
        return [b for entry in self.entries for b in entry.bullets]

    def bullet_index(self) -> dict[str, Bullet]:
        """Map bullet id -> Bullet for O(1) provenance lookups."""
        return {b.id: b for b in self.all_bullets()}

    def all_skills(self) -> set[str]:
        """Every skill the candidate actually claims, lowercased."""
        skills: set[str] = set()
        for group in self.skill_groups:
            skills.update(s.strip().lower() for s in group.skills)
        for bullet in self.all_bullets():
            skills.update(s.strip().lower() for s in bullet.skills)
        return skills


class RequirementKind(StrEnum):
    required = "required"
    preferred = "preferred"
    responsibility = "responsibility"


class JobRequirement(BaseModel):
    """One atomic ask from a job description."""

    id: str = Field(default_factory=_new_id)
    text: str
    kind: RequirementKind = RequirementKind.required


class JobDescription(BaseModel):
    """A parsed job posting, decomposed into discrete requirements."""

    title: str
    company: str | None = None
    requirements: list[JobRequirement] = Field(default_factory=list)
    raw_text: str | None = None


class TailoredBullet(BaseModel):
    """A rephrased bullet produced by the LLM tailoring step.

    ``source_bullet_id`` MUST reference a real :class:`Bullet` in the original
    resume. This is the structural contract that makes fabrication detectable:
    no source id, or an unknown source id, means the content was invented.
    """

    text: str
    source_bullet_id: str
    rationale: str | None = None


class TailoredResume(BaseModel):
    """The LLM's tailored output, before grounding validation and editing."""

    summary: str | None = None
    bullets: list[TailoredBullet] = Field(default_factory=list)
