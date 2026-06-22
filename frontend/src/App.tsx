import { useState } from "react";
import {
  parsePastedResume,
  parsePastedJD,
  EXAMPLE_RESUME_TEXT,
  EXAMPLE_JD,
} from "./parse";
import { analyze, recommend } from "./api";
import type { GapReport, RecommendationReport, JobDescription } from "./types";
import "./App.css";

const EXAMPLE_JD_TEXT = [
  `Title: ${EXAMPLE_JD.title}`,
  "",
  EXAMPLE_JD.raw_text ?? "",
  "",
  ...EXAMPLE_JD.requirements.map((r) => `- ${r.text}`),
].join("\n");

type Step = "input" | "gap";

const STEPS = [
  { id: 1, key: "input", label: "Input" },
  { id: 2, key: "gap", label: "Gap analysis" },
  { id: 3, key: "tailor", label: "Tailor & review" },
  { id: 4, key: "export", label: "Export" },
] as const;

// The signature: a live provenance engine. A source bullet, a tailored line
// derived from it, and a verification beam traveling between them — the thing
// the product promises, demonstrated on sight. Pure markup + CSS, no deps.
function ProvenanceEngine() {
  return (
    <div className="engine">
      <div className="engine-label">
        <span>provenance engine</span>
        <span className="live">grounding</span>
      </div>

      <div className="beam" style={{ top: "3.4rem", height: "2.1rem" }} />
      <div className="beam-dot" />

      <div className="doc">
        <span className="doc-tag src">source · real</span>
        <span className="id">id=ex1</span>
        <div>Helped customers with computer problems at the store.</div>
      </div>

      <div className="doc">
        <span className="doc-tag out">tailored · grounded</span>
        <span className="id">source_bullet_id=ex1</span>
        <div>Diagnosed and resolved customer hardware and software issues.</div>
      </div>

      <div className="engine-foot">
        <span className="stamp">✓ grounded</span>
        <span>traces to a real bullet · invents nothing</span>
      </div>
    </div>
  );
}

