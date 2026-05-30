# resume-tailor — Complete Build & Ship Guide (macOS, privacy-first)

From the keystone you have now → a deployed, public web app people can trust with
their resumes.

**This guide is written for a Mac** (Apple Silicon or Intel) using the default
**zsh** shell in the Terminal app. Every command is copy-paste ready for macOS.

It's also designed around one principle: **handle other people's resumes
responsibly.** That shapes the model choice (Gemini 2.5 Flash on the paid tier,
which does not train on your inputs), the architecture (strip personal data before
the LLM ever sees it), and operations (process in memory, store nothing, say so
plainly).

You already have the `resume_tailor/` package: models, embeddings, gap analysis,
grounding, and the **tailoring module with PII-stripping built in**. This guide
installs every tool and package you need, then turns that package into a live site.

---

## The privacy model (read first — it drives later decisions)

Three layers, defense in depth:

1. **Data minimization — strip PII before the LLM call.** The tailoring step only
   needs *bullet text*. The `tailoring.py` module enforces this: `build_user_prompt`
   only ever receives bullet ids + text and the job description, and
   `assert_no_pii_in_prompt` is a fail-closed guard before every network call. The
   full resume — name and contact included — is reassembled **locally** via
   `rebuild_resume`, from data that never left your server.
2. **A model that doesn't train on your data.** Gemini 2.5 Flash on the **paid**
   API tier does not use your inputs for training (unlike the free tier), for a few
   dollars a *year* at your traffic. Verify current terms on Google's site at launch.
3. **No storage + transparency.** Process in memory, never persist or log resume
   content, HTTPS only, and a short honest privacy notice.

Honest limitation: stripping *structured* identity fields can't guarantee a
free-text bullet contains zero personal data the candidate typed. That's why
layers 2 and 3 still matter.

---

## How to use this guide

Work top to bottom in the macOS Terminal. Each phase ends with a **commit
checkpoint** — push to GitHub at every one so you always have a working fallback.

**Discipline that matters most:** ship a *finished, small* thing. The "Deferred"
list stays deferred until v1 is live.

### Phase map
0. **Set up your Mac** — install every tool (detailed)
1. **Project + Python packages** — venv and every dependency (detailed)
2. Finish backend logic (embeddings provider, docx export)
3. FastAPI service (no logging of resume content)
4. React frontend (Vite) with the accept/reject editor + privacy notice
5. GitHub + CI
6. Containerize the backend
7. Deploy (Azure primary, AWS alternative)
8. Harden for real users
9. Polish, README, demo, resume bullets

### Realistic timeline
~5–7 weekends alongside school.

---

## Accounts & cost reality

- **GitHub** account (free).
- **Google Gemini API key**, paid tier enabled (Google AI Studio). Tailoring one
  resume is ~$0.003 — a few dollars covers thousands of uses. Set a spend cap.
- **OpenAI key** (or Google embeddings) for the production embedding provider, so
  you don't ship PyTorch. Local TF-IDF is the offline fallback for tests.
- **Cloud**: Azure (recommended — backend scales to zero) or AWS.

**Before deploying:** set a spend limit on your Gemini key and a cloud billing
alert. The biggest real-money risk is an unbounded `/tailor` endpoint.

---

## Phase 0 — Set up your Mac

This installs everything: the build tools, Python, Node, Docker, the cloud CLI,
a free local LLM, your editor, and the command-line helpers. Do it once.

### 0.1 — Xcode Command Line Tools (compilers + git)

These provide `git` and the C toolchain some Python packages compile against.
Run, then click "Install" in the popup and wait (a few minutes):
```zsh
xcode-select --install
```
Already installed? You'll see "command line tools are already installed" — fine.

### 0.2 — Homebrew (the macOS package manager)

Homebrew (`brew`) is how you install almost everything else. Install it:
```zsh
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```
**Apple Silicon (M1/M2/M3/M4) — important:** Homebrew installs to `/opt/homebrew`,
which isn't on your PATH yet. Add it (the installer prints these exact lines too):
```zsh
echo >> ~/.zprofile
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"
```
(On Intel Macs Homebrew uses `/usr/local` and is already on PATH — skip the above.)

