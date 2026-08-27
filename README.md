# FitForge Agent — Milestone 1 (Deterministic Vertical Slice)

FitForge converts a candidate's résumé, job description, and applicant career priorities into an evidence-based job-opportunity assessment. It produces a clear recommendation (`Pursue`, `Investigate`, `Pass`), transparent fit score (0–100), requirement-to-evidence matrix, strengths, gaps, risks, clarification questions, prioritized next actions, and interview preparation talking points.

This repository implements **Milestone 1**: a locally runnable, deterministic vertical slice with a coordinator orchestrating 5 specialist agents, in-memory state persistence, and a responsive web interface.

---

## 🏛️ Multi-Agent Architecture

FitForge operates as a coordinated multi-agent pipeline rather than a general-purpose chatbot:

```
[Raw Inputs: Résumé + Job Description + Priorities]
                         │
                         ▼
             ┌───────────────────────┐
             │     Intake Agent      │  ──> Normalizes text, parses sections & flags missing criteria
             └───────────────────────┘
                         │
                         ▼
             ┌───────────────────────┐
             │    Evidence Agent     │  ──> Extracts requirements, maps evidence (direct, transferable, inference, missing)
             └───────────────────────┘
                         │
                         ▼
             ┌───────────────────────┐
             │      Fit Analyst      │  ──> Computes 0-100 fit score, checks non-negotiables & recommends Pursue/Investigate/Pass
             └───────────────────────┘
                         │
                         ▼
             ┌───────────────────────┐
             │    Action Planner     │  ──> Generates application brief, next actions, questions & STAR interview prep
             └───────────────────────┘
                         │
                         ▼
             ┌───────────────────────┐
             │     Quality Gate      │  ──> Audits unsupported claims, contradictions & enforces max 1 correction pass
             └───────────────────────┘
                         │
                         ▼
             [Completed Assessment & Timestamped Audit Trail]
```

### Specialist Stages

1. **Intake Agent (`normalizing`)**
   - Cleans formatting artifacts, standardizes bullets, and strips invalid characters.
   - Preserves raw input models while creating structured sections.
   - Detects missing salary, location, or experience fields.

2. **Evidence Agent (`mapping_evidence`)**
   - Parses job requirements across key operational and leadership domains.
   - Maps résumé facts to each requirement and classifies evidence into:
     - `direct`: Explicit, quantified proof in candidate history.
     - `transferable`: Adjacent skill or parallel leadership responsibility.
     - `inference`: Logically derived capability requiring verification.
     - `missing`: No demonstrable background found.
   - Never invents credentials or experiences.

3. **Fit Analyst (`scoring_fit`)**
   - Calculates a transparent weighted fit score (0–100).
   - Evaluates applicant non-negotiables against job conditions.
   - Assigns unambiguous recommendation: `Pursue` ($\ge 75$), `Investigate` ($50-74$), or `Pass` ($< 50$ or critical constraint breach).
   - Formulates uncertainty ratio and explains score drivers.

4. **Action Planner (`planning_actions`)**
   - Synthesizes an executive application brief.
   - Outlines prioritized next actions tailored to match level.
   - Drafts targeted clarification questions to ask employers.
   - Formats STAR interview preparation points tied to candidate evidence.

5. **Quality Gate (`validating`)**
   - Validates that evidence citations are grounded in the résumé text.
   - Eliminates logical contradictions (e.g. low score with Pursue recommendation).
   - Permits a maximum of **one correction pass** to resolve identified flaws.
   - Enforces strict loop circuit-breaking to prevent infinite retries.

---

## 🔄 Workflow State Lifecycle

State transitions occur deterministically in strict order:
`created` $\rightarrow$ `normalizing` $\rightarrow$ `mapping_evidence` $\rightarrow$ `scoring_fit` $\rightarrow$ `planning_actions` $\rightarrow$ `validating` $\rightarrow$ `completed` (or `failed`)

Every transition logs an immutable, timestamped `AuditEvent` recording `from_state`, `to_state`, `agent_name`, and execution details.

---

## 🚀 Quickstart & Local Setup

### Prerequisites
- Python 3.11+
- Git

### 1. Clone & Navigate
```bash
git clone <repo-url>
cd fitforge-agent
```

