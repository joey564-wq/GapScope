import type {
  Resume,
  JobDescription,
  GapReport,
  TailorResponse,
  RecommendationReport,
} from "./types";

const BASE = import.meta.env.VITE_API_URL;

async function post<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    throw new Error(`${path} failed: ${r.status}`);
  }
  return r.json() as Promise<T>;
}

export function analyze(
  resume: Resume,
  jobDescription: JobDescription,
): Promise<GapReport> {
  return post<GapReport>("/analyze", {
    resume,
    job_description: jobDescription,
  });
}

export function tailor(
  resume: Resume,
  jobDescription: JobDescription,
): Promise<TailorResponse> {
  return post<TailorResponse>("/tailor", {
    resume,
    job_description: jobDescription,
  });
}

// /recommend suggests ways to CLOSE each gap (certs, courses, projects,
// experience). It sends only the gap report + JD — no resume, no PII — and the
// suggestions are advice to acquire experience, never woven into tailored bullets.
export function recommend(
  gap: GapReport,
  jobDescription: JobDescription,
): Promise<RecommendationReport> {
  return post<RecommendationReport>("/recommend", {
    gap,
    job_description: jobDescription,
  });
}

// /export streams a .docx; we download it as a blob without ever
// touching disk on the server (consistent with the no-storage policy).
export async function exportDocx(resume: Resume): Promise<void> {
  const r = await fetch(`${BASE}/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ resume }),
  });
  if (!r.ok) throw new Error(`export failed: ${r.status}`);

  const blob = await r.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${(resume.name || "resume").replace(/\s+/g, "_")}_tailored.docx`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
