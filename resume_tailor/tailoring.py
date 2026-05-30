"""LLM-powered resume tailoring with privacy enforced by design.

Privacy guarantees that live in this module's architecture (not just in docs):

1. DATA MINIMIZATION. Only bullet ids + bullet text and the job-description
   requirements are ever sent to the LLM. The candidate's name, email, phone,
   and links never enter the prompt. This is enforced two ways: `build_user_prompt`
   has no access to identity/contact fields by construction (it only receives
   bullets and the JD), and `tailor_resume` runs `assert_no_pii_in_prompt` as a
   fail-closed runtime guard before every network call.

2. LOCAL REASSEMBLY. Tailoring returns only rephrased bullet text keyed by
   source id. The full resume — name and contact included — is rebuilt locally
   via `rebuild_resume`, from data that never left this server.

3. NO STORAGE. Nothing here persists anything. Inputs exist only for the
   duration of the call. (The API layer must also avoid logging resume content.)

Fabrication is prevented by the grounding validator: every tailored bullet must
trace to a real source bullet, introduce no new numbers, and stay semantically
close to its source. Ungrounded output is re-prompted with the specific reasons,
and if still bad after `max_attempts`, surfaced to the UI flagged rather than
silently used.
"""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from .embeddings import EmbeddingProvider
from .gap_analysis import GapReport
from .grounding import GroundingReport, GroundingValidator
from .models import (
    Bullet,
    JobDescription,
    Resume,
    TailoredBullet,
    TailoredResume,
)

# --------------------------------------------------------------------------- #
# LLM clients (swappable; network calls are isolated here)
# --------------------------------------------------------------------------- #


@runtime_checkable
class LLMClient(Protocol):
    """Anything that turns a (system, user) prompt pair into a text response."""

    def complete(self, system: str, user: str) -> str: ...


class GeminiClient:
    """Google Gemini 2.5 Flash via the google-genai SDK.

    Uses the paid API tier (set GEMINI_API_KEY), which does not train on your
    inputs — the right privacy posture for handling other people's resumes.
    Requests JSON directly with response_mime_type for reliable structured output.

    Install: pip install google-genai
    """

    def __init__(
        self,
        model: str = "gemini-2.5-flash",
        api_key_env: str = "GEMINI_API_KEY",
        temperature: float = 0.2,
    ) -> None:
        try:
            from google import genai
        except ImportError as exc:  # pragma: no cover - optional dep
            raise ImportError(
                "GeminiClient requires google-genai. Install: pip install google-genai"
            ) from exc
        self._genai = genai
        self._client = genai.Client(api_key=os.environ[api_key_env])
        self._model = model
        self._temperature = temperature

    def complete(self, system: str, user: str) -> str:  # pragma: no cover - network
        resp = self._client.models.generate_content(
            model=self._model,
            contents=user,
            config=self._genai.types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                temperature=self._temperature,
            ),
        )
        return resp.text or ""


class OllamaClient:
    """Local model via Ollama, for free offline development.

    No API key, no cost, and resume data never leaves your machine — ideal while
    iterating on the prompt. Swap to GeminiClient for the deployed app.

    Run a model first, e.g.:  ollama run llama3.1
    """

    def __init__(
        self,
        model: str = "llama3.1",
        host: str = "http://localhost:11434",
    ) -> None:
        self._model = model
        self._host = host

    def complete(self, system: str, user: str) -> str:  # pragma: no cover - network
        import httpx

        resp = httpx.post(
            f"{self._host}/api/chat",
            json={
                "model": self._model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "stream": False,
                "format": "json",
            },
            timeout=120,
        )
        resp.raise_for_status()
        return str(resp.json()["message"]["content"])


# --------------------------------------------------------------------------- #
# Prompting (PII-free by construction — accepts only bullets + JD)
# --------------------------------------------------------------------------- #

SYSTEM_PROMPT = """You rewrite resume bullets to better match a job description.

HARD RULES — obey every one:
- ONLY rephrase, reorder, and re-emphasise the candidate's real bullets.
- NEVER invent skills, employers, titles, or metrics. NEVER add a number that is
  not already present in the source bullet.
- Every output bullet MUST include the id of the source bullet it was built from.
- Keep each bullet concise, active-voice, and achievement-oriented.
- Return ONLY valid JSON, no prose, no markdown fences.

JSON schema:
{"bullets":[{"source_bullet_id":"<id>","text":"<rephrased>","rationale":"<short why>"}]}

EXAMPLE
Source bullets:
- id=ex1: "Helped customers with computer problems at the store."
Target requirement: "Provide technical troubleshooting for customers."
GOOD output (faithful, invents nothing):
{"bullets":[{"source_bullet_id":"ex1",
  "text":"Diagnosed and resolved customer hardware and software issues.",
  "rationale":"Aligns wording with the requirement; adds no new facts."}]}
BAD output (REJECTED — invents a metric absent from the source):
{"bullets":[{"source_bullet_id":"ex1",
  "text":"Resolved 500+ customer issues with a 98% satisfaction rate.",
  "rationale":"..."}]}
"""


