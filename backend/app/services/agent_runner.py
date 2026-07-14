from __future__ import annotations

import logging

from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.db.session import SessionLocal
from app.models import AgentLog, Candidate, Job, JobStatus, Resume, ResumeStatus, Score
from app.observability import log_task_event, logger
from app.schemas.structured import ScoreResult, StructuredCandidate, StructuredJD
from app.services.file_parser import TextExtractionError, extract_text
from app.services.llm_client import LLMClient
from app.services.scoring import normalize_score

SAFE_JOB_FAILURE_MESSAGE = "Background job processing failed."
SAFE_RESUME_FAILURE_MESSAGE = "Resume processing was interrupted."


def run_screening_job(job_id: int) -> None:
    """Run a screening job in the background with its own database session."""
    db = SessionLocal()
    try:
        _run(db, job_id)
    except Exception:
        _rollback_session(db, job_id, "job")
        log_task_event(logging.ERROR, "Background job failed unexpectedly", job_id=job_id, resume_id=None, stage="job")
        if get_settings().debug:
            logger.exception("Background job failed unexpectedly", extra={"job_id": job_id, "stage": "job"})
        _recover_unexpected_job_failure(job_id)
    finally:
        db.close()


def _run(db: Session, job_id: int) -> None:
    """Execute a complete screening pass, replacing the prior pass's business logs."""
    job = db.get(Job, job_id)
    if not job:
        return

    llm = LLMClient()
    # The model has no run identifier. A new full-job run therefore replaces the prior run's business log.
    db.query(AgentLog).filter(AgentLog.job_id == job.id).delete(synchronize_session=False)
    job.status = JobStatus.running
    job.error_message = None
    db.commit()
    log_task_event(logging.INFO, "Screening job started", job_id=job.id, resume_id=None, stage="job")
    _log(db, job.id, None, "job_started", "开始执行招聘筛选 Agent", "running")

    try:
        log_task_event(logging.INFO, "Parsing job description", job_id=job.id, resume_id=None, stage="parse_jd")
        _log(db, job.id, None, "parse_jd", "开始解析岗位 JD", "running")
        jd = llm.parse_jd(job.title, job.jd_text)
        job.jd_structured_json = jd.model_dump()
        db.commit()
        _log(db, job.id, None, "parse_jd", f"提取到 {len(jd.must_have_skills)} 个必备技能", "completed")
    except Exception:
        _rollback_session(db, job.id, "parse_jd")
        _finalize_job_failure(db, job.id, stage="parse_jd", message="Job description parsing failed.")
        log_task_event(logging.ERROR, "Job description parsing failed", job_id=job.id, resume_id=None, stage="parse_jd")
        if get_settings().debug:
            logger.exception("Job description parsing failed", extra={"job_id": job.id, "stage": "parse_jd"})
        return

    resumes = db.query(Resume).filter(Resume.job_id == job.id).order_by(Resume.id.asc()).all()
    for resume in resumes:
        _process_resume(db, job, resume, jd, llm)

    final_status = _settle_job_status(db, job.id)
    level = logging.INFO if final_status == JobStatus.completed else logging.ERROR
    message = "Screening job completed" if final_status == JobStatus.completed else "Screening job failed"
    log_task_event(level, message, job_id=job.id, resume_id=None, stage="job")


def _process_resume(db: Session, job: Job, resume: Resume, jd: StructuredJD, llm: LLMClient) -> bool:
    """Process one resume and upsert exactly one candidate and one score on success."""
    try:
        resume.status = ResumeStatus.extracting
        resume.error_message = None
        db.commit()
        log_task_event(logging.INFO, "Extracting resume text", job_id=job.id, resume_id=resume.id, stage="extract_text")
        _log(db, job.id, resume.id, "extract_text", f"开始提取 {resume.original_filename}", "running")
        resume.raw_text = extract_text(resume.file_path)
        resume.status = ResumeStatus.parsed
        db.commit()
        _log(db, job.id, resume.id, "extract_text", "简历文本提取完成", "completed")

        _log(db, job.id, resume.id, "parse_resume", "开始结构化候选人信息", "running")
        candidate_data = llm.parse_candidate(resume.raw_text, resume.original_filename)
        _log(db, job.id, resume.id, "parse_resume", "候选人信息解析完成", "completed")

        log_task_event(logging.INFO, "Scoring candidate", job_id=job.id, resume_id=resume.id, stage="score_candidate")
        _log(db, job.id, resume.id, "score_candidate", "开始多维评分", "running")
        score_data = llm.score_candidate(jd, candidate_data)
        total, level, detail = normalize_score(score_data)
        _upsert_candidate_and_score(db, job, resume, candidate_data, total, level, detail, score_data)
        _log(db, job.id, resume.id, "score_candidate", f"评分完成：{total} 分，级别 {level}", "completed")
        log_task_event(logging.INFO, "Resume screening completed", job_id=job.id, resume_id=resume.id, stage="score_candidate")
        return True
    except TextExtractionError:
        _rollback_session(db, job.id, "extract_text")
        _mark_resume_failed(db, job.id, resume, "Resume text extraction failed.", "extract_text")
    except ValueError:
        _rollback_session(db, job.id, "validation")
        _mark_resume_failed(db, job.id, resume, "Resume data validation failed.", "validation")
    except Exception:
        _rollback_session(db, job.id, "processing")
        _mark_resume_failed(db, job.id, resume, "Resume processing failed.", "processing")
        if get_settings().debug:
            logger.exception("Resume processing failed", extra={"job_id": job.id, "resume_id": resume.id, "stage": "processing"})
    return False