Verify:
```zsh
brew --version        # prints a version number
```

### 0.3 — Install the tools

Run these one block at a time so you can spot any errors.

**Python 3.12** (don't use the system Python; install your own):
```zsh
brew install python@3.12
```

**Node.js + npm** (for the React frontend):
```zsh
brew install node
```

**GitHub CLI** (`gh` — create/push repos from the terminal):
```zsh
brew install gh
```

**Docker Desktop** (builds and runs your backend container). This is a GUI app, so
it's a "cask":
```zsh
brew install --cask docker
```
Then **open Docker Desktop once** (from Applications or `open -a Docker`) and leave
it running — the `docker` command only works while the app's engine is running.

**Azure CLI** (for deployment):
```zsh
brew install azure-cli
```

**AWS CLI** (only if you choose the AWS path later — optional):
```zsh
brew install awscli
```

**Ollama** (free local LLM for development — no API key, no cost):
```zsh
brew install ollama
```

**VS Code** (your editor):
```zsh
brew install --cask visual-studio-code
```

### 0.4 — Verify everything installed

Run each; you should get a version, not "command not found":
```zsh
python3.12 --version     # Python 3.12.x
node --version           # v20+ (or newer)
npm --version            # 10+
git --version            # 2.x
gh --version             # 2.x
docker --version         # Docker 2x.x  (Docker Desktop must be running)
az version               # azure-cli ...
ollama --version         # ollama version ...
code --version           # 1.x
```
If `code` says "command not found": open VS Code, press `Cmd+Shift+P`, run
**"Shell Command: Install 'code' command in PATH"**, then reopen Terminal.

### 0.5 — VS Code extensions

Install from the terminal (or search each in VS Code's Extensions panel):
```zsh
code --install-extension ms-python.python
code --install-extension ms-python.vscode-pylance
code --install-extension charliermarsh.ruff
code --install-extension ms-azuretools.vscode-docker
code --install-extension dsznajder.es7-react-js-snippets
code --install-extension ms-azuretools.vscode-azurecontainerapps
code --install-extension ms-azuretools.vscode-azurestaticwebapps
# AWS path only:
# code --install-extension amazonwebservices.aws-toolkit-vscode
```
What they do: Python + Pylance (language support, type hints), Ruff (linting on
save), Docker (Dockerfile help + container view), React snippets (frontend), and
the Azure Container Apps / Static Web Apps extensions (deploy from the editor).

### 0.6 — Sign in to your accounts

```zsh
gh auth login        # choose GitHub.com → HTTPS → login with browser
az login             # opens a browser to sign in to Azure
ollama pull llama3.1 # downloads the local model (~4.9 GB); run once
```
**Ollama RAM note:** `llama3.1` (8B) wants ~8 GB of free memory and runs well on a
16 GB+ MacBook (Apple Silicon's unified memory is great for this). On a smaller
Mac, use a lighter model instead: `ollama pull llama3.2` (3B) and reference
`"llama3.2"` in the code. Test it:
```zsh
ollama run llama3.1 "Say hello in one short sentence."   # Ctrl+D to exit
```

**Phase 0 done** — your Mac now has every tool the project needs.

---

## Phase 1 — Project setup & Python packages

### 1.1 — Get the project and open it

If your code is already on GitHub, clone it; otherwise open the folder you have:
```zsh
cd ~/Developer 2>/dev/null || mkdir -p ~/Developer && cd ~/Developer
# git clone https://github.com/<you>/resume-tailor.git   # if already pushed
cd resume-tailor
code .                 # opens this folder in VS Code
```

### 1.2 — Create and activate a virtual environment

A venv keeps this project's packages isolated from the system. Create it with the
Python you installed, then activate it (you'll do the activate step every new
Terminal session):
```zsh
python3.12 -m venv .venv
source .venv/bin/activate
```
Your prompt now shows `(.venv)`. Confirm pip points inside the venv:
```zsh
which python            # .../resume-tailor/.venv/bin/python
python --version        # Python 3.12.x
```
> Inside a venv you use plain `pip install` — no special flags needed.

In VS Code: `Cmd+Shift+P` → **"Python: Select Interpreter"** → pick the one under
`.venv`. This makes the editor, the test runner, and the terminal all use it.

### 1.3 — The packages, what each is for, and how to install them

Your `pyproject.toml` already declares everything in groups — you don't need to
edit it. For reference, here's what's declared and why each package is there:
```toml
dependencies = [
    "pydantic>=2",          # typed data models + validation (the resume schema)
    "numpy",                # vectors for similarity math
    "scikit-learn",         # TF-IDF + cosine similarity (offline gap analysis)
    "httpx",                # HTTP client (embeddings API + Ollama calls)
    "fastapi",              # the web API framework
    "uvicorn[standard]",    # the server that runs FastAPI
    "python-dotenv",        # loads your .env secrets in development
    "python-docx",          # generates the downloadable .docx resume
]

[project.optional-dependencies]
semantic = ["sentence-transformers"]   # optional local semantic embeddings (heavy)
gemini = ["google-genai"]              # the deployed LLM client (Gemini 2.5 Flash)
dev = ["pytest", "mypy", "ruff"]       # tests + type checker + linter
```

Now install the project **in editable mode** with the dev tools. Editable (`-e`)
means your source changes take effect without reinstalling:
```zsh
pip install -e ".[dev]"
```
That single command installs the package plus all core dependencies plus
pytest/mypy/ruff. Add the deployment LLM client too (used in production; for dev
you'll use local Ollama):
```zsh
pip install -e ".[gemini]"
```
Optional — only if you want local semantic embeddings instead of TF-IDF (large
download, pulls in PyTorch; you do NOT need this for the deployed app):
```zsh
pip install -e ".[semantic]"
```

**Quick reference — what you just installed and where it's used:**
- `pydantic` → `models.py` (Resume/JobDescription schemas, validation).
- `numpy` + `scikit-learn` → `embeddings.py` / `gap_analysis.py` (TF-IDF vectors,
  cosine similarity).
- `httpx` → `embeddings.py` (`ApiEmbeddingProvider`) and `tailoring.py`
  (`OllamaClient`).
- `google-genai` → `tailoring.py` (`GeminiClient`, the deployed model).
- `fastapi` + `uvicorn` → `api/main.py` (Phase 3) and the Docker image.
- `python-dotenv` → loading `.env` secrets locally.
- `python-docx` → `export.py` (Phase 2, the .docx download).
- `pytest` / `mypy` / `ruff` → your quality gate, run below and in CI.

### 1.4 — Confirm the baseline passes

```zsh
ruff check .            # "All checks passed!"
mypy resume_tailor      # "Success: no issues found"
pytest                  # all tests green (models, gap, grounding, tailoring)
```
The tailoring tests include the **PII-leak guard** — they prove no name, email,
phone, or link is ever sent to the model. Seeing them pass confirms your install
is correct end to end.

### 1.5 — VS Code settings (optional but nice)

Create `.vscode/settings.json`:
```json
{
  "python.testing.pytestEnabled": true,
  "editor.formatOnSave": true,
  "[python]": { "editor.defaultFormatter": "charliermarsh.ruff" },
  "ruff.lint.run": "onType"
}
```

**Phase 1 commit checkpoint:** `chore: declare web deps; verify install on macOS`

---

## Phase 2 — Backend logic (all implemented — verify & understand)

Good news: the remaining backend modules are **already written and tested** in the
package — `resume_tailor/embeddings.py` (now including `ApiEmbeddingProvider`),
`resume_tailor/tailoring.py`, and `resume_tailor/export.py`. This phase is about
understanding them and confirming they run on your Mac, not transcribing code.

First, confirm the whole suite is green (you ran this in Phase 1; run it again
after pulling these files):
```zsh
pytest -q          # all tests pass, incl. embeddings/export/tailoring/api
```

### 2A. `ApiEmbeddingProvider` — hosted embeddings, no PyTorch

In `resume_tailor/embeddings.py`. It calls an embeddings API (OpenAI
`text-embedding-3-small` by default) so the deployed container ships none of the
~2GB ML stack. The key is read from the environment; an `httpx.Client` can be
injected so tests use a mock transport instead of the network. Because
`EmbeddingProvider` is a swappable interface, nothing in `gap_analysis.py`,
`grounding.py`, or `tailoring.py` changes — you pick the provider at the edge.
Privacy note: it only ever embeds bullet text and JD requirements, never identity
fields.

Try it for real (optional — costs a fraction of a cent):
```zsh
export OPENAI_API_KEY=sk-...      # your key
python3 -c "
from resume_tailor.embeddings import ApiEmbeddingProvider
v = ApiEmbeddingProvider().embed(['shipped a REST API', 'built web services'])
print('shape:', v.shape)
"
```
The offline test (`tests/test_embeddings_api.py`) proves it works with **no
network** via `httpx.MockTransport`, so CI stays fast and free.

### 2B. Tailoring — already built (how it works)

`resume_tailor/tailoring.py` provides `GeminiClient` (paid tier, JSON-forced) and
`OllamaClient` (free local dev) behind one `LLMClient` interface; the PII-free
`build_user_prompt`; the `assert_no_pii_in_prompt` guard; the validate-and-reprompt
`tailor_resume(...)` loop; and `rebuild_resume(...)` for local reassembly. Develop
free against Ollama (you pulled the model in Phase 0), deploy against Gemini with a
one-line swap:
```python
from resume_tailor import OllamaClient, GeminiClient, tailor_resume
llm = OllamaClient("llama3.1")            # free local dev
# llm = GeminiClient("gemini-2.5-flash")  # deployed (set GEMINI_API_KEY)
tailored, grounding = tailor_resume(resume, jd, provider, llm, gap_report=report)
```

### 2C. `resume_to_docx_bytes` — Word export, in memory

In `resume_tailor/export.py`. It renders a `Resume` (name, contact, entries,
bullets, skills) to a `.docx` and returns **bytes**, so the API can stream it as a
download without ever writing resume content to disk — consistent with the
no-storage policy. The full resume is rendered locally; this data never went to the
LLM. `tests/test_export.py` confirms it produces a valid Word file containing the
expected content.

**Phase 2 commit checkpoint:** `feat: API embeddings + docx export (tested)`

---

## Phase 3 — The FastAPI service (already implemented — run & test it)

The service is **already written and tested** at `api/main.py`, with
`api/__init__.py` making it a package. It exposes four routes:

| Method | Path       | What it does                                          |
|--------|------------|-------------------------------------------------------|
| GET    | `/health`  | liveness check → `{"status":"ok"}`                    |
| POST   | `/analyze` | gap analysis of a resume vs. a job description        |
| POST   | `/tailor`  | PII-safe tailoring + grounding report + gap report    |
| POST   | `/export`  | renders an (edited) resume to a downloadable `.docx`  |

Design notes worth understanding:
- The embedding provider and LLM client are **FastAPI dependencies**
  (`get_provider`, `get_llm`). In production they resolve to `ApiEmbeddingProvider`
  + `GeminiClient`; in tests they're overridden with doubles, so the suite needs no
  network and no API key. This is also how `/tailor` stays PII-safe — it routes
  through `tailor_resume`, which only ever sends bullet text to the model.
- `/tailor` wraps the call in a `try/except` that returns a clean **502** and never
  leaks internal error text to the client.
- CORS is locked to `ALLOWED_ORIGINS` (comma-separated env var).

### 3.1 — Secrets via a gitignored `.env`

```zsh
cat > .env << 'EOF'
GEMINI_API_KEY=your-gemini-key
OPENAI_API_KEY=your-openai-key
ALLOWED_ORIGINS=http://localhost:5173
EOF
```
Load it into your shell when running locally so the app sees the keys:
```zsh
export $(grep -v '^#' .env | xargs)
```
**Privacy in the API layer:** don't log request bodies (record method/path/status/
timing only), don't persist resume data, keep secrets in `.env` (never commit it).

### 3.2 — Run it locally

With your venv active and Docker not required:
```zsh
uvicorn api.main:app --reload --port 8000
```
Open **`http://localhost:8000/docs`** — FastAPI's interactive UI. Try `/health` and
`/analyze` there with a sample resume + JD JSON (the shapes mirror the Pydantic
models; the test fixtures in `tests/conftest.py` are good examples to copy).

Quick checks from another terminal:
```zsh
curl http://localhost:8000/health
# -> {"status":"ok"}
```

### 3.3 — Test `/tailor` for free (local Ollama, no paid calls)

`/tailor` needs an LLM. For zero-cost local testing, point `get_llm` at Ollama by
setting an env switch or temporarily editing `get_llm` to return
`OllamaClient("llama3.1")`. With Ollama running (Phase 0), the endpoint works with
no API spend. Switch back to `GeminiClient` for deployment.

### 3.4 — The automated API tests

`tests/test_api.py` uses FastAPI's `TestClient` with dependency overrides: a
deterministic embedding double and a `FakeLLM` returning canned JSON. It verifies
`/health`, `/analyze` coverage, the `/tailor` happy path (grounded output), the
`/tailor` 502-on-failure path (and that the internal error doesn't leak), and that
`/export` returns a real `.docx`. Run the whole suite:
```zsh
pytest -q          # backend package + API, all green, no network
```

**Phase 3 commit checkpoint:** `feat: FastAPI service (tested), no content logging`

---

## Phase 4 — The React frontend (Vite)

Scaffold the app and install its packages (npm pulls React, ReactDOM, Vite, and
TypeScript from the template's `package.json`):
```zsh
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install            # installs all frontend dependencies
npm run dev            # http://localhost:5173 — leave running while you build
```
Point the frontend at your backend — create `frontend/.env`:
```zsh
echo 'VITE_API_URL=http://localhost:8000' > .env
```
Access it as `import.meta.env.VITE_API_URL` (use the deployed URL in production).

### Four screens
1. **Input** — a structured form (or paste-as-markdown) to build the `Resume`
   object, plus a textarea for the job description. Match the Pydantic shapes.
2. **Gap analysis** — `POST /analyze`; render each requirement with a
   covered/partial/uncovered badge, its best-matching bullet, and missing skills.
3. **Tailored editor** — `POST /tailor`, then for each tailored bullet show
   **original vs. tailored** with **Accept / Reject**, and flag any bullet the
   grounding report marked (red "unverified — review" with the reason). An
   **Export** button POSTs the edited resume to `/export` and downloads the docx.
4. **Privacy notice** — short, plain-language (see Phase 8).

Minimal fetch helper `frontend/src/api.ts`:
```ts
const BASE = import.meta.env.VITE_API_URL;
export async function analyze(resume: unknown, jobDescription: unknown) {
  const r = await fetch(`${BASE}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ resume, job_description: jobDescription }),
  });
  if (!r.ok) throw new Error(`analyze failed: ${r.status}`);
  return r.json();
}
```
The accept/reject diff plus visible grounding flags are what make this read as a
trustworthy product. The `frontend-design` skill helps if you want it distinctive.

**Phase 4 commit checkpoint:** `feat: React frontend with editor + privacy notice`

---

## Phase 5 — GitHub & CI

`.gitignore` at the repo root:
```
.venv/
__pycache__/
*.pyc
.pytest_cache/
.mypy_cache/
.env
frontend/node_modules/
frontend/dist/
```
Init and push (you signed into `gh` in Phase 0):
```zsh
git init
git add .
git commit -m "feat: resume-tailor v1 (core + tailoring + api + frontend)"
gh repo create resume-tailor --public --source=. --push
```
Work on feature branches → open a PR → CI passes → merge. In **Settings → Branches**,
require the CI check before merge.

CI at `.github/workflows/backend-ci.yml`:
```yaml
name: backend-ci
on: [push, pull_request]
jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e ".[dev]"
      - run: ruff check .
      - run: mypy resume_tailor
      - run: pytest
