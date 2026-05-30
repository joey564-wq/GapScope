"""Tests for the tailoring loop, privacy guard, and local reassembly.

A FakeLLM records the prompts it receives and returns scripted responses, so
tests are fully offline and can assert exactly what was (and wasn't) sent.
"""

from __future__ import annotations

import json

import pytest

from resume_tailor import GroundingValidator, Resume, TfidfEmbeddingProvider
from resume_tailor.tailoring import (
    assert_no_pii_in_prompt,
    build_user_prompt,
    parse_tailored,
    rebuild_resume,
    tailor_resume,
)


class FakeLLM:
    """Returns queued responses; remembers every (system, user) it was asked."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        return self._responses.pop(0)


def _json(*bullets: dict) -> str:
    return json.dumps({"bullets": list(bullets)})


def _tfidf_validator(provider: TfidfEmbeddingProvider) -> GroundingValidator:
    # TF-IDF yields low absolute similarity on short rephrases; use a floor
    # appropriate to that backend (semantic embeddings would use the default).
    return GroundingValidator(provider, semantic_floor=0.10)


# --------------------------------------------------------------------------- #
# Privacy: the central guarantee
# --------------------------------------------------------------------------- #


def test_prompt_never_contains_identity_or_contact(resume: Resume, job_description):
    """The compiled prompt must not leak name, email, phone, or links."""
    prompt = build_user_prompt(resume.all_bullets(), job_description)
    assert resume.name not in prompt
    assert resume.contact.email is not None and resume.contact.email not in prompt
    for link in resume.contact.links:
        assert link not in prompt
    # But it SHOULD contain the bullet content the model needs to rephrase.
    assert "service-health monitor" in prompt


def test_llm_only_ever_sees_pii_free_prompt(resume, job_description):
    """End-to-end: drive the loop and inspect what the LLM actually received."""
    llm = FakeLLM([_json({"source_bullet_id": "pulse1", "text": "Shipped a REST API.",
                          "rationale": "ok"})])
    prov = TfidfEmbeddingProvider()
    tailor_resume(resume, job_description, prov, llm, validator=_tfidf_validator(prov))
    assert llm.calls, "LLM should have been called"
    _, user_prompt = llm.calls[0]
    assert resume.name not in user_prompt
    assert resume.contact.email not in user_prompt
    for link in resume.contact.links:
        assert link not in user_prompt


def test_pii_guard_raises_if_pii_present(resume):
    """The fail-closed guard catches PII that somehow reached the prompt."""
    poisoned = f"...some prompt containing {resume.contact.email} by mistake..."
    with pytest.raises(ValueError, match="PII"):
        assert_no_pii_in_prompt(poisoned, resume)


# --------------------------------------------------------------------------- #
# The grounding-aware tailoring loop
# --------------------------------------------------------------------------- #


def test_faithful_rephrase_returns_grounded(resume, job_description):
    llm = FakeLLM([
        _json({"source_bullet_id": "pulse1",
               "text": "Shipped an async service-health monitor with a REST API.",
               "rationale": "faithful"})
    ])
    prov = TfidfEmbeddingProvider()
    tailored, report = tailor_resume(
        resume, job_description, prov, llm, validator=_tfidf_validator(prov)
    )
    assert report.all_grounded
    assert tailored.bullets[0].source_bullet_id == "pulse1"
    assert len(llm.calls) == 1  # no re-prompt needed


def test_fabricated_metric_triggers_reprompt(resume, job_description):
    """First attempt invents '60%'; loop must reject and re-prompt with the reason."""
    bad = _json({"source_bullet_id": "pulse1",
                 "text": "Shipped a monitor, improving uptime by 60%.",
                 "rationale": "nope"})
    good = _json({"source_bullet_id": "pulse1",
                  "text": "Shipped an async service-health monitor with a REST API.",
                  "rationale": "fixed"})
    llm = FakeLLM([bad, good])
    prov = TfidfEmbeddingProvider()
    tailored, report = tailor_resume(
        resume, job_description, prov, llm, validator=_tfidf_validator(prov)
    )
    assert report.all_grounded
    assert len(llm.calls) == 2  # re-prompted once
    # The second prompt must include the violation feedback.
    _, second_prompt = llm.calls[1]
    assert "REJECTED" in second_prompt
    assert "60" in second_prompt  # the fabricated number is named back to the model


def test_invalid_json_triggers_reprompt(resume, job_description):
    llm = FakeLLM([
        "not json at all",
        _json({"source_bullet_id": "pulse2",
               "text": "Wrote 34 unit tests with strict mypy checking.",
               "rationale": "ok"}),
    ])
    prov = TfidfEmbeddingProvider()
    tailored, report = tailor_resume(
        resume, job_description, prov, llm, validator=_tfidf_validator(prov)
    )
    assert len(llm.calls) == 2
    assert report.all_grounded


def test_parse_tolerates_markdown_fences():
    raw = '```json\n{"bullets":[{"source_bullet_id":"x","text":"y"}]}\n```'
    parsed = parse_tailored(raw)
    assert parsed.bullets[0].source_bullet_id == "x"


# --------------------------------------------------------------------------- #
# Local reassembly preserves the PII the model never saw
# --------------------------------------------------------------------------- #


def test_rebuild_resume_preserves_contact_and_replaces_text(resume: Resume):
    new = rebuild_resume(resume, {"pulse1": "Rephrased shipping bullet."})
    # Identity/contact preserved from the local copy:
    assert new.name == resume.name
    assert new.contact.email == resume.contact.email
    # Targeted bullet replaced:
    idx = new.bullet_index()
    assert idx["pulse1"].text == "Rephrased shipping bullet."
    # Untargeted bullet untouched:
    assert idx["gs1"].text == resume.bullet_index()["gs1"].text
    # Original object not mutated:
    assert resume.bullet_index()["pulse1"].text != "Rephrased shipping bullet."
