# FitForge Agent — Reproducible Testing Instructions

This document provides exact, reproducible steps for evaluators and judges to verify FitForge Agent locally and inspect its architectural safeguards.

---

## 🔒 1. Offline Deterministic Test Suite & Safety Tripwire

FitForge Agent is engineered with a **zero-cost offline testing guarantee**:
* **Network Isolation Tripwire**: The test suite incorporates a pytest socket blocker (`tests/conftest.py`) that strictly prohibits non-loopback network calls during unit testing.
* **Deterministic Execution Slice**: Offline tests utilize structured deterministic agent implementations (`app/agents/deterministic_slice.py`) that simulate all 5 specialist agents without contacting the live Gemini API or Google Cloud services.
* **Cost Guarantee**: Running `pytest` **never consumes Google Cloud billing or Gemini API quota**.

---

## 💻 2. Local Environment Setup

### Prerequisites
* Python 3.10+ (Tested on Python 3.14)
* Git

### Step-by-Step Installation

#### Windows (PowerShell)
```powershell
# 1. Clone or navigate to the repository
cd D:\Projects\fitforge-agent

# 2. Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Install core dependencies
pip install -r requirements.txt
```

#### macOS / Linux (Bash)
```bash
# 1. Clone or navigate to the repository
cd fitforge-agent

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install core dependencies
pip install -r requirements.txt
```

---

## 🧪 3. Executing the Test Suite

Run the full automated test suite (80 offline tests covering agents, coordinator, schema validation, rate limiter, and security controls):

```bash
python -m pytest tests/ -v
```

### Expected Test Output
```text
============================== 80 passed in ~4.5s ==============================
```

---

## 🚀 4. Running the Local Application (Deterministic Mode)

You can launch the full interactive web application locally with zero cloud dependencies or API keys:

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

1. Open your browser to: `http://127.0.0.1:8000`
2. Click **Load Sample** to populate the synthetic restaurant district manager benchmark.
3. Click **Run Multi-Agent Assessment**.
4. Observe the real-time execution flow through all 5 lifecycle states:
   `created` ➡️ `normalizing` ➡️ `mapping_evidence` ➡️ `scoring_fit` ➡️ `planning_actions` ➡️ `validating` ➡️ `completed`

---

## 🔍 5. Verification of Hardened Health Endpoint

To verify that the health endpoint returns only status and version without disclosing internal configuration:

```bash
curl -s http://127.0.0.1:8000/health
```

### Expected Output:
```json
{
  "status": "healthy",
  "version": "0.3.0"
}
```

---

## 🌐 6. Public Hosted Cloud Run Verification

To inspect the live Google Cloud Run service deployed in `us-central1`:

* **Service URL**: [https://fitforge-agent-169201386255.us-central1.run.app](https://fitforge-agent-169201386255.us-central1.run.app)
* **Health Check**: [https://fitforge-agent-169201386255.us-central1.run.app/health](https://fitforge-agent-169201386255.us-central1.run.app/health)
* **Synthetic Sample Endpoint**: [https://fitforge-agent-169201386255.us-central1.run.app/api/sample](https://fitforge-agent-169201386255.us-central1.run.app/api/sample)