### 2. Set Up Virtual Environment & Dependencies
```bash
python -m venv .venv

# On Windows:
.venv\Scripts\activate

# On macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Run the Test Suite
```bash
pytest -v
```

### 4. Start the Application Server
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
Open your browser at **[http://127.0.0.1:8000](http://127.0.0.1:8000)**.

---

## 📡 API Reference

### `GET /health`
Returns service status and operational metadata.
```json
{
  "status": "healthy",
  "milestone": "1",
  "version": "0.1.0",
  "mode": "deterministic_local_slice"
}
```

### `GET /api/sample`
Returns fictionalized multi-unit restaurant district manager sample data.

### `POST /api/workflows`
Executes the full multi-agent workflow assessment.
- **Request Body:**
```json
{
  "resume_text": "...",
  "job_description_text": "...",
  "priorities": {
    "min_compensation": "$95,000 base salary + bonus",
    "location_preference": "Metro Region / Travel up to 50 miles",
    "desired_role_type": "District Manager / Multi-Unit Operations",
    "non_negotiables": [
      "Must have dedicated territory under 12 units"
    ]
  }
}
```
- **Response:** JSON `WorkflowResult` model containing fit score, evidence matrix, action plan, and complete audit trail. (Returns HTML partial when `Accept: text/html` is passed).

### `GET /api/workflows/{workflow_id}`
Retrieves a previously executed workflow and audit trail by UUID.

---

## ⚙️ Execution Modes & Configuration

FitForge Agent supports two explicit execution modes:

| Mode | Environment Config | Description |
|---|---|---|
| **Deterministic** | `EXECUTION_MODE=deterministic` (Default) | Verified local rule-based slice. Zero external network calls or credentials required. Default mode for automated testing. |
| **Google ADK & Gemini** | `EXECUTION_MODE=gemini` | Live specialist orchestration powered by official Google Agent Development Kit (`google-adk`) and `gemini-3.5-flash` (`google-genai`). |

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `EXECUTION_MODE` | `deterministic` | Execution adapter selection (`deterministic` or `gemini`). |
| `GEMINI_MODEL` | `gemini-3.5-flash` | Gemini model identifier for ADK agent stages. |
| `GEMINI_API_KEY` | *(None)* | Google Gemini API key (required only when `EXECUTION_MODE=gemini`). |
| `ALLOWED_ORIGINS` | `http://localhost:8000,http://127.0.0.1:8000` | Comma-separated CORS allowlist. |

---

## 📂 Repository Structure

```
fitforge-agent/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI endpoints & health check
│   ├── models.py                # Pydantic schemas, enums & state machine
│   ├── settings.py              # Configuration & mode validation
│   ├── coordinator.py           # Multi-agent orchestrator & state machine
│   ├── execution/               # Execution Adapter Pattern
│   │   ├── __init__.py
│   │   ├── base.py              # WorkflowExecutionAdapter abstract interface
│   │   ├── deterministic.py     # Milestone 1 local rule-based adapter
│   │   └── gemini_adk.py        # Milestone 2 Google ADK / Gemini 3.5 adapter
│   ├── prompts/                 # Specialist System Instructions & Injection Defense
│   │   ├── __init__.py          # Common security constraints & injection defenses
│   │   ├── intake.py            # Intake Agent instructions
│   │   ├── evidence.py          # Evidence Agent instructions & atomic decomposition
│   │   ├── fit_analyst.py       # Fit Analyst scoring & qualification distinction
│   │   ├── action_planner.py    # Action Planner brief & STAR points synthesis
│   │   └── quality_gate.py      # Quality Gate audit & verbatim check rules
│   ├── agents/                  # Milestone 1 specialist agent implementations
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── intake.py
│   │   ├── evidence.py
│   │   ├── fit_analyst.py
│   │   ├── action_planner.py
│   │   └── quality_gate.py
│   ├── repositories/
│   │   ├── __init__.py
│   │   └── in_memory.py         # Thread-safe in-memory store
│   ├── static/
│   │   ├── app.js               # Client-side interaction & safe DOM rendering
│   │   └── style.css            # Dark-mode styling with execution mode badges
│   └── templates/
│       ├── base.html            # Main HTML layout wrapper
│       ├── index.html           # Dashboard & submission form
│       └── partials/
│           ├── audit_trail.html # Real-time state transition timeline
│           └── workflow_result.html # Score hero, matrix, mode badge & strategy cards
├── samples/
│   └── restaurant_district_manager.json # Fictionalized benchmark dataset
├── tests/
│   ├── __init__.py
│   ├── test_agents.py           # Deterministic agent logic & boundaries
│   ├── test_health.py           # Service health & route validation
│   ├── test_quality_gate.py     # Grounding, contradiction check & retry bounds
│   ├── test_workflow.py         # End-to-end workflow execution & determinism
│   └── test_milestone2_adk.py   # Mocked ADK integration, injection & schema tests
├── .env.example
├── .gitignore
├── Dockerfile
├── LICENSE
├── README.md
└── requirements.txt
```

---

## 🔒 Privacy, Security & Testing

- **Mock Testing Policy**: Automated tests run with mocked Google GenAI / ADK clients and make **zero network calls**, incurring zero API charges.
- **Prompt-Injection Defense**: Specialist prompts explicitly instruct agents to treat résumé and job-description texts as untrusted data and ignore embedded instructions or overrides.
- **Sanitized Logging**: Server logs record only workflow ID, stage name, model identifier, latency, and status — never raw résumés, job descriptions, or API keys.
- **No Silent Fallback**: If Gemini execution fails, the coordinator transitions to `failed` state and logs a sanitized error. It never silently masks errors by falling back to deterministic mode.
- **Verification Status**: Live Google Cloud / Gemini API calls remain unexecuted until explicit authorization and secure credential configuration are provided (Phase C).

---

## 🗺️ Milestone Roadmap

- [x] **Milestone 1**: Deterministic 5-stage local slice with UI & complete test suite.
- [x] **Milestone 2**: Google Agent Development Kit (ADK) & `gemini-3.5-flash` adapter architecture with strict schema enforcement, prompt-injection defense, and mock test coverage.
- [ ] **Milestone 3**: Firestore persistent storage integration & Cloud Run deployment.
