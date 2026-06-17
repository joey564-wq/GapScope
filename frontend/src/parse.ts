import type {
  Resume,
  JobDescription,
  Entry,
  EntryKind,
  ContactInfo,
} from "./types";

// Option A input: a forgiving paste box. The user pastes plain text using a
// light convention. This is NOT a PDF/Word parser (that's deferred to v2) — it
// reads text the user pastes from their own resume and maps it to the Resume
// shape the backend expects. Anything ambiguous degrades into a single entry.
//
// Convention (all optional except at least one bullet):
//   Name: Jane Doe
//   Contact: jane@email.com | github.com/jane | San Francisco, CA
//   Skills: Python, React, FastAPI
//   # Job Title @ Organization | 2023 - Present
//   - bullet text
//   - another bullet
//
// Lines starting with "#" open a new entry. Lines starting with "-/•/*" are
// bullets on the current entry. Bullet ids are left to the backend.

// --- contact: split a free "a | b | c" string into structured fields ---
function parseContact(raw: string): ContactInfo {
  const contact: ContactInfo = { links: [] };
  const parts = raw.split(/[|,]/).map((p) => p.trim()).filter(Boolean);
  for (const p of parts) {
    if (/\S+@\S+\.\S+/.test(p)) contact.email = p;
    else if (/^\+?[\d().\s-]{7,}$/.test(p)) contact.phone = p;
    else if (/(https?:\/\/|github\.com|linkedin\.com|\.dev|\.io|\.com)/i.test(p))
      contact.links!.push(p);
    else if (!contact.location) contact.location = p;
    else contact.links!.push(p);
  }
  return contact;
}

// --- entry header: "# Title @ Org | dates" + infer kind from the words ---
function inferKind(title: string, organization: string): EntryKind {
  const hay = `${title} ${organization}`.toLowerCase();
  if (/(project|app|site|tool|built|portfolio)/.test(hay)) return "project";
  if (/(b\.?s\.?|b\.?a\.?|degree|university|college|school|coursework)/.test(hay))
    return "education";
  return "experience";
}

function parseEntryHeader(header: string): Entry {
  const pipe = header.split("|");
  const left = (pipe[0] ?? "").trim();
  const dates = (pipe[1] ?? "").trim();

  const at = left.split("@");
  const title = (at[0] ?? "").trim();
  const organization = (at[1] ?? "").trim();

  return {
    kind: inferKind(title, organization),
    title,
    organization: organization || null,
    date_range: dates || null,
    bullets: [],
  };
}

export function parsePastedResume(raw: string): Resume {
  const lines = raw.split(/\r?\n/);
  const resume: Resume = {
    name: "",
    contact: { links: [] },
    entries: [],
    skill_groups: [],
  };

  const pushBullet = (text: string) => {
    if (resume.entries.length === 0) {
      resume.entries.push({ kind: "experience", title: "Experience", bullets: [] });
    }
    resume.entries[resume.entries.length - 1].bullets.push({ text });
  };

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) continue;
    const lower = line.toLowerCase();

    if (lower.startsWith("name:")) {
      resume.name = line.slice(5).trim();
      continue;
    }
    if (lower.startsWith("contact:")) {
      resume.contact = parseContact(line.slice(8).trim());
      continue;
    }
    if (lower.startsWith("skills:")) {
      const skills = line
        .slice(7)
        .split(/[,;]/)
        .map((s) => s.trim())
        .filter(Boolean);
      if (skills.length) resume.skill_groups.push({ category: "Skills", skills });
      continue;
    }
    if (line.startsWith("#")) {
      resume.entries.push(parseEntryHeader(line.replace(/^#+/, "").trim()));
      continue;
    }
    if (/^[-•*]/.test(line)) {
      const text = line.replace(/^[-•*]\s*/, "").trim();
      if (text) pushBullet(text);
      continue;
    }
    // Plain line, no marker: keep it rather than drop it.
    pushBullet(line);
  }

  return resume;
}

export const EXAMPLE_RESUME_TEXT = `Name: Joey Rivera
Contact: joey@example.com | github.com/joey564-wq | San Rafael, CA

# Consultation Agent @ Geek Squad | 2023 - Present
- Diagnosed and resolved hardware and software issues for 20+ clients per day
- Walked non-technical customers through device setup and data privacy settings
- Logged service outcomes and flagged recurring failure patterns for the team

# Campus Exchange (student project) @ CSU Chico | 2024 - 2025
- Built a full-stack student marketplace with React, Vite, and AWS Amplify
- Designed the PostgreSQL schema on Supabase and wrote AWS Lambda functions
- Sole builder on a 3-role Agile team, shipping iteratively over the term

Skills: Python, FastAPI, React, TypeScript, AWS, PostgreSQL, Docker, Git`;

// --- job description: build requirement OBJECTS, not strings ---
export function parsePastedJD(raw: string): JobDescription {
  const lines = raw.split(/\r?\n/);
  const requirements: JobDescription["requirements"] = [];
  const body: string[] = [];
  let title = "";
  let company: string | undefined;

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) continue;
    const lower = line.toLowerCase();
    if (lower.startsWith("title:")) {
      title = line.slice(6).trim();
      continue;
    }
    if (lower.startsWith("company:")) {
      company = line.slice(8).trim();
      continue;
    }
    if (/^[-•*]/.test(line)) {
      requirements.push({ text: line.replace(/^[-•*]\s*/, "").trim() });
    } else {
      body.push(line);
    }
  }
  return {
    title,
    company: company ?? null,
    requirements,
    raw_text: body.join("\n") || null,
  };
}

export const EXAMPLE_JD: JobDescription = {
  title: "Software Engineering Intern",
  company: null,
  requirements: [
    { text: "Experience with Python and a web framework like FastAPI or Flask" },
    { text: "Frontend development with React and TypeScript" },
    { text: "Familiarity with cloud deployment (AWS or Azure)" },
    { text: "Writing automated tests" },
    { text: "Working with relational databases such as PostgreSQL" },
  ],
  raw_text: `We're hiring a software engineering intern to build and ship web services.
You'll work across a Python backend and a React frontend, write tests, and
deploy to the cloud. We value clear communication and a privacy-conscious
mindset when handling user data.`,
};