function BrandSeal() {
  return (
    <svg className="brand-seal" viewBox="0 0 32 32" fill="none" aria-hidden="true">
      <circle cx="16" cy="16" r="14" stroke="var(--seal)" strokeWidth="1.5" strokeDasharray="3 2.5" opacity="0.6" />
      <circle cx="16" cy="16" r="9.5" fill="var(--seal-wash)" stroke="var(--seal)" strokeWidth="1.5" />
      <path d="M11.5 16.2l3 3 6-6.4" stroke="var(--seal)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function ScoreRing({ value }: { value: number }) {
  const pct = Math.max(0, Math.min(1, value));
  const r = 36;
  const c = 2 * Math.PI * r;
  return (
    <svg className="score-ring" viewBox="0 0 90 90" aria-hidden="true">
      <circle className="ring-track" cx="45" cy="45" r={r} />
      <circle
        className="ring-fill"
        cx="45"
        cy="45"
        r={r}
        style={{ strokeDasharray: c, strokeDashoffset: c * (1 - pct) }}
      />
      <text className="ring-label" x="45" y="50">
        {Math.round(pct * 100)}%
      </text>
    </svg>
  );
}

export default function App() {
  const [resumeText, setResumeText] = useState("");
  const [jdText, setJdText] = useState("");
  const [step, setStep] = useState<Step>("input");
  const [gap, setGap] = useState<GapReport | null>(null);
  const [jd, setJd] = useState<JobDescription | null>(null);
  const [recs, setRecs] = useState<RecommendationReport | null>(null);
  const [recLoading, setRecLoading] = useState(false);
  const [recError, setRecError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function loadExample() {
    setResumeText(EXAMPLE_RESUME_TEXT);
    setJdText(EXAMPLE_JD_TEXT);
    setError(null);
  }

  function clearAll() {
    setResumeText("");
    setJdText("");
    setGap(null);
    setJd(null);
    setRecs(null);
    setRecError(null);
    setError(null);
    setStep("input");
  }

  async function runAnalysis() {
    setError(null);
    setRecs(null);
    setRecError(null);

    const resume = parsePastedResume(resumeText);
    const parsedJd = parsePastedJD(jdText);

    const bulletCount = resume.entries.reduce(
      (n, e) => n + e.bullets.length,
      0,
    );
    if (bulletCount === 0) {
      setError("Paste your resume first — at least one bullet of experience.");
      return;
    }
    if (parsedJd.requirements.length === 0) {
      setError(
        "Add at least one requirement to the job description — put each on its own line starting with “- ”.",
      );
      return;
    }

    setLoading(true);
    try {
      const report = await analyze(resume, parsedJd);
      setGap(report);
      setJd(parsedJd);
      setStep("gap");
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Analysis failed. Is the backend running?",
      );
    } finally {
      setLoading(false);
    }
  }

  async function getRecommendations() {
    if (!gap || !jd) return;
    setRecError(null);
    setRecLoading(true);
    try {
      const report = await recommend(gap, jd);
      setRecs(report);
    } catch (e) {
      setRecError(
        e instanceof Error
          ? e.message
          : "Couldn't fetch recommendations. Is the backend running?",
      );
    } finally {
      setRecLoading(false);
    }
  }

  const recsByReq = new Map(
    (recs?.items ?? []).map((it) => [it.requirement_id, it]),
  );

  const coverages = gap?.coverages ?? [];
  const coveredCount = coverages.filter((c) => c.status === "covered").length;

  function railState(key: string): string {
    if (key === step) return "current";
    if (key === "input" && step === "gap") return "done";
    return "";
  }

  return (
    <div className="app">
      <div className="grid-bg" aria-hidden="true" />

      <header className="masthead">
        <div className="masthead-text">
          <div className="brand">
            <BrandSeal />
            <span className="brand-name">
              Gap<b>·</b>Scope
            </span>
          </div>
          <p className="eyebrow">Provenance-checked resume tailoring</p>
          <h1 className="display">
            Re-present what's real.{" "}
            <span className="strike-fab">Never fabricate</span>
            {" — "}
            <span className="proven">prove it.</span>
          </h1>
          <p className="tagline">
            Map your actual experience against a target job, see exactly where
            you stand, and get honest, grounded ways to close the gap.
          </p>
        </div>
        <ProvenanceEngine />
      </header>

      <ol className="rail">
        {STEPS.map((s) => {
          const state = railState(s.key);
          return (
            <li key={s.id} className={state}>
              <span className="num">{state === "done" ? "✓" : s.id}</span>
              <span className="step-label">{s.label}</span>
            </li>
          );
        })}
      </ol>

      {step === "input" && (
        <section className="panel reveal">
          <div className="panel-head">
            <h2>Paste your resume and the job</h2>
            <p className="hint">
              Copy your resume text (Cmd/Ctrl+A, Cmd/Ctrl+C from your PDF or
              Word doc) and paste it below. This reads text you paste — it does
              not upload or store your file.
            </p>
          </div>

          <div className="field-grid">
            <label className="field" style={{ animationDelay: "0.05s" }}>
              <span className="field-label">
                Your resume
                <span className="field-tag">structured locally</span>
              </span>
              <textarea
                className="resume"
                value={resumeText}
                onChange={(e) => setResumeText(e.target.value)}
                placeholder={
                  "Name: Jane Doe\n" +
                  "Contact: jane@email.com | github.com/jane\n\n" +
                  "# Job Title @ Organization | 2023 - Present\n" +
                  "- A bullet describing what you did\n" +
                  "- Another bullet, ideally with a real number\n\n" +
                  "Skills: Python, React, FastAPI"
                }
              />
            </label>

            <label className="field" style={{ animationDelay: "0.12s" }}>
              <span className="field-label">
                Target job description
                <span className="field-tag">requirements</span>
              </span>
              <textarea
                className="jd"
                value={jdText}
                onChange={(e) => setJdText(e.target.value)}
                placeholder={
                  "Title: Software Engineering Intern\n\n" +
                  "Short description of the role…\n\n" +
                  "- A requirement on its own line\n" +
                  "- Another requirement"
                }
              />
            </label>
          </div>

          {error && <div className="error">{error}</div>}

          <div className="row">
            <button className="primary" onClick={runAnalysis} disabled={loading}>
              {loading ? (
                <>
                  <span className="spinner" /> Analyzing…
                </>
              ) : (
                "Analyze gap →"
              )}
            </button>
            <button className="ghost" onClick={loadExample} disabled={loading}>
              Load example
            </button>
            <button
              className="ghost small"
              onClick={clearAll}
              disabled={loading}
            >
              Clear
            </button>
          </div>
        </section>
      )}

      {step === "gap" && gap && (
        <section className="panel reveal">
          <div className="panel-head">
            <h2>Gap analysis</h2>
            <p className="hint">
              How your pasted experience covers each requirement. Ranking is
              reliable on any backend; absolute scores are meaningful only with
              the semantic embedding provider.
            </p>
          </div>

          <div className="score-card">
            <ScoreRing value={gap.overall_score ?? 0} />
            <div className="score-meta">
              <div className="score-headline">
                {coveredCount} of {coverages.length} requirements covered
              </div>
              {(gap.overall_score ?? 0) < 0.15 && (
                <p className="score-note">
                  Low scores across the board usually mean the offline TF-IDF
                  backend is running — it matches shared words, not meaning. Set{" "}
                  <code>OPENAI_API_KEY</code> for semantic scoring.
                </p>
              )}
            </div>
          </div>

          <div className="req-list">
            {coverages.map((r, idx) => {
              const reqRecs = recsByReq.get(r.requirement_id);
              return (
                <div
                  key={r.requirement_id}
                  className={`req ${r.status} reveal`}
                  style={{ animationDelay: `${idx * 0.07}s` }}
                >
                  <div className="req-top">
                    <span className="req-text">{r.requirement_text}</span>
                    <span className={`badge ${r.status}`}>{r.status}</span>
                  </div>
                  {typeof r.best_score === "number" && (
                    <div className="score-bar" aria-hidden="true">
                      <span
                        className="score-bar-fill"
                        style={{
                          width: `${Math.min(100, Math.round((r.best_score ?? 0) * 100))}%`,
                        }}
                      />
                    </div>
                  )}
                  {r.best_bullet_text && (
                    <div className="match">
                      <span className="lead">best match in your resume</span>
                      {r.best_bullet_text}
                    </div>
                  )}
                  {reqRecs && reqRecs.suggestions.length > 0 && (
                    <div className="suggestions">
                      <div className="sugg-head">Ways to close this gap</div>
                      <div className="sugg-grid">
                        {reqRecs.suggestions.map((s, i) => (
                          <div
                            key={i}
                            className="sugg reveal"
                            style={{ animationDelay: `${i * 0.06}s` }}
                          >
                            <div className="sugg-row">
                              <span className={`sugg-kind ${s.kind}`}>
                                {s.kind}
                              </span>
                              {s.effort && (
                                <span className="sugg-effort">{s.effort}</span>
                              )}
                            </div>
                            <div className="sugg-title">{s.title}</div>
                            {s.detail && (
                              <div className="sugg-detail">{s.detail}</div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {(gap.missing_skills ?? []).length > 0 && (
            <div className="missing">
              <strong>Keywords not found in your resume</strong>
              <div className="chips">
                {(gap.missing_skills ?? []).map((s, i) => (
                  <span key={i} className="chip">
                    {s}
                  </span>
                ))}
              </div>
            </div>
          )}

          {recError && <div className="error">{recError}</div>}

          {!recs && (
            <p className="growth-note">
              <span className="growth-mark" aria-hidden="true" />
              <span>
                These are suggested ways to <em>build</em> experience you don't
                yet have — certifications, courses, projects, and roles to seek.
                Advice for growth, never added to your resume.
              </span>
            </p>
          )}

          <div className="row">
            <button className="ghost" onClick={() => setStep("input")}>
              ← Edit input
            </button>
            <button
              className="primary"
              onClick={getRecommendations}
              disabled={recLoading}
            >
              {recLoading ? (
                <>
                  <span className="spinner" /> Researching…
                </>
              ) : recs ? (
                "Refresh suggestions"
              ) : (
                "Suggest ways to close these gaps"
              )}
            </button>
          </div>
        </section>
      )}

      <footer className="privacy">
        <span className="redaction" aria-hidden="true" />
        <span>
          <strong>Your resume stays private.</strong> Processed in memory to
          generate suggestions — not stored or logged. Only bullet text, never
          your name, email, phone, or links, is sent to the AI model.
        </span>
      </footer>
    </div>
  );
}