```
The PII-leak guard test running in CI means a future change can't silently start
sending personal data to the model without a test going red.

**Phase 5 commit checkpoint:** `ci: add backend quality gate`

---

## Phase 6 — Containerize the backend

`Dockerfile` (small image — API embeddings, no torch):
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
COPY resume_tailor ./resume_tailor
COPY api ./api
RUN pip install --no-cache-dir -e ".[gemini]"
EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```
`.dockerignore`:
```
.venv
frontend
__pycache__
.git
.env
*.md
```
Build and run locally (Docker Desktop must be running):
```zsh
docker build -t resume-tailor-api .
docker run -p 8000:8000 \
  -e GEMINI_API_KEY=$GEMINI_API_KEY \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  resume-tailor-api
curl http://localhost:8000/health        # -> {"status":"ok"}
```
> Tip: load your `.env` into the current shell first so `$GEMINI_API_KEY` is set:
> `export $(grep -v '^#' .env | xargs)`

**Phase 6 commit checkpoint:** `build: dockerize backend`

---

## Phase 7 — Deploy

### Option A — Azure (recommended: scales to zero, free frontend)

**Backend → Azure Container Apps.** One-time setup (you ran `az login` in Phase 0):
```zsh
az upgrade
az extension add --name containerapp --upgrade
az provider register --namespace Microsoft.App
az provider register --namespace Microsoft.OperationalInsights
az group create --name resume-tailor-rg --location eastus
```
Deploy from source (builds the image + registry + environment in one command):
```zsh
az containerapp up \
  --resource-group resume-tailor-rg \
  --name resume-tailor-api \
  --ingress external \
  --target-port 8000 \
  --source .
```
Save the printed HTTPS URL. Set secrets, lock CORS, enable scale-to-zero:
```zsh
az containerapp secret set -g resume-tailor-rg -n resume-tailor-api \
  --secrets gemini-key=$GEMINI_API_KEY openai-key=$OPENAI_API_KEY

az containerapp update -g resume-tailor-rg -n resume-tailor-api \
  --min-replicas 0 --max-replicas 2 \
  --set-env-vars \
    GEMINI_API_KEY=secretref:gemini-key \
    OPENAI_API_KEY=secretref:openai-key \
    ALLOWED_ORIGINS=https://<your-frontend-domain>
```
`--min-replicas 0` makes it cost ~nothing idle (short cold start on first request).

