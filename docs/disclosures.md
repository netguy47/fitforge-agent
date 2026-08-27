# FitForge Agent — Project Disclosures & Ethical Boundaries

**Project Creation Date**: August 26, 2026  
**Competition Category**: Taskmaster (Google Agentic AI Hackathon)  
**Submitter**: Individual (United States)  

---

## 🤖 1. AI-Assisted Development Disclosure
FitForge Agent was conceived, architected, and built with AI-assisted software development tools. All core architectural designs, multi-agent state machines, Pydantic schemas, and cloud deployment pipelines have been independently audited, tested, and validated with an 80-test automated verification suite.

---

## 🛠️ 2. Proven Technologies & Google Services Used
FitForge Agent is built using proven standard open-source libraries and verified Google Cloud Platform services:
* **Google Agent Development Kit (ADK)**: Multi-agent orchestration via `InMemoryRunner`.
* **Google GenAI SDK & Gemini 3.5 Flash**: Structured reasoning, normalization, evidence extraction, and strategic planning.
* **Google Cloud Run**: Fully managed container execution with least-privilege service account identity (`fitforge-runner`).
* **Google Cloud Firestore (Native Mode)**: Atomic persistence for workflow states and audit logs.
* **Google Secret Manager**: Zero-disk API key injection into runtime process memory.
* **FastAPI, Pydantic, Jinja2, HTMX, Pytest, Docker**: Core application framework, strict typing, responsive UI, and unit test runner.

---

## ⚖️ 3. Operational & Ethical Boundaries

1. **Candidate Decision Support Only**:
   FitForge Agent is exclusively designed to empower job candidates in assessing role alignment, identifying factual resume evidence, and preparing strategic interview positioning. It does **not** make hiring or screening decisions on behalf of employers.

2. **No Automated Job Application Spamming**:
   FitForge Agent does **not** perform mass automated job submissions, bot form-filling, or algorithmic application spamming.

3. **No Protected-Platform Web Scraping**:
   The system operates entirely on user-provided or synthetic input text. It does **not** bypass authentication barriers, scrape protected platforms, or violate third-party terms of service.

4. **Advisory Scores, Not Guarantees**:
   Fit scores (0–100) and recommendations (`Pursue`, `Investigate`, `Pass`) are algorithmic decision-support heuristics derived from factual evidence extraction. They represent alignment indicators, not legal advice or employment guarantees.

5. **Privacy & Public Demo Safeguards**:
   Users evaluating the public Cloud Run deployment should utilize the provided synthetic benchmarks (e.g., Restaurant District Manager) or anonymized text. Real personal PII should not be submitted to public shared endpoints.
