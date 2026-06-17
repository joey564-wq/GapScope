"""FastAPI service for resume-tailor.

Endpoints:
    GET  /health     liveness check
    POST /analyze    gap analysis of a resume against a job description
    POST /tailor     privacy-safe, anti-fabrication tailoring + grounding report
    POST /recommend  LLM suggestions for closing uncovered/partial gaps
    POST /export     render an (edited) resume to a downloadable .docx

Privacy posture enforced at this layer:
    - Resume content is processed in memory and never persisted.
    - This module configures no request-body logging; deployments must keep
      logging to metadata only (method, path, status, timing).
    - The embedding provider and LLM client are injected via FastAPI
      dependencies, so the tailoring step only ever receives PII-stripped prompts
      (see resume_tailor.tailoring), and tests can override them without network.
    - CORS is locked to ALLOWED_ORIGINS (comma-separated env var).
"""

from __future__ import annotations

import os

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from resume_tailor import (
    GapReport,
    GeminiClient,
    JobDescription,
    OllamaClient,
    RecommendationReport,
    Resume,
    analyze_gap,
    recommend_for_gaps,
    tailor_resume,
)
from resume_tailor.embeddings import (
    ApiEmbeddingProvider,
    EmbeddingProvider,
    TfidfEmbeddingProvider,
)
from resume_tailor.export import resume_to_docx_bytes
from resume_tailor.tailoring import LLMClient

DOCX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)

app = FastAPI(title="resume-tailor")

_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------- #
# Dependencies (override in tests via app.dependency_overrides)
# --------------------------------------------------------------------------- #


def get_provider() -> EmbeddingProvider:
    """Hosted embeddings in production; offline TF-IDF when no key is set."""
    if os.environ.get("OPENAI_API_KEY"):
        return ApiEmbeddingProvider()
    return TfidfEmbeddingProvider()


def get_llm() -> LLMClient:
    """Gemini in production; local Ollama for free offline dev.

    Mirrors get_provider's degrade-gracefully pattern: if GEMINI_API_KEY is set
    we use the hosted model, otherwise we fall back to a local Ollama model so
    development needs no key and no network. Constructed per request so tests
    can override it before any real client is created.
    """
    if os.environ.get("GEMINI_API_KEY"):
        return GeminiClient("gemini-2.5-flash")
    return OllamaClient(os.environ.get("OLLAMA_MODEL", "llama3.1"))


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #


class AnalyzeRequest(BaseModel):
    resume: Resume
    job_description: JobDescription


class ExportRequest(BaseModel):
    resume: Resume


class RecommendRequest(BaseModel):
    gap: GapReport
    job_description: JobDescription


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/analyze", response_model=GapReport)
def analyze(
    req: AnalyzeRequest,
    provider: EmbeddingProvider = Depends(get_provider),
) -> GapReport:
    return analyze_gap(req.resume, req.job_description, provider)


@app.post("/tailor")
def tailor(
    req: AnalyzeRequest,
    provider: EmbeddingProvider = Depends(get_provider),
    llm: LLMClient = Depends(get_llm),
) -> dict[str, object]:
    report = analyze_gap(req.resume, req.job_description, provider)
    try:
        tailored, grounding = tailor_resume(
            req.resume,
            req.job_description,
            provider,
            llm,
            gap_report=report,
        )
    except Exception as exc:  # never leak internals to the client
        raise HTTPException(status_code=502, detail="Tailoring failed") from exc
    return {
        "tailored": tailored.model_dump(),
        "grounding": grounding.model_dump(),
        "gap": report.model_dump(),
    }


@app.post("/recommend", response_model=RecommendationReport)
def recommend(
    req: RecommendRequest,
    llm: LLMClient = Depends(get_llm),
) -> RecommendationReport:
    """Suggest ways to close each uncovered/partial gap.

    Sends only requirement text + job title to the LLM — no resume, no PII.
    Suggestions are advice to acquire experience and are never merged into
    tailored bullets.
    """
    try:
        return recommend_for_gaps(req.gap, req.job_description, llm)
    except Exception as exc:  # never leak internals to the client
        raise HTTPException(status_code=502, detail="Recommendation failed") from exc


@app.post("/export")
def export(req: ExportRequest) -> StreamingResponse:
    data = resume_to_docx_bytes(req.resume)
    return StreamingResponse(
        iter([data]),
        media_type=DOCX_MEDIA_TYPE,
        headers={"Content-Disposition": 'attachment; filename="resume.docx"'},
    )
