import { useEffect, useRef, useState } from "react";
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
  { id: 2, key: "gap", label: "Analysis" },
] as const;

function BrandMark() {
  return (
    <svg className="brand-mark" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <rect x="1" y="1" width="22" height="22" rx="6" fill="var(--accent-soft)" stroke="var(--accent)" strokeWidth="1.25" />
      <path d="M7 13.5l3 3 7-8" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function LockIcon() {
  return (
    <svg className="lock" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <rect x="5" y="11" width="14" height="9" rx="2" stroke="currentColor" strokeWidth="1.5" />
      <path d="M8 11V8a4 4 0 018 0v3" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

export default function App() {
  const ambientRef = useRef<HTMLDivElement>(null);

  // Drive the ambient gutters: a continuous gentle rotation, nudged by scroll
  // position, plus a subtle lean toward the cursor. All fed to CSS vars so the
  // browser compositor does the smoothing.
  useEffect(() => {
    const el = ambientRef.current;
    if (!el) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    let raf = 0;
    let mouseX = 0;
    let mouseY = 0;
    const start = performance.now();

    const onMove = (e: MouseEvent) => {
      // -1..1 relative to viewport center
      mouseX = (e.clientX / window.innerWidth - 0.5) * 2;
      mouseY = (e.clientY / window.innerHeight - 0.5) * 2;
    };
    window.addEventListener("mousemove", onMove, { passive: true });

    const tick = (now: number) => {
      const t = (now - start) / 1000;
      const scroll = window.scrollY;
      // continuous spin (6°/s) + scroll contribution
      const rot = t * 6 + scroll * 0.06;
      // cursor lean, capped so it stays subtle
      const px = mouseX * 26;
      const py = mouseY * 26 + scroll * 0.04;
      el.style.setProperty("--rot", `${rot}deg`);
      el.style.setProperty("--px", `${px}px`);
      el.style.setProperty("--py", `${py}px`);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("mousemove", onMove);
    };
  }, []);

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
      setError("Add your resume first — at least one bullet of experience.");
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
          : "Couldn't load recommendations. Is the backend running?",
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
  const pct = Math.round((gap?.overall_score ?? 0) * 100);

  function railState(key: string): string {
    if (key === step) return "current";
    if (key === "input" && step === "gap") return "done";
    return "";
  }

  return (
    <div className="app">
      <div className="ambient" ref={ambientRef} aria-hidden="true">
        <div className="glow left" />
        <div className="glow right" />
        <div className="orbit left">
          <svg viewBox="0 0 200 200">
            <circle cx="100" cy="100" r="96" strokeWidth="1" strokeOpacity="0.22" />
            <circle cx="100" cy="100" r="74" strokeWidth="1" strokeOpacity="0.18" />
            <circle cx="100" cy="100" r="52" strokeWidth="1" strokeOpacity="0.15" />
            <circle cx="100" cy="100" r="30" strokeWidth="1" strokeOpacity="0.12" />
            <circle cx="100" cy="4" r="3" fill="var(--accent)" stroke="none" opacity="0.5" />
            <circle cx="174" cy="100" r="2.5" fill="var(--accent-2)" stroke="none" opacity="0.4" />
          </svg>
        </div>
        <div className="orbit right">
          <svg viewBox="0 0 200 200">
            <circle cx="100" cy="100" r="96" strokeWidth="1" strokeOpacity="0.22" />
            <circle cx="100" cy="100" r="68" strokeWidth="1" strokeOpacity="0.16" />
            <circle cx="100" cy="100" r="40" strokeWidth="1" strokeOpacity="0.13" />
            <circle cx="196" cy="100" r="3" fill="var(--accent)" stroke="none" opacity="0.5" />
            <circle cx="100" cy="32" r="2.5" fill="var(--accent-2)" stroke="none" opacity="0.4" />
          </svg>
        </div>
        <div className="spin left">
          <svg viewBox="0 0 200 200">
            <circle cx="100" cy="100" r="90" strokeWidth="0.8"
              strokeDasharray="3 9" strokeOpacity="0.3" />
          </svg>
        </div>
        <div className="spin right">
          <svg viewBox="0 0 200 200">
            <circle cx="100" cy="100" r="90" strokeWidth="0.8"
              strokeDasharray="2 12" strokeOpacity="0.28" />
          </svg>
        </div>
      </div>

      <header className="masthead">
        <div className="brand">
          <BrandMark />
          <span className="brand-name">GapScope</span>
        </div>
        <h1 className="display">See where your resume meets the job.</h1>
        <p className="tagline">
          Compare your experience against a role, see how well you cover each
          requirement, and get honest, specific ways to close the gaps.
        </p>

        <ol className="steps">
          {STEPS.map((s) => {
            const state = railState(s.key);
            return (
              <li key={s.id} className={state}>
                <span className="num">{state === "done" ? "✓" : s.id}</span>
                {s.label}
              </li>
            );
          })}
        </ol>
      </header>

      {step === "input" && (
        <section className="panel">
          <div className="panel-head">
            <p className="hint">
              Paste your resume text and a job description below. Nothing is
              uploaded or stored. New here? Use “Load example” to see the format.
            </p>
          </div>

          <div className="field-grid">
            <label className="field">
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

            <label className="field">
              <span className="field-label">
                Job description
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
                "Analyze fit"
              )}
            </button>
            <button className="ghost" onClick={loadExample} disabled={loading}>
              Load example
            </button>
            <button className="ghost small" onClick={clearAll} disabled={loading}>
              Clear
            </button>
          </div>
        </section>
      )}

      {step === "gap" && gap && (
        <section className="panel">
          <div className="panel-head">
            <h2>Your fit for this role</h2>
            <p className="hint">
              Each requirement is matched to your closest experience. Ranking is
              reliable on any backend; absolute scores are most meaningful with
              semantic scoring enabled.
            </p>
          </div>

          <div className="score-card">
            <div className="score-figure">
              {pct}
              <span>%</span>
            </div>
            <div className="score-meta">
              <div className="score-headline">
                {coveredCount} of {coverages.length} requirements covered
              </div>
              {pct < 15 ? (
                <p className="score-note">
                  Low scores usually mean offline word-matching is in use. Enable
                  semantic scoring with <code>OPENAI_API_KEY</code> for meaningful
                  absolute scores.
                </p>
              ) : (
                <p className="score-note">Overall requirement coverage.</p>
              )}
              <div className="score-track">
                <span className="score-track-fill" style={{ width: `${pct}%` }} />
              </div>
            </div>
          </div>

          <div className="req-list">
            {coverages.map((r, idx) => {
              const reqRecs = recsByReq.get(r.requirement_id);
              const barPct = Math.min(100, Math.round((r.best_score ?? 0) * 100));
              return (
                <div
                  key={r.requirement_id}
                  className={`req reveal ${r.status}`}
                  style={{ animationDelay: `${0.15 + idx * 0.06}s` }}
                >
                  <div className="req-top">
                    <span className="req-text">{r.requirement_text}</span>
                    <span className={`badge ${r.status}`}>{r.status}</span>
                  </div>
                  {typeof r.best_score === "number" && (
                    <div className="score-bar" aria-hidden="true">
                      <span
                        className="score-bar-fill"
                        style={{ width: `${barPct}%` }}
                      />
                    </div>
                  )}
                  {r.best_bullet_text && (
                    <div className="match">
                      <span className="lead">Closest experience</span>
                      {r.best_bullet_text}
                    </div>
                  )}
                  {reqRecs && reqRecs.suggestions.length > 0 && (
                    <div className="suggestions">
                      <div className="sugg-head">Ways to close this gap</div>
                      <div className="sugg-grid">
                        {reqRecs.suggestions.map((s, i) => (
                          <div key={i} className="sugg">
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
                Get suggested ways to build the experience you don't yet have —
                certifications, courses, projects, and roles to pursue. These are
                for growth, never added to your resume.
              </span>
            </p>
          )}

          <div className="row">
            <button className="ghost" onClick={() => setStep("input")}>
              Edit input
            </button>
            <button
              className="primary"
              onClick={getRecommendations}
              disabled={recLoading}
            >
              {recLoading ? (
                <>
                  <span className="spinner" /> Finding suggestions…
                </>
              ) : recs ? (
                "Refresh suggestions"
              ) : (
                "Suggest ways to close gaps"
              )}
            </button>
          </div>
        </section>
      )}

      <footer className="privacy">
        <LockIcon />
        <span>
          <strong>Your resume stays private.</strong> It's processed in memory to
          generate results — never stored or logged. Only requirement text is
          sent to the AI for suggestions, never your name, contact details, or
          resume content.
        </span>
      </footer>
    </div>
  );
}
