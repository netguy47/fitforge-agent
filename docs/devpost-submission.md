# FitForge Agent — Devpost Submission Package (Copy-Ready)

This document contains copy-ready fields for the **FitForge Agent** entry in the **Google Agentic AI Hackathon**.

---

## 🏷️ 1. Project Overview

### Project Name
`FitForge Agent`

### Elevator Pitch (159 / 200 characters)
`Autonomous evidence-backed workflow using Google ADK, Gemini 3.6 Flash, Cloud Run, and Firestore to map career proof, score job fit, and produce an audited action plan.`

---

## 📖 2. Project Story

### Inspiration
Navigating career transitions and evaluating complex job opportunities is high-stakes, yet existing tools are fundamentally broken. Job seekers are forced to rely either on keyword-matching ATS scanners that miss transferable achievements or generic conversational LLMs that hallucinate qualifications and give vague advice. We set out to build an evidence-based multi-agent system that approaches career evaluation like an elite executive coach and diligent hiring auditor: extracting verifiable proof, scoring objective alignment, and formulating actionable interview intelligence without hallucinations.

### What It Does
FitForge Agent coordinates a specialized 5-agent pipeline orchestrated through the Google Agent Development Kit (ADK). The candidate supplies the source material once; no prompts or manual routing are required between stages:
1. **Intake Agent**: Normalizes unstructured candidate résumés and job postings into structured evaluation criteria.
2. **Evidence Agent**: Maps factual candidate proof line-by-line against explicit role requirements, identifying strong matches and potential gaps.
3. **Fit Analyst**: Computes a grounded, multi-factor fit score (0–100) and actionable recommendation (`Pursue`, `Investigate`, `Pass`).
4. **Action Planner**: Generates targeted interview positioning strategies, vulnerability defenses, and customized diligence questions.
5. **Quality Gatekeeper**: Enforces Pydantic schema consistency, completeness, and truthfulness before committing the final state to Google Cloud Firestore.

The autonomous lifecycle is `created → normalizing → mapping_evidence → scoring_fit → planning_actions → validating → completed`. Each specialist consumes structured state from the prior stage and passes validated output forward. The Quality Gatekeeper can trigger one controlled correction cycle before persistence. FitForge intentionally reserves the consequential decision to submit an application for the candidate while autonomously completing the entire assessment and action-planning workflow.

### How It Was Built
* **Agent Framework**: Google Agent Development Kit (ADK) using `InMemoryRunner` for multi-agent state choreography.
* **Reasoning Engine**: Gemini 3.6 Flash (`gemini-3.6-flash`) via the official Google GenAI SDK (`google-genai 2.20.0`), utilizing structured JSON generation and Pydantic validation.
* **Serverless Backend**: Google Cloud Run in `us-central1` with automated scale-to-zero, request-based CPU allocation, and a dedicated least-privilege service account (`fitforge-runner`).
* **Persistence Layer**: Google Cloud Firestore in Native mode (`(default)` database) for atomic workflow recovery and audit logging.
* **Security & Secret Management**: Google Secret Manager for zero-disk credential injection at container startup.
* **Web Frontend**: Python FastAPI with Jinja2 templates, HTMX for real-time progress updates, and a responsive Tailwind-style dark interface.
* **Verification & Safety**: An 80-test automated pytest suite with a network socket tripwire to guarantee zero paid calls during offline testing.

### Challenges We Overcame
1. **Eliminating Agent Hallucinations**: LLMs frequently invent experience to make a candidate look better. We solved this by designing the Evidence Agent to extract strict quotes and adding an independent Quality Gatekeeper that validates evidence grounding against the original input.
2. **Deterministic Offline Testing**: Ensuring rapid, zero-cost developer iteration without contacting live Gemini endpoints required building a deterministic mock slice alongside the ADK InMemoryRunner.
3. **Guarded Cloud Deployment**: Operating a public demo without exposure to runaway billing required crafting an in-memory single-instance concurrency lock and 60-second cooldown with SHA-256 IP masking.

### Accomplishments That We're Proud Of
* Fully verified end-to-end cloud pipeline on Google Cloud Run with live Gemini 3.6 Flash and Cloud Firestore persistence.
* Autonomous seven-state workflow with five strictly separated specialist agents and no manual routing between stages.
* 100% clean test suite with 80 passing automated unit and integration tests.
* Hardened security posture: zero credentials committed to Git, zero PII logged, and resource-scoped IAM permissions.
* Sub-100 millisecond response times on cached/deterministic requests and comprehensive structured reports on live runs.

### What We Learned
We mastered the Google Agent Development Kit (ADK) architecture, experiencing firsthand how separating agent responsibilities (normalization ➡️ evidence ➡️ scoring ➡️ planning ➡️ quality gating) produces dramatically higher accuracy and reliability compared to monolithic single-prompt LLM applications.

### What's Next for FitForge Agent
* **Multi-Turn Interactive Mock Interviews**: Real-time voice and text interview simulation based on the generated Action Plan.
* **Distributed Cloud Armor & Redis**: Scaling rate-limiting to multi-region Cloud Run deployments.
* **Multi-Opportunity Comparison**: Enabling candidates to compare multiple competing offers side-by-side on an objective evidence matrix.

---

## 🛠️ 3. Built With
* `Python`
* `FastAPI`
* `HTMX`
* `Pydantic`
* `Google Agent Development Kit`
* `Google GenAI SDK`
* `Gemini 3.6 Flash`
* `Google Cloud Run`
* `Google Cloud Firestore`
* `Google Secret Manager`
* `Pytest`
* `Docker`

---

## 📋 4. Additional Info (Form Fields)

* **Submitter Type**: `Individuals`
* **Country**: `United States`
* **Category**: `Taskmaster`
* **Project Start Date**: `08-26-26`
* **Google SDKs Used**: `Google Agent Development Kit (ADK)` and `Google GenAI SDK`
* **Google Cloud Services**: `Google Cloud Run`, `Google Cloud Firestore`, `Google Secret Manager`
* **AI Model**: `Gemini 3.6 Flash (gemini-3.6-flash)`
* **Reproducible Testing Available**: `Yes` (Comprehensive 80-test pytest suite with offline socket blocker)
* **Hosted Application URL**: `https://fitforge-agent-169201386255.us-central1.run.app`
* **Public GitHub Repository**: `https://github.com/netguy47/fitforge-agent`
* **Video Demo URL**: `https://youtu.be/iA8fy3MUdBs`
* **Eligibility Exclusion**: *Startup Excellence is NOT selected (Individual entry).*
