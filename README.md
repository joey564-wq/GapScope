# GapScope

**See exactly where your resume falls short of a job — and how to close the gap.**

GapScope takes your resume and a target job description, scores how well your real
experience covers each requirement, and recommends concrete ways to close the gaps
it finds — certifications, courses, projects, and the kind of experience to seek.

It is built around one principle: **honesty about where you stand.** GapScope does
not rewrite your resume or invent experience. It tells you the truth about your fit
for a role, and points you toward real ways to improve it.

🔗 **Live app:** https://witty-cliff-06d2dee10.7.azurestaticapps.net

---

## What it does

GapScope does three things:

1. **Analyzes the gap.** It compares your resume against a job description's
   requirements and finds, for each requirement, the bullet in your experience that
   best matches it.
2. **Scores coverage.** Each requirement is rated *covered*, *partial*, or
   *uncovered*, with an overall coverage score, so you can see at a glance how strong
   a candidate you are for that specific role.
3. **Recommends ways to close the gap.** For requirements you don't yet meet, it
   suggests certifications, courses, project ideas, and roles or internships to
   pursue — advice for genuinely building the experience, never fabricating it.

## Why it's built this way

A tool like this could take a shortcut: invent skills, inflate titles, or pad a
resume with experience the candidate doesn't have. GapScope refuses to. The analysis
reports real coverage without inflating it, and the recommendations are about
acquiring experience in the future — they are never presented as things you already
have. The value is an honest read on your fit and a real plan to improve it.

## How to use it

Paste your resume and a job description into the two boxes, then run the analysis.
Input uses a light text format:

- Resume entries start with `#` (e.g. `# Software Engineer @ Acme | 2023 - Present`)
- Bullets and job requirements each start with `-` on their own line
- `Name:`, `Contact:`, and `Skills:` lines are recognized in the resume box
- `Title:` is recognized in the job description box

The **Load example** button fills both boxes with a working sample so you can see the
format and try it instantly.

## Architecture

```
gapscope/
  backend (FastAPI)
    resume_tailor/
      models.py         Pydantic models: Resume, Entry, Bullet (stable IDs),
                        JobDescription / JobRequirement, ContactInfo, SkillGroup
      embeddings.py     Swappable EmbeddingProvider:
                          - TF-IDF (offline, zero-dependency, for CI/local)
                          - sentence-transformers / hosted API (semantic)
      gap_analysis.py   analyze_gap() -> GapReport (per-requirement coverage,
                        overall score, missing-skill keywords)
      recommendations.py  LLM-generated, PII-free gap-closing suggestions
    api/main.py         FastAPI service: /health, /analyze, /recommend

  frontend (React + Vite + TypeScript)
    parse.ts            Paste-as-text -> structured Resume / JobDescription
    api.ts              Typed calls to the backend
    types.ts            TypeScript mirrors of the backend models
    App.tsx, App.css    Input + gap-analysis UI ("Blueprint & Seal" theme)
```

The embedding layer is swappable on purpose. TF-IDF matches on shared *words* and is
great for fast offline runs; a sentence model matches on *meaning* and is what gives
meaningful absolute coverage scores. Recommendations run through a small LLM client
abstraction (`LLMClient`) so the same code uses Gemini in production and a local
Ollama model in development.

### Privacy by design

Recommendations are generated from job-requirement text only — which describes the
employer, not the candidate. No resume content, name, email, or contact details ever
enter that prompt path, by construction. Resume data is processed in memory and is
not stored or logged.

## Tech stack

**Backend:** Python 3.12, FastAPI, Pydantic, scikit-learn (TF-IDF),
sentence-transformers (optional semantic embeddings)
**Frontend:** React, Vite, TypeScript
**LLM:** Gemini 2.5 Flash (production), Ollama / llama3.2 (local dev)
**Infrastructure:** Docker, Azure Container Apps (backend), Azure Static Web Apps
(frontend), Azure Container Registry
**Tooling:** GitHub Actions CI (ruff, mypy, pytest), ruff, mypy

## Running it locally

Backend:

```bash
pip install -e ".[dev]"          # core + lint/type/test tools
# optional: pip install -e ".[semantic]"   # real semantic embeddings
# optional: pip install -e ".[gemini]"     # Gemini client

uvicorn api.main:app --reload --port 8000
```

For recommendations locally, run a model with [Ollama](https://ollama.com)
(`ollama run llama3.2`); the backend falls back to it when no `GEMINI_API_KEY` is set.

Frontend:

```bash
cd frontend
npm install
echo 'VITE_API_URL=http://localhost:8000' > .env
npm run dev
```

## Quality

```bash
ruff check .       # lint
mypy resume_tailor # strict type-check
pytest             # tests, including a guard that recommendation prompts stay PII-free
```

CI runs all three on every push and pull request.

## Limitations (honest notes)

- **Input is paste-as-text**, using the light format above. Importing and parsing raw
  PDF or Word resumes was deliberately deferred — real-world resume layouts are a
  rabbit hole, and the value of the tool is in the analysis, not the parsing. Pasting
  text works for everyone; a file importer is a possible future addition.
- **Recommendations come from the model's training knowledge**, not live web
  research. Treat specific certification names or details as directional, not a
  current catalogue.
- **Offline scoring matches words, not meaning.** With the default TF-IDF backend,
  coverage scores are low and mostly useful for *ranking* which bullet best matches a
  requirement. Meaningful absolute scores require the semantic embedding backend
  (or a hosted embeddings key).
- **Cold start.** The backend scales to zero to stay nearly free when idle, so the
  first request after a period of inactivity takes roughly 10–20 seconds to wake.

## Roadmap

- Semantic embeddings enabled by default in production for meaningful absolute scores
- Optional resume file import (PDF / Word) with graceful parsing
- Web-researched recommendations (current, verifiable certs and courses)
