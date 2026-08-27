# FitForge Agent — Google Cloud Run Deployment & Operational Guide

FitForge Agent is an evidence-based job-opportunity assessment workflow engine. This document provides the architecture, security controls, and deployment specifications for Google Cloud Run.

---

## 🏛️ Deployment Architecture

```text
[ HTTP Client / Browser ]
         │
         ▼
 ┌─────────────────────────────────────────────────────────┐
 │ Google Cloud Run (Service: fitforge-agent)              │
 │ Region: us-central1                                     │
 │ Service Account: fitforge-runner@PROJECT_ID.iam...      │
 │ Scaling: min-instances=0, max-instances=1               │
 │ Concurrency: 1 request per container, timeout=300s      │
 │ CPU Allocation: Request-based (--cpu-throttling)        │
 └─────────────────────────────────────────────────────────┘
         │                                   │
         ▼                                   ▼
┌─────────────────────────┐       ┌─────────────────────────┐
│ Google Cloud Firestore  │       │ Google Gemini 3.5 Flash │
│ Native Mode: (default)  │       │ Secret Manager Key      │
│ Collection: workflows   │       │ (fitforge-gemini-api-key│
└─────────────────────────┘       └─────────────────────────┘
```

---

## 🛡️ Cost, Abuse & Quota Safeguards

1. **Cloud Run Resource Limits**:
   * `--min-instances=0`: Scale to zero during idle periods (zero compute cost).
   * `--max-instances=1`: Strictly restricts service to at most one active container.
   * `--concurrency=1`: Single concurrent request per container.
   * `--timeout=300`: Caps maximum execution duration per assessment to 5 minutes.
   * `--cpu-throttling`: Allocates CPU only during active request processing.

2. **Application Demo Rate Limiting**:
   * Single-instance concurrency lock rejecting simultaneous submissions.
   * 60-second client cooldown enforced using privacy-safe SHA-256 IP hashes.
   * Automatic in-memory record pruning to prevent unbounded growth.

3. **Billing Alerts vs Hard Caps**:
   * Standard Google Cloud billing budgets generate **alerts only** via email/PubSub.
   * Architectural scaling limits and in-memory rate limiters enforce operational boundaries.

---

## 🔒 Service Identity & Least-Privilege IAM Roles

1. **Dedicated Service Identity**:
   ```bash
   gcloud iam service-accounts create fitforge-runner \
       --display-name="FitForge Cloud Run Runner"
   ```

2. **Least-Privilege Role Bindings**:
   * **`roles/datastore.user`**: Granted on the project for Firestore database access.
   * **`roles/secretmanager.secretAccessor`**: Resource-scoped strictly to the `fitforge-gemini-api-key` secret container.
   * **Zero Broad Roles**: No Owner, Editor, or broad Secret Manager administration roles are granted.

---

## 🔑 Secret Manager Integration

```powershell
# Create secret container
gcloud secrets create fitforge-gemini-api-key --replication-policy="automatic"

# Add secret version securely
$secretKey = Read-Host -MaskInput "Enter Gemini API Key"
$secretKey | gcloud secrets versions add fitforge-gemini-api-key --data-file=-
```

---

## 🚀 Cloud Run Source Deployment

Deploy directly from source using the repository Dockerfile:

```powershell
gcloud run deploy fitforge-agent `
  --source . `
  --project="fitforge-agent-2026" `
  --region="us-central1" `
  --service-account="fitforge-runner@fitforge-agent-2026.iam.gserviceaccount.com" `
  --set-env-vars="EXECUTION_MODE=gemini,GEMINI_MODEL=gemini-3.5-flash,PERSISTENCE_BACKEND=firestore,GOOGLE_CLOUD_PROJECT=fitforge-agent-2026,FIRESTORE_DATABASE=(default),FIRESTORE_COLLECTION=workflows" `
  --set-secrets="GEMINI_API_KEY=fitforge-gemini-api-key:1" `
  --allow-unauthenticated `
  --port=8080 `
  --min-instances=0 `
  --max-instances=1 `
  --concurrency=1 `
  --timeout=300 `
  --cpu-throttling
```

---

## 📡 Hardened Health Verification

The public `/health` endpoint reveals only service status and version without leaking internal environment variables, database names, or API key presence:

```http
GET /health HTTP/1.1
Host: fitforge-agent-169201386255.us-central1.run.app

HTTP/1.1 200 OK
Content-Type: application/json

{
  "status": "healthy",
  "version": "0.3.0"
}
```
