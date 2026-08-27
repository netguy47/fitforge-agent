# FitForge Agent — Google Cloud Run Deployment & Operational Security Guide

FitForge is an evidence-based job-opportunity assessment workflow engine. This document provides production guidelines, security controls, and deployment commands for deploying FitForge to Google Cloud Run.

---

## 🏛️ Architecture Overview

```
[ HTTP Client / Browser ]
         │
         ▼
 ┌─────────────────────────────────────────────────────────┐
 │ Google Cloud Run (Service: fitforge-agent)              │
 │ Region: us-central1                                     │
 │ Environment: PORT=8080, EXECUTION_MODE=gemini/deterministic │
 └─────────────────────────────────────────────────────────┘
         │                                   │
         ▼                                   ▼
┌─────────────────────────┐       ┌─────────────────────────┐
│ Google Cloud Firestore  │       │ Google Gemini 3.5 Flash │
│ Database: (default)     │       │ Secret Manager Key      │
│ Collection: workflows   │       │ (gemini-3.5-flash)      │
└─────────────────────────┘       └─────────────────────────┘
```

---

## ⚠️ CRITICAL DEPLOYMENT RISKS & SPENDING CONTROLS

> [!WARNING]
> **Public Exposure & Quota Consumption Risks**
> - `--allow-unauthenticated` exposes the workflow POST `/api/workflows` endpoint publicly on the internet.
> - Unauthenticated public requests can trigger live Gemini 3.5 Flash ADK multi-stage workflows, rapidly consuming Gemini API quotas and project billing.
> - `--max-instances=1` limits concurrency and container scaling, but does **NOT** create a hard spending cap on API quotas.
> - Google Cloud billing budgets generate **alerts only** — they do NOT automatically shut down services or cap spending.
> - Gemini API quotas and Cloud Run billing limits must be reviewed and configured before public deployment.
> - **Public deployment requires Donald's explicit prior approval.**

---

## 🔒 Service Identity & Least-Privilege IAM Roles

1. **Dedicated Service Identity**: Create a dedicated Google Cloud Service Account for FitForge:
   ```bash
   gcloud iam service-accounts create fitforge-runner \
       --display-name="FitForge Cloud Run Runner"
   ```

2. **Least-Privilege Role Assignment**:
   - Assign **`roles/datastore.user`** for Firestore document storage in the project:
     ```bash
     gcloud projects add-iam-policy-binding PROJECT_ID \
         --member="serviceAccount:fitforge-runner@PROJECT_ID.iam.gserviceaccount.com" \
         --role="roles/datastore.user"
     ```
   - Assign **`roles/secretmanager.secretAccessor`** strictly on the specific Gemini secret (NOT project-wide):
     ```bash
     gcloud secrets add-iam-policy-binding fitforge-gemini-api-key \
         --member="serviceAccount:fitforge-runner@PROJECT_ID.iam.gserviceaccount.com" \
         --role="roles/secretmanager.secretAccessor"
     ```
   - **DO NOT** grant `roles/owner`, `roles/editor`, or broad project-level Secret Manager administration to the runtime service account.

---

## 🔑 Secure Gemini API Key Entry

> [!IMPORTANT]
> Never place `GEMINI_API_KEY` directly in source code, Dockerfile, Git, plain deployment documentation, command history, or `--set-env-vars` commands.

### Option A: Masked PowerShell Input (Recommended for CLI)
```powershell
# Create secret metadata container
gcloud secrets create fitforge-gemini-api-key --replication-policy="automatic"

# Prompt for key securely without displaying characters or logging to shell history
$secretKey = Read-Host -MaskInput "Enter Gemini API Key"
$secretKey | gcloud secrets versions add fitforge-gemini-api-key --data-file=-
```

### Option B: Google Cloud Console UI
1. Navigate to **Security > Secret Manager** in the Google Cloud Console.
2. Click **Create Secret**. Name it `fitforge-gemini-api-key`.
3. Paste the API key into the secret value field and click **Create**.

---

## 🚀 Cloud Run Source Deployment Command

> [!NOTE]
> **Future, Approval-Gated Deployment Command**
> *Do not execute this command without explicit approval from Donald. Source deployment uses Google Cloud Build and Artifact Registry under the hood. Their APIs, along with Firestore, Cloud Run, and Secret Manager APIs, must be enabled only after authorization.*

```powershell
gcloud run deploy fitforge-agent `
  --source . `
  --region us-central1 `
  --service-account "fitforge-runner@PROJECT_ID.iam.gserviceaccount.com" `
  --set-env-vars 'EXECUTION_MODE=gemini,GEMINI_MODEL=gemini-3.5-flash,PERSISTENCE_BACKEND=firestore,GOOGLE_CLOUD_PROJECT=PROJECT_ID,FIRESTORE_DATABASE=(default),FIRESTORE_COLLECTION=workflows' `
  --set-secrets 'GEMINI_API_KEY=fitforge-gemini-api-key:latest' `
  --allow-unauthenticated `
  --port 8080 `
  --timeout 300 `
  --concurrency 1 `
  --max-instances 1
```

---

## 📡 Health Check Verification

### Current Local / Deterministic Response (`GET /health`)
```json
{
  "status": "healthy",
  "milestone": "3B",
  "version": "0.3.0",
  "mode": "deterministic_local_slice",
  "execution_mode": "deterministic",
  "gemini_model": "gemini-3.5-flash",
  "has_credentials": "False",
  "persistence_backend": "in_memory",
  "firestore_database": "(default)",
  "firestore_collection": "workflows"
}
```

### Live Gemini ADK Response (`GET /health`)
When `EXECUTION_MODE=gemini` and live credentials are present:
```json
{
  "status": "healthy",
  "milestone": "3B",
  "version": "0.3.0",
  "mode": "gemini_adk",
  "execution_mode": "gemini",
  "gemini_model": "gemini-3.5-flash",
  "has_credentials": "True",
  "persistence_backend": "firestore",
  "firestore_database": "(default)",
  "firestore_collection": "workflows"
}
```
