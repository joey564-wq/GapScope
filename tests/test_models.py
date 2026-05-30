"""Tests for the structured resume model."""

from __future__ import annotations

from resume_tailor import Bullet, Entry, EntryKind, Resume


def test_all_bullets_flattens_every_entry(resume: Resume) -> None:
    ids = {b.id for b in resume.all_bullets()}
    assert ids == {"gs1", "gs2", "pulse1", "pulse2", "campus1"}


def test_bullet_index_maps_id_to_bullet(resume: Resume) -> None:
    index = resume.bullet_index()
    assert index["pulse1"].text.startswith("Designed and shipped")
    assert set(index) == {b.id for b in resume.all_bullets()}


def test_all_skills_unions_groups_and_bullet_tags(resume: Resume) -> None:
    skills = resume.all_skills()
    # From skill groups:
    assert "python" in skills
    assert "postgresql" in skills
    # From a bullet's own tags:
    assert "fastapi" in skills
    # Everything is lowercased:
    assert all(s == s.lower() for s in skills)


def test_auto_ids_are_unique_when_not_supplied() -> None:
    entry = Entry(
        kind=EntryKind.project,
        title="Test",
        bullets=[Bullet(text="a"), Bullet(text="b"), Bullet(text="c")],
    )
    ids = [b.id for b in entry.bullets]
    assert len(set(ids)) == 3
