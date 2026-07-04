from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import AgentLog, Candidate, Job, JobStatus, Resume, ResumeStatus, Score
from app.schemas.structured import StructuredJD
from app.services.file_parser import TextExtractionError, extract_text
from app.services.llm_client import LLMClient
from app.services.scoring import normalize_score


def run_screening_job(job_id: int) -> None:
    db = SessionLocal()
    try:
        _run(db, job_id)
    finally:
        db.close()


def _run(db: Session, job_id: int) -> None:
    job = db.get(Job, job_id)
    if not job:
        return

    llm = LLMClient()
    job.status = JobStatus.running
    job.error_message = None
    db.commit()
    _log(db, job.id, None, "job_started", "开始执行招聘筛选 Agent", "running")

    try:
        _log(db, job.id, None, "parse_jd", "开始解析岗位 JD", "running")
        jd = llm.parse_jd(job.title, job.jd_text)
        job.jd_structured_json = jd.model_dump()
        db.commit()
        _log(db, job.id, None, "parse_jd", f"提取到 {len(jd.must_have_skills)} 个必备技能", "completed")
    except Exception as exc:
        job.status = JobStatus.failed
        job.error_message = f"JD 解析失败：{exc}"
        db.commit()
        _log(db, job.id, None, "parse_jd", job.error_message, "failed")
        return

    resumes = db.query(Resume).filter(Resume.job_id == job.id).order_by(Resume.id.asc()).all()
    success_count = 0
    for resume in resumes:
        if _process_resume(db, job, resume, jd, llm):
            success_count += 1

    if success_count > 0:
        job.status = JobStatus.completed
        job.error_message = None
        _log(db, job.id, None, "job_completed", f"筛选完成，成功处理 {success_count}/{len(resumes)} 份简历", "completed")
    else:
        job.status = JobStatus.failed
        job.error_message = "全部简历处理失败"
        _log(db, job.id, None, "job_failed", job.error_message, "failed")
    db.commit()


def _process_resume(db: Session, job: Job, resume: Resume, jd: StructuredJD, llm: LLMClient) -> bool:
    try:
        resume.status = ResumeStatus.extracting
        resume.error_message = None
        db.commit()
        _log(db, job.id, resume.id, "extract_text", f"开始提取 {resume.original_filename}", "running")
        resume.raw_text = extract_text(resume.file_path)
        resume.status = ResumeStatus.parsed
        db.commit()
        _log(db, job.id, resume.id, "extract_text", "简历文本提取完成", "completed")

        _log(db, job.id, resume.id, "parse_resume", "开始结构化候选人信息", "running")
        candidate_data = llm.parse_candidate(resume.raw_text, resume.original_filename)
        candidate = Candidate(
            resume_id=resume.id,
            name=candidate_data.name,
            email=candidate_data.email,
            phone=candidate_data.phone,
            structured_json=candidate_data.model_dump(),
        )
        db.add(candidate)
        db.flush()
        _log(db, job.id, resume.id, "parse_resume", f"候选人 {candidate.name} 解析完成", "completed")

        _log(db, job.id, resume.id, "score_candidate", "开始多维评分", "running")
        score_data = llm.score_candidate(jd, candidate_data)
        total, level, detail = normalize_score(score_data)
        score = Score(
            candidate_id=candidate.id,
            job_id=job.id,
            total_score=total,
            level=level,
            score_detail_json=detail,
            matched_points_json=score_data.matched_points,
            missing_points_json=score_data.missing_points,
            interview_questions_json=score_data.interview_questions,
            invitation_message=score_data.invitation_message,
            summary=score_data.summary,
        )
        db.add(score)
        resume.status = ResumeStatus.completed
        db.commit()
        _log(db, job.id, resume.id, "score_candidate", f"评分完成：{total} 分，级别 {level}", "completed")
        return True
    except (TextExtractionError, ValueError) as exc:
        _mark_resume_failed(db, job.id, resume, str(exc))
    except Exception as exc:
        _mark_resume_failed(db, job.id, resume, f"处理失败：{exc}")
    return False


def _mark_resume_failed(db: Session, job_id: int, resume: Resume, message: str) -> None:
    resume.status = ResumeStatus.failed
    resume.error_message = message
    db.commit()
    _log(db, job_id, resume.id, "resume_failed", message, "failed")


def _log(db: Session, job_id: int, resume_id: int | None, step: str, message: str, status: str) -> None:
    db.add(AgentLog(job_id=job_id, resume_id=resume_id, step=step, message=message, status=status))
    db.commit()