**Frontend → Azure Static Web Apps** (free tier). In the Azure Portal: *Create a
resource* → *Static Web App* → connect your GitHub repo, then for Vite set:
- **App location:** `frontend`
- **Output location:** `dist`
- **Build:** `npm run build`

Azure auto-commits a GitHub Actions workflow and adds the deploy token. Two Vite
gotchas to avoid a blank page: confirm `output_location: "dist"` (no slashes), and
add `frontend/staticwebapp.config.json`:
```json
{ "navigationFallback": { "rewrite": "/index.html" } }
```
Set `VITE_API_URL` to your Container Apps URL as a build env var, and update the
backend `ALLOWED_ORIGINS` to your Static Web Apps domain.

### Option B — AWS (uses your Amplify experience)

- **Frontend → AWS Amplify Hosting**: connect the repo, base directory `frontend`,
  build `npm run build`, output `dist`.
- **Backend → AWS App Runner**: create a service from the repo (reads the
  Dockerfile); port 8000; add `GEMINI_API_KEY`, `OPENAI_API_KEY`, `ALLOWED_ORIGINS`.
- Honest trade-off: App Runner **doesn't scale to zero** (~$5+/mo idle). Prefer
  Azure if near-zero idle cost matters.

### After either option
- Run a real resume + JD end to end on the live frontend.
- Tail backend logs:
  - Azure: `az containerapp logs show -n resume-tailor-api -g resume-tailor-rg --follow`
