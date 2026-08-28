# FitForge Agent — Verified Live Evidence Report

This document records the empirical verification evidence collected from live Google Cloud Platform executions and automated test runs.

---

## 📊 1. Master Evidence Summary

| Component | Target Requirement | Verified Status | Verification Evidence |
|---|---|---|---|
| **Test Suite** | Comprehensive offline coverage | **PASSED (80/80)** | `pytest tests/ -q` (80 passed, 0 failed in 8.09s) |
| **Network Tripwire** | Zero external calls during unit tests | **VERIFIED** | Non-loopback sockets blocked in `conftest.py` |
| **Cloud Run Deployment** | Source-built container in `us-central1` | **DEPLOYED & SERVING** | Revision `fitforge-agent-00002-8jt`, 100% traffic allocated |
| **Service Identity** | Dedicated least-privilege SA | **VERIFIED** | `fitforge-runner@fitforge-agent-2026.iam.gserviceaccount.com` |
| **Secret Management** | Runtime secret injection | **VERIFIED** | Secret Manager `fitforge-gemini-api-key:1` bound to process |
| **Public Health Check** | Hardened minimal endpoint | **VERIFIED (200 OK)** | Returns `{"status": "healthy", "version": "0.3.0"}` |
| **Public Rate Limiter** | Cooldown & Concurrency Guard | **VERIFIED (HTTP 429)** | Returns `Retry-After: <seconds>` on repeat submission |
| **Live Multi-Agent Workflow** | Multi-agent ADK execution | **VERIFIED (COMPLETED)** | Score: `82/100`, Rec: `Investigate`, 9 requirements mapped |
| **Quality Gatekeeper** | Schema consistency & grounding | **VERIFIED (PASSED)** | Zero hallucinated claims, 0 schema repair retries required |
| **Cloud Firestore** | Document persistence & retrieval | **VERIFIED** | Persisted to `(default)` database and recovered via API |

---

## 🌐 2. Live Public Health Endpoint Output

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "status": "healthy",
  "version": "0.3.0"
}
```

---

## ⚡ 3. Live Public Gemini / ADK Assessment Execution

```json
{
  "workflow_id": "a635ea53-a72d-4bd6-924b-84b0146c0dc9",
  "state": "completed",
  "execution_mode": "gemini",
  "gemini_model": "gemini-3.6-flash",
  "fit_score": 82,
  "recommendation": "Investigate",
  "requirements_extracted": 9,
  "quality_gate": {
    "passed": true,
    "correction_count": 0
  },
  "lifecycle_audit_trail": [
    {"to_state": "created", "agent": "Coordinator"},
    {"to_state": "normalizing", "agent": "Intake Agent"},
    {"to_state": "mapping_evidence", "agent": "Evidence Agent"},
    {"to_state": "scoring_fit", "agent": "Fit Analyst"},
    {"to_state": "planning_actions", "agent": "Action Planner"},
    {"to_state": "validating", "agent": "Quality Gate"},
    {"to_state": "completed", "agent": "Coordinator"}
  ]
}
```

---

## 🛑 4. Public Rate Limiter 429 Rejection Evidence

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 48
Content-Type: application/json

{
  "detail": "Rate limit exceeded. Please wait 48 seconds before submitting another workflow."
}
```
