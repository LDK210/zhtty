from __future__ import annotations

from pathlib import Path
from typing import List
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile, status
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.db import get_db
from app.exceptions import AppError
from app.models import AgentLog, Candidate, Job, JobStatus, Resume, ResumeStatus, Score
from app.schemas.api import (
    AgentLogRead,
    CandidateResult,
    JobCreate,
    JobRead,
    ResumeRead,
    RunResponse,
    UploadResponse,
)
from app.services.agent_runner import run_screening_job

router = APIRouter(prefix="/api")


@router.post("/jobs", response_model=JobRead, status_code=status.HTTP_201_CREATED)
def create_job(payload: JobCreate, db: Session = Depends(get_db)) -> JobRead:
    """Create a recruitment job from a title and job description."""
    job = Job(title=payload.title.strip(), jd_text=payload.jd_text.strip(), status=JobStatus.draft)
    db.add(job)
    db.commit()
    db.refresh(job)
    return _job_read(job)


@router.get("/jobs", response_model=List[JobRead])
def list_jobs(db: Session = Depends(get_db)) -> list[JobRead]:
    """List jobs with their resume status summaries."""
    jobs = db.query(Job).options(joinedload(Job.resumes)).order_by(Job.created_at.desc()).all()
    return [_job_read(job) for job in jobs]


@router.get("/jobs/{job_id}", response_model=JobRead)
def get_job(job_id: int, db: Session = Depends(get_db)) -> JobRead:
    """Return one job and its current progress."""
    job = _get_job_or_404(db, job_id)
    return _job_read(job)


@router.post("/jobs/{job_id}/resumes", response_model=UploadResponse)
async def upload_resumes(job_id: int, files: list[UploadFile] = File(...), db: Session = Depends(get_db)) -> UploadResponse:
    """Store validated PDF or DOCX resumes for a job."""
    job = _get_job_or_404(db, job_id)
    settings = get_settings()
    settings.upload_path.mkdir(parents=True, exist_ok=True)

    created: list[Resume] = []
    for file in files:
        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in {".pdf", ".docx"}:
            raise AppError(code="invalid_file_type", message="Only PDF and DOCX files are supported.", status_code=400)

        content = await file.read()
        if len(content) > settings.max_upload_size_mb * 1024 * 1024:
            raise AppError(code="file_too_large", message="Uploaded file exceeds the allowed size.", status_code=400)

        safe_name = f"{uuid4().hex}{suffix}"
        path = settings.upload_path / safe_name
        path.write_bytes(content)
        resume = Resume(
            job_id=job.id,
            original_filename=file.filename or safe_name,
            file_path=str(path),
            status=ResumeStatus.uploaded,
        )
        db.add(resume)
        created.append(resume)

    if created and job.status == JobStatus.draft:
        job.status = JobStatus.ready
    db.commit()
    for resume in created:
        db.refresh(resume)
    return UploadResponse(uploaded=len(created), resumes=[ResumeRead.model_validate(item) for item in created])


@router.post("/jobs/{job_id}/run", response_model=RunResponse)
def run_job(job_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)) -> RunResponse:
    """Start or safely rerun the screening process for an existing job."""
    job = _get_job_or_404(db, job_id)
    if not job.jd_text.strip():
        raise AppError(code="invalid_job", message="Job description cannot be empty.", status_code=400)
    resume_count = db.query(Resume).filter(Resume.job_id == job.id).count()
    if resume_count == 0:
        raise AppError(code="no_resumes", message="Upload at least one resume before running.", status_code=400)
    if job.status == JobStatus.running:
        raise AppError(code="job_running", message="Job is already running.", status_code=409)

    job.status = JobStatus.running
    job.error_message = None
    db.commit()
    background_tasks.add_task(run_screening_job, job.id)
    return RunResponse(job_id=job.id, status=job.status, message="Screening job started.")


@router.get("/jobs/{job_id}/results", response_model=List[CandidateResult])
def get_results(job_id: int, db: Session = Depends(get_db)) -> list[CandidateResult]:
    """Return the current scored candidate ranking for a job."""
    _get_job_or_404(db, job_id)
    candidates = (
        db.query(Candidate)
        .join(Resume)
        .join(Score)
        .options(joinedload(Candidate.score))
        .filter(Resume.job_id == job_id)
        .order_by(Score.total_score.desc())
        .all()
    )
    return [CandidateResult.model_validate(candidate) for candidate in candidates if candidate.score]


@router.get("/candidates/{candidate_id}", response_model=CandidateResult)
def get_candidate(candidate_id: int, db: Session = Depends(get_db)) -> CandidateResult:
    """Return one scored candidate by ID."""
    candidate = db.query(Candidate).options(joinedload(Candidate.score)).filter(Candidate.id == candidate_id).first()
    if not candidate or not candidate.score:
        raise AppError(code="candidate_not_found", message="Candidate not found.", status_code=404)
    return CandidateResult.model_validate(candidate)


@router.get("/jobs/{job_id}/logs", response_model=List[AgentLogRead])
def get_logs(job_id: int, db: Session = Depends(get_db)) -> list[AgentLogRead]:
    """Return the current business processing log for a job."""
    _get_job_or_404(db, job_id)
    logs = db.query(AgentLog).filter(AgentLog.job_id == job_id).order_by(AgentLog.created_at.asc()).all()
    return [AgentLogRead.model_validate(log) for log in logs]


def _get_job_or_404(db: Session, job_id: int) -> Job:
    """Load a job or raise a stable not-found API error."""
    job = db.query(Job).options(joinedload(Job.resumes)).filter(Job.id == job_id).first()
    if not job:
        raise AppError(code="job_not_found", message="Job not found.", status_code=404)
    return job


def _job_read(job: Job) -> JobRead:
    """Build a job response with resume progress counts."""
    counts = {status.value: 0 for status in ResumeStatus}
    for resume in job.resumes:
        counts[resume.status.value] += 1
    data = JobRead.model_validate(job)
    data.progress = counts
    return data