- Confirm CORS works and the docx download succeeds.

**Phase 7 commit checkpoint:** `deploy: backend container + static frontend`

---

## Phase 8 — Harden for real users

- **Spend cap first** — hard usage limit on your Gemini key + cloud billing alert,
  before sharing the link. Non-negotiable.
- **Rate limit** `/tailor` and `/analyze` (`pip install slowapi`, or platform limits).
- **Cap input size** — reject oversized payloads and cap the number of bullets.
- **No content logging / no storage** — re-verify logging is metadata-only and
  nothing writes resume data to disk.
- **HTTPS only** (both platforms provide it) and **CORS locked** to your exact
  frontend origin (not `*`).
- **Graceful errors** — `/tailor` already returns a clean 502.
- **Privacy notice** on the site, e.g.:
  > *Your resume is processed in memory to generate suggestions and is not stored
  > or logged. Only bullet text — never your name, email, phone, or links — is sent
  > to a third-party AI model (Google Gemini) on a paid tier that does not train on
  > your data.*
  Keep that statement true as the code changes.

**Phase 8 commit checkpoint:** `feat: rate limiting, input caps, spend cap, privacy`

---

## Phase 9 — Polish, README, demo, resume bullets

- **README**: lead with the privacy-by-design model and the three-gate
  anti-fabrication check; add a live demo link, a GIF of the accept/reject editor
  catching a fabricated bullet, the architecture, run instructions, and the CI badge.
