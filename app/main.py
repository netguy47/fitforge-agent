"""FastAPI Application for FitForge Agent (Milestone 1)."""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Header, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.coordinator import WorkflowCoordinator
from app.models import WorkflowInput, WorkflowResult
from app.repositories.in_memory import workflow_repo

# Initialize paths
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
SAMPLES_DIR = BASE_DIR.parent / "samples"

app = FastAPI(
    title="FitForge Agent",
    description="Evidence-Based Job Opportunity Assessment Multi-Agent System",
    version="0.1.0",
)

# CORS middleware: environment-controlled allowlist (never wildcard with credentials)
_allowed_origins = [
    origin.strip()
    for origin in os.environ.get("ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Accept"],
)

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Jinja2 Templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Coordinator instance
coordinator = WorkflowCoordinator(repo=workflow_repo)


@app.get("/health", tags=["System"])
async def health_check() -> Dict[str, str]:
    """Health check endpoint confirming service status."""
    return {
        "status": "healthy",
        "milestone": "1",
        "version": "0.1.0",
        "mode": "deterministic_local_slice",
    }


@app.get("/api/sample", tags=["Workflows"])
async def get_sample_data() -> Dict[str, Any]:
    """Return fictionalized restaurant district manager sample data."""
    sample_file = SAMPLES_DIR / "restaurant_district_manager.json"
    if not sample_file.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Sample dataset not found."
        )
    with open(sample_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


@app.get("/", response_class=HTMLResponse, tags=["Web Interface"])
async def get_index_page(request: Request):
    """Render main web application interface."""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "workflow": None,
        },
    )


# --- Input length constraints ---
_MIN_INPUT_LEN = 50
_MAX_INPUT_LEN = 100_000
_MAX_PRIORITY_LEN = 10_000
_MAX_NON_NEGOTIABLES = 20


@app.post("/api/workflows", tags=["Workflows"])
async def create_workflow(
    workflow_input: WorkflowInput,
    request: Request,
    accept: Optional[str] = Header(None),
):
    """Execute multi-agent workflow assessment on submitted résumé and job description."""
    resume_stripped = workflow_input.resume_text.strip()
    jd_stripped = workflow_input.job_description_text.strip()

    if not resume_stripped:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Résumé text cannot be empty.",
        )
    if not jd_stripped:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Job description text cannot be empty.",
        )
    if len(resume_stripped) < _MIN_INPUT_LEN:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Résumé text must be at least {_MIN_INPUT_LEN} characters.",
        )
    if len(jd_stripped) < _MIN_INPUT_LEN:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Job description must be at least {_MIN_INPUT_LEN} characters.",
        )
    if len(resume_stripped) > _MAX_INPUT_LEN:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Résumé text must not exceed {_MAX_INPUT_LEN} characters.",
        )
    if len(jd_stripped) > _MAX_INPUT_LEN:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Job description must not exceed {_MAX_INPUT_LEN} characters.",
        )
    # Priority field length checks
    priorities = workflow_input.priorities
    for field_name, field_val in [
        ("min_compensation", priorities.min_compensation),
        ("location_preference", priorities.location_preference),
        ("desired_role_type", priorities.desired_role_type),
    ]:
        if field_val and len(field_val) > _MAX_PRIORITY_LEN:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Priority field '{field_name}' must not exceed {_MAX_PRIORITY_LEN} characters.",
            )
    if len(priorities.non_negotiables) > _MAX_NON_NEGOTIABLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Non-negotiables list must not exceed {_MAX_NON_NEGOTIABLES} items.",
        )

    # Run deterministic workflow pipeline
    result = coordinator.execute_workflow(workflow_input)

    # Return HTML partial if browser UI requested text/html
    if accept and "text/html" in accept:
        return templates.TemplateResponse(
            request=request,
            name="partials/workflow_result.html",
            context={
                "workflow": result,
            },
        )

    # Otherwise return JSON model
    return result


@app.get("/api/workflows/{workflow_id}", response_model=WorkflowResult, tags=["Workflows"])
async def get_workflow(workflow_id: str):
    """Retrieve full workflow state and audit trail by workflow ID."""
    workflow = workflow_repo.get(workflow_id)
    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID '{workflow_id}' not found.",
        )
    return workflow
