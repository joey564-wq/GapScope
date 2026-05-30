# resume-tailor

A tool that maps a candidate's **real** experience against a target job
description and re-presents it for that job — **without ever fabricating
experience**.

This repo is the keystone of the project: the structured data model, the
explainable gap analysis, and the grounding (anti-fabrication) validator. The
LLM tailoring step, REST API, and React accept/reject editor build on top of
these.

## The design decision that defines this project: integrity

A resume tailoring tool can either **fabricate** (invent skills, inflate titles,
bolt on metrics that never happened) or **truthfully re-present** (rephrase,
reorder, and re-emphasize the candidate's *actual* experience to surface what's
most relevant). This tool does the second, and enforces it in code.

Every rephrased bullet must trace back to a real bullet from the candidate's
resume, and is checked against three gates before it's allowed through:

1. **Structural** — the tailored bullet names a `source_bullet_id` that exists
   in the original resume. No source, or an unknown source, means the content
   has no origin and is rejected.
2. **Metric** — every number in the tailored text must also appear in its source
   bullet. This catches the most common and most damaging fabrication: invented
   metrics like *"improved performance by 40%"* added to a bullet that never
   quantified anything.
3. **Semantic** — the tailored text must stay close in meaning to its source
   (cosine similarity above a floor). Rephrasing is fine; drifting into a
   different claim is not.

The validator never edits text — it reports violations, so the editor UI can
flag or reject a suggestion and the LLM step can be re-prompted. It **fails
closed**: anything the checks can't vouch for is treated as ungrounded.

## Architecture

```
resume_tailor/
  models.py        Structured Resume / JobDescription / TailoredResume (Pydantic).
                   Every Bullet has a stable id; tailored bullets reference it.
  embeddings.py    EmbeddingProvider behind one interface:
                     - TfidfEmbeddingProvider  (zero-dependency, offline, for CI)
                     - SentenceTransformerProvider  (real semantic embeddings)
  gap_analysis.py  analyze_gap(): per-requirement coverage + missing-skill
                   keywords. Deterministic and explainable — no LLM here.
  grounding.py     GroundingValidator: the three-gate anti-fabrication check.
```

The embedding layer is swappable on purpose. TF-IDF matches on shared *words*
and is great for fast offline tests; a sentence model matches on *meaning*
("shipped a REST API" ≈ "built and deployed web services") and is what you run
in production. Gap-analysis **ranking** (which bullet best matches a
requirement) is robust across both; absolute coverage **scores** are only
meaningful with the semantic backend.

## Quick start

```bash
pip install -e ".[dev]"     # pydantic, numpy, scikit-learn, pytest, mypy, ruff
python demo.py              # end-to-end: gap analysis + grounding, offline

# For real semantic scores:
pip install -e ".[semantic]"   # adds sentence-transformers
```

In code, swap the backend without touching anything else:

```python
from resume_tailor import analyze_gap, SentenceTransformerProvider
report = analyze_gap(resume, jd, SentenceTransformerProvider("all-MiniLM-L6-v2"))
```

## Quality bar

```bash
pytest          # 16 tests: model, gap analysis, grounding
mypy resume_tailor   # strict mode, clean
ruff check .         # clean
```

## What's next (not in this keystone)

- LLM tailoring endpoint: prompt for tailored bullets as structured JSON, validate
  against the Pydantic schema, then run `GroundingValidator` and re-prompt on any
  violation.
- FastAPI service wrapping `analyze_gap` and the tailoring + grounding loop.
- React editor: render the structured resume, show each AI suggestion as an
  original-vs-tailored diff, accept/reject per bullet.
- `.docx` export via `python-docx`.
- Resume import parsing (deliberately deferred — it's a rabbit hole and not core
  to the value).