- **Demo data**: a "Load example" button that fills a sample resume + JD.
- **GIF**: ~15 seconds — paste JD → gap analysis → accept/reject (show a flagged
  fabrication) → export. Put it at the top of the README.
- **Pin the repo** on your GitHub profile.

### Resume bullets you'll have earned
- Designed and deployed a privacy-first, full-stack resume-tailoring web app
  (FastAPI + React, containerized, CI-gated) mapping experience to a target job via
  hosted semantic embeddings.
- Engineered a **PII-stripping tailoring pipeline**: only bullet text (never name or
  contact details) is sent to the LLM, enforced by construction and a fail-closed
  runtime guard with a CI test; the full resume is reassembled locally.
- Built a **three-gate anti-fabrication validator** (source-provenance,
  invented-metric, semantic-drift) with an automatic validate-and-re-prompt loop;
  ungrounded content is flagged, never silently used.
- Shipped a bullet-level **accept/reject editor** with one-click `.docx` export;
  chose a paid, no-training model tier and a scale-to-zero deployment with locked
  CORS, rate limiting, input caps, and spend controls.

---

## Daily workflow reminder (every new Terminal session)

```zsh
cd ~/Developer/resume-tailor
source .venv/bin/activate         # backend Python work
# backend:   uvicorn api.main:app --reload --port 8000
# frontend:  cd frontend && npm run dev
```