def _upsert_candidate_and_score(
    db: Session,
    job: Job,
    resume: Resume,
    candidate_data: StructuredCandidate,
    total: int,
    level: str,
    detail: dict,
    score_data: ScoreResult,
) -> None:
    """Update existing derived records or create them once for a successful resume pass."""
    try:
        candidate = (
            db.query(Candidate)
            .options(joinedload(Candidate.score))
            .filter(Candidate.resume_id == resume.id)
            .one_or_none()
        )
        if candidate is None:
            candidate = Candidate(resume_id=resume.id, name=candidate_data.name, structured_json={})
            db.add(candidate)
            db.flush()

        candidate.name = candidate_data.name
        candidate.email = candidate_data.email
        candidate.phone = candidate_data.phone
        candidate.structured_json = candidate_data.model_dump()

        score = candidate.score
        if score is None:
            score = Score(candidate_id=candidate.id, job_id=job.id, total_score=0, level="", score_detail_json={})
            db.add(score)

        score.job_id = job.id
        score.total_score = total
        score.level = level
        score.score_detail_json = detail
        score.matched_points_json = score_data.matched_points
        score.missing_points_json = score_data.missing_points
        score.interview_questions_json = score_data.interview_questions
        score.invitation_message = score_data.invitation_message
        score.summary = score_data.summary
        resume.status = ResumeStatus.completed
        resume.error_message = None
        db.commit()
    except Exception:
        db.rollback()
        raise


def _mark_resume_failed(db: Session, job_id: int, resume: Resume, message: str, stage: str) -> None:
    """Remove stale derived data and record a safe failure for a resume."""
    try:
        candidate = (
            db.query(Candidate)
            .options(joinedload(Candidate.score))
            .filter(Candidate.resume_id == resume.id)
            .one_or_none()
        )
        if candidate is not None:
            if candidate.score is not None:
                db.delete(candidate.score)
            db.delete(candidate)
            db.flush()
        resume.status = ResumeStatus.failed
        resume.error_message = message
        db.commit()
    except Exception:
        db.rollback()
        raise
    _log(db, job_id, resume.id, "resume_failed", message, "failed")
    log_task_event(logging.ERROR, "Resume screening failed", job_id=job_id, resume_id=resume.id, stage=stage)


def _settle_job_status(db: Session, job_id: int) -> JobStatus:
    """Set the Job terminal state from persisted resume terminal states and record one terminal log."""
    resumes = db.query(Resume).filter(Resume.job_id == job_id).all()
    completed_count = sum(resume.status == ResumeStatus.completed for resume in resumes)
    job = db.get(Job, job_id)
    if job is None:
        raise RuntimeError("Job disappeared before status settlement.")

    if completed_count > 0:
        job.status = JobStatus.completed
        job.error_message = None
        step = "job_completed"
        message = f"筛选完成，成功处理 {completed_count}/{len(resumes)} 份简历"
        log_status = "completed"
    else:
        job.status = JobStatus.failed
        job.error_message = "All resume processing attempts failed."
        step = "job_failed"
        message = job.error_message
        log_status = "failed"

    db.add(AgentLog(job_id=job_id, resume_id=None, step=step, message=message, status=log_status))
    db.commit()
    return job.status


def _recover_unexpected_job_failure(job_id: int) -> None:
    """Use a clean session to converge an unexpectedly interrupted job to a safe terminal state."""
    recovery_db = SessionLocal()
    try:
        _finalize_job_failure(recovery_db, job_id, stage="job", message=SAFE_JOB_FAILURE_MESSAGE)
    except Exception:
        _rollback_session(recovery_db, job_id, "job_recovery")
        log_task_event(logging.ERROR, "Background job recovery failed", job_id=job_id, resume_id=None, stage="job_recovery")
        if get_settings().debug:
            logger.exception("Background job recovery failed", extra={"job_id": job_id, "stage": "job_recovery"})
    finally:
        recovery_db.close()


def _finalize_job_failure(db: Session, job_id: int, *, stage: str, message: str) -> None:
    """Mark one job and only its unfinished resumes as failed in one recovery transaction."""
    job = db.get(Job, job_id)
    if job is None:
        return

    unfinished_statuses = [
        ResumeStatus.uploaded,
        ResumeStatus.extracting,
        ResumeStatus.parsed,
        ResumeStatus.scored,
    ]
    db.query(Resume).filter(Resume.job_id == job_id, Resume.status.in_(unfinished_statuses)).update(
        {Resume.status: ResumeStatus.failed, Resume.error_message: SAFE_RESUME_FAILURE_MESSAGE},
        synchronize_session=False,
    )
    job.status = JobStatus.failed
    job.error_message = message
    db.add(AgentLog(job_id=job_id, resume_id=None, step="job_failed", message=message, status="failed"))
    db.commit()
    log_task_event(logging.ERROR, "Job failure state persisted", job_id=job_id, resume_id=None, stage=stage)


def _rollback_session(db: Session, job_id: int, stage: str) -> None:
    """Rollback safely and emit only a non-sensitive operational event if rollback itself fails."""
    try:
        db.rollback()
    except Exception:
        log_task_event(logging.ERROR, "Database rollback failed", job_id=job_id, resume_id=None, stage=stage)


def _log(db: Session, job_id: int, resume_id: int | None, step: str, message: str, status: str) -> None:
    """Persist the current run's business log without using application logs for PII."""
    db.add(AgentLog(job_id=job_id, resume_id=resume_id, step=step, message=message, status=status))
    db.commit()
