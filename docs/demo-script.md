# FitForge Agent — Video Demonstration Script (3.5 – 4 Minutes)

This script provides exact timing and narration for the video demonstration submitted to Devpost.

---

## ⏱️ Video Structure & Narration

### [0:00 – 0:25] The Problem: The High-Stakes Career Dilemma
* **Visual**: Camera on speaker / Split screen showing overwhelming job descriptions and resume text.
* **Narration**:
  > *"Every experienced professional knows the struggle: you find an intriguing opportunity, but the job description is dense, vague, and full of implied expectations. Candidates spend hours guessing whether they are truly qualified, struggling to map their actual career proof to role requirements, and walking into interviews without strategic talking points. Career decisions are high-stakes, yet our assessment tools are either generic keyword scrapers or unstructured chat bots."*

---

### [0:25 – 0:50] The Solution: FitForge Agent & Taskmaster
* **Visual**: FitForge Landing page (`https://fitforge-agent-169201386255.us-central1.run.app`). Clean interface banner highlighting Google ADK & Gemini 3.5 Flash.
* **Narration**:
  > *"Meet FitForge Agent, an evidence-backed multi-agent workflow engine built for the Google Agentic AI Hackathon in the Taskmaster category. Instead of generating generic fluff or hallucinating qualifications, FitForge coordinates five specialized AI agents powered by the Google Agent Development Kit and Gemini 3.5 Flash to extract factual career evidence, score multidimensional fit, and generate concrete interview strategy."*

---

### [0:50 – 2:30] Live Demonstration: Synthetic District Manager Workflow
* **Visual**: Click **Load Sample** (Restaurant District Manager profile). Show the filled candidate resume ($32M volume, 15 units, 98.4% audit scores) and Midwest franchise job description.
* **Narration**:
  > *"Let’s test FitForge with a realistic synthetic benchmark: an Operations Leader evaluating a Regional District Manager opportunity. We click 'Load Sample' to populate candidate priorities, compensation requirements, and role text, then submit for assessment."*
* **Visual**: Workflow progress bar moves through the 5-step agent lifecycle in real time.
* **Narration**:
  > *"Behind the scenes, the Workflow Coordinator manages our specialized Google ADK agents:
  > 1. The **Intake Agent** normalizes unstructured text and parses explicit criteria.
  > 2. The **Evidence Agent** maps factual proof from the resume directly against every single requirement.
  > 3. The **Fit Analyst** calculates an objective fit score across operations, finance, and talent leadership.
  > 4. The **Action Planner** synthesizes high-impact interview positioning and customized diligence questions.
  > 5. And crucially, our **Quality Gate** validates schema consistency, completeness, and evidence truthfulness before persisting the final state."*
* **Visual**: Display completed assessment: Fit Score 82/100 (`Investigate`), Evidence Matrix (9 mapped requirements), and the Strategic Action Plan.
* **Narration**:
  > *"Here is the output: a comprehensive 82/100 score recommending 'Investigate', highlighting that the candidate exceeds multi-unit unit scale (15 units vs 10 required), while flagging new-unit expansion as a talking point to address. The Action Plan provides tailored interview questions to probe franchise support structures."*

---

### [2:30 – 3:10] Architecture & Google Cloud Integration
* **Visual**: Zoom in on `docs/architecture.png`.
* **Narration**:
  > *"Let’s examine how FitForge is architected on Google Cloud Platform:
  > • The runtime is built using the **Google Agent Development Kit (ADK)** with `InMemoryRunner` for structured agent choreography.
  > • Reasoning and structured extraction are powered by **Gemini 3.5 Flash** using the official Google GenAI SDK.
  > • The application is deployed on **Google Cloud Run** in `us-central1` with automatic scale-to-zero, request-based CPU allocation, and a dedicated service identity.
  > • Credentials are never stored on disk—Cloud Run injects the Gemini API key securely from **Google Secret Manager** at startup.
  > • Every workflow state and audit event is saved atomically to **Google Cloud Firestore** in Native mode."*

---

### [3:10 – 3:40] Evidence Controls, Rate Limiting & Safety Guardrails
* **Visual**: Show hardened `/health` JSON and demonstrate rate limiter 429 response on immediate retry.
* **Narration**:
  > *"Security, cost containment, and ethical boundaries were top priorities:
  > • We implemented a process-level single-instance concurrency lock and a 60-second cooldown with SHA-256 IP masking.
  > • Our public `/health` endpoint is strictly hardened to reveal zero internal infrastructure metadata.
  > • The entire repository features an 80-test automated test suite with an offline socket tripwire, ensuring zero paid calls during development and CI."*

---

### [3:40 – 4:00] Limitations & Future Roadmap
* **Visual**: Camera back on speaker / Summary slide with GitHub repository link.
* **Narration**:
  > *"FitForge Agent empowers job seekers to make evidence-backed career moves. While today’s public demo uses an in-memory single-instance guard, our roadmap includes distributed Redis rate limiting, user authentication, and multi-round mock interview simulations. Check out the open-source code on GitHub. Thank you!"*