## Cost management & teardown

- Check the cloud cost dashboard weekly the first month. Frontend free; backend
  idles cheaply on Azure; Gemini is pennies.
- Teardown — Azure: `az group delete --name resume-tailor-rg` and delete the Static
  Web App; AWS: delete App Runner + Amplify. Rotate/disable keys when you stop hosting.

## Deferred (NOT in v1)

PDF/Word import parsing, accounts, saved profiles, multi-JD comparison, ATS
scoring, fine-tuned models. Each is a v2 story — after v1 is live and on your resume.

## Quick troubleshooting

- **`brew: command not found`** — you skipped the Apple-Silicon PATH step in 0.2;
  re-run the two `~/.zprofile` lines and open a new Terminal.
- **`docker: command not found` or "Cannot connect to the Docker daemon"** — open
  the Docker Desktop app and wait for it to finish starting.
- **`code: command not found`** — run the "Install 'code' command in PATH" step (0.4).
- **`pip` installs into system Python** — your venv isn't active; run
  `source .venv/bin/activate` (prompt should show `(.venv)`).
- **Blank page on Azure SWA** — wrong `output_location` (must be `dist`) or missing
  SPA fallback config.
- **CORS error** — `ALLOWED_ORIGINS` doesn't exactly match the frontend URL.
- **`/tailor` 502** — check logs; usually a missing/invalid `GEMINI_API_KEY`.
- **PII guard raises ValueError** — a change wired identity data into the prompt
  path; fix the prompt construction, don't disable the guard.
- **Docker image huge/slow** — you're installing torch; confirm the deployed path
  uses `ApiEmbeddingProvider` and `sentence-transformers` stays an optional extra.