def build_user_prompt(
    bullets: Sequence[Bullet],
    jd: JobDescription,
    gap_report: GapReport | None = None,
    violations: str | None = None,
) -> str:
    """Construct the user prompt from ONLY bullets (id + text) and the JD.

    This function deliberately has no parameter for the candidate's name or
    contact details — identity data cannot leak through a channel that doesn't
    exist. The JD describes the employer, not the candidate, so it carries no
    candidate PII.
    """
    bullet_lines = "\n".join(f'- id={b.id}: "{b.text}"' for b in bullets)
    req_lines = "\n".join(f"- {r.text}" for r in jd.requirements)

    prompt = (
        f"JOB TITLE: {jd.title}\n\n"
        f"JOB REQUIREMENTS:\n{req_lines}\n\n"
        f"CANDIDATE'S REAL BULLETS (rephrase only these; keep their ids):\n"
        f"{bullet_lines}\n"
    )

    # Quality lever: tell the model which requirements are weakly covered so it
    # focuses its rephrasing where it matters most. Uses only requirement text
    # and bullet ids — still no PII.
    if gap_report is not None:
        weak = [c for c in gap_report.coverages if c.status.value != "covered"]
        if weak:
            focus = "\n".join(
                f"- requirement \"{c.requirement_text}\" is weakly covered"
                f" (best existing match: id={c.best_bullet_id})"
                for c in weak
            )
            prompt += (
                "\nFOCUS: these requirements are currently weak — prioritise "
                f"rephrasing the related bullets to surface relevant real "
                f"experience:\n{focus}\n"
            )

    if violations:
        prompt += (
            "\nYour previous attempt was REJECTED for these reasons. Fix them and "
            f"return corrected JSON:\n{violations}\n"
        )
    return prompt


def assert_no_pii_in_prompt(prompt: str, resume: Resume) -> None:
    """Fail-closed guard: identity/contact values must not appear in the prompt.

    Belt-and-suspenders alongside build_user_prompt's construction. If a future
    edit ever wires PII into the prompt path, this raises before any network call.

    Note the honest limitation: this strips *structured* identity fields. It
    cannot guarantee a free-text bullet contains no personal data the candidate
    chose to write there — which is exactly why the no-training paid tier and the
    no-storage policy still matter as defense in depth.
    """
    contact = resume.contact
    candidates = [resume.name, contact.email, contact.phone, *(contact.links or [])]
    leaked = [value for value in candidates if value and value in prompt]
    if leaked:
        raise ValueError(
            "Refusing to send prompt: candidate PII detected in LLM payload: "
            + ", ".join(leaked)
        )


# --------------------------------------------------------------------------- #
# Parsing + the tailoring loop
# --------------------------------------------------------------------------- #


def parse_tailored(raw: str) -> TailoredResume:
    """Parse the model's JSON into a validated TailoredResume.

    Tolerates accidental markdown fences. Raises on malformed input so the loop
    can re-prompt.
    """
    text = raw.strip()
    if text.startswith("```"):
        text = text.removeprefix("```json").removeprefix("```").removesuffix("```")
        text = text.strip()
    data = json.loads(text)
    bullets = [TailoredBullet(**b) for b in data["bullets"]]
    return TailoredResume(summary=data.get("summary"), bullets=bullets)


def tailor_resume(
    resume: Resume,
    jd: JobDescription,
    provider: EmbeddingProvider,
    llm: LLMClient,
    *,
    gap_report: GapReport | None = None,
    validator: GroundingValidator | None = None,
    max_attempts: int = 3,
) -> tuple[TailoredResume, GroundingReport]:
    """Generate tailored bullets, enforcing privacy and anti-fabrication.

    Sends only bullet ids/text + JD to the LLM (PII-guarded), validates each
    attempt against the grounding rules, and re-prompts with the specific
    violations until everything is grounded or `max_attempts` is reached. Returns
    the most-grounded attempt; any still-flagged bullets carry their violations
    so the UI can surface them rather than hide them.

    Pass a `validator` to match the embedding backend: the default semantic floor
    suits sentence-transformers, but the offline TF-IDF backend needs a lower
    floor (see GroundingValidator). If omitted, a default validator is used.
    """
    bullets = resume.all_bullets()
    if validator is None:
        validator = GroundingValidator(provider)
    violations_text: str | None = None
    best: tuple[TailoredResume, GroundingReport] | None = None

    for _ in range(max_attempts):
        user = build_user_prompt(bullets, jd, gap_report, violations_text)
        assert_no_pii_in_prompt(user, resume)  # fail closed before any network call

        raw = llm.complete(SYSTEM_PROMPT, user)
        try:
            tailored = parse_tailored(raw)
        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
            violations_text = "Output was not valid JSON matching the schema."
            continue

        report = validator.validate(tailored, resume)
        if best is None or len(report.grounded_bullets) > len(
            best[1].grounded_bullets
        ):
            best = (tailored, report)
        if report.all_grounded:
            return tailored, report

        violations_text = "\n".join(
            f"- {v.kind.value}: {v.detail}" for v in report.violations
        )

    assert best is not None  # loop runs at least once
    return best


# --------------------------------------------------------------------------- #
# Local reassembly (PII never left this server)
# --------------------------------------------------------------------------- #


def rebuild_resume(resume: Resume, replacements: dict[str, str]) -> Resume:
    """Return a new Resume with bullet text replaced by id, everything else kept.

    `replacements` maps bullet id -> accepted tailored text (typically the bullets
    the user accepted in the editor). Name, contact, dates, and structure are
    preserved from the original local copy — the model never saw them.
    """
    updated = resume.model_copy(deep=True)
    for entry in updated.entries:
        for bullet in entry.bullets:
            if bullet.id in replacements:
                bullet.text = replacements[bullet.id]
    return updated
