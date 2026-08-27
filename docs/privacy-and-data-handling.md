# FitForge Agent — Privacy, Security & Data Handling Policy

FitForge Agent is architected with a **security-first, least-privilege, and privacy-preserving posture** across all layers of the stack.

---

## 🛡️ 1. IP Privacy & Rate Limiter Security

* **Immediate Cryptographic Masking**: Client IP addresses extracted from `X-Forwarded-For` or request sockets are immediately hashed with SHA-256 and truncated to 16 characters.
* **No Raw IP Logging or Persistence**: Full IP addresses are never written to standard output, Cloud Logging, Firestore, or memory data structures.
* **Bounded In-Memory Tracking**: The `DemoRateLimiter` automatically prunes expired client records older than twice the cooldown window on every acquisition attempt, guaranteeing that memory consumption remains strictly bounded.
* **Cold Start Neutrality**: As an in-memory process guard, the rate limiter holds zero persistent state across Cloud Run container recycling.

---

## 🔑 2. Secrets & Credential Management

* **Zero Hardcoded Secrets**: No API keys, service account credentials, or environment secrets are stored in Git, Dockerfiles, or committed configuration files.
* **Google Secret Manager Integration**: Cloud Run binds the Gemini API key directly from Google Secret Manager (`fitforge-gemini-api-key:1`) into container environment variables in process memory at startup.
* **Least-Privilege Service Account**: The runtime identity (`fitforge-runner@fitforge-agent-2026.iam.gserviceaccount.com`) is granted only:
  - `roles/datastore.user` (scoped to Firestore access)
  - `roles/secretmanager.secretAccessor` (resource-scoped strictly to the `fitforge-gemini-api-key` secret container)
* **Zero Privilege Escalation**: No Project Owner, Project Editor, or broad Admin roles are assigned.

---

## 🗄️ 3. Data Persistence & Firestore Storage

* **Workflow Storage**: Assessments submitted via the web interface are persisted in Google Cloud Firestore (Native mode, `(default)` database, `workflows` collection) under randomly generated UUIDs.
* **Document Hygiene**: Assessment records contain structured extraction outputs and timestamped lifecycle audit events. They do not retain sensitive authentication credentials.
* **Public Evaluation Guidance**: Evaluators are instructed to use synthetic candidate profiles (such as the provided Restaurant District Manager profile) when testing the public endpoint.
