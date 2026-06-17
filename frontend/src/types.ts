// Mirrors the Pydantic shapes in resume_tailor/models.py.
// Keep these in sync with the backend schema (the source of truth).

export type EntryKind = "experience" | "project" | "education";
export type RequirementKind = "required" | "preferred" | "responsibility";

export interface Bullet {
  id?: string;            // backend assigns one if omitted; we set it for provenance
  text: string;
  skills?: string[];
}

export interface Entry {
  id?: string;
  kind: EntryKind;        // REQUIRED by the backend
  title: string;
  organization?: string | null;
  location?: string | null;
  date_range?: string | null;
  bullets: Bullet[];
}

export interface SkillGroup {
  category: string;
  skills: string[];
}

export interface ContactInfo {
  location?: string | null;
  phone?: string | null;
  email?: string | null;
  links?: string[];
}

export interface Resume {
  name: string;
  contact: ContactInfo;   // an object, not a string
  summary?: string | null;
  entries: Entry[];
  skill_groups: SkillGroup[];
}

export interface JobRequirement {
  id?: string;
  text: string;
  kind?: RequirementKind;
}

export interface JobDescription {
  title: string;
  company?: string | null;
  requirements: JobRequirement[];   // objects, not strings
  raw_text?: string | null;
}

// ---- /analyze response (GapReport) — matches resume_tailor/gap_analysis.py ----

export type Status = "covered" | "partial" | "uncovered";

export interface RequirementCoverage {
  requirement_id: string;
  requirement_text: string;
  status: Status;
  best_score: number;
  best_bullet_id?: string | null;
  best_bullet_text?: string | null;
}

export interface GapReport {
  overall_score: number;
  coverages: RequirementCoverage[];
  missing_skills: string[];
}

// ---- /tailor response ----

export interface TailoredBullet {
  text: string;
  source_bullet_id: string;
  rationale?: string | null;
}

export interface TailoredResume {
  summary?: string | null;
  bullets: TailoredBullet[];
}

export interface TailorResponse {
  tailored: TailoredResume;
  grounding: unknown;   // shape lives in grounding.py; refine when needed
  gap: GapReport;
}

// ---- /recommend response (RecommendationReport) ----
// LLM-generated gap-closing suggestions. Kept entirely separate from tailoring:
// these are things to ACQUIRE, never woven into resume bullets.

export type SuggestionKind = "certification" | "course" | "project" | "experience";

export interface Suggestion {
  kind: SuggestionKind;
  title: string;
  detail?: string;
  effort?: string;
}

export interface RequirementSuggestions {
  requirement_id: string;
  requirement_text: string;
  suggestions: Suggestion[];
}

export interface RecommendationReport {
  items: RequirementSuggestions[];
}
