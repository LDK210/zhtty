from __future__ import annotations

import re

from app.schemas.structured import ProjectItem, ScoreResult, StructuredCandidate, StructuredJD

KNOWN_SKILLS = [
    "Java",
    "Spring Boot",
    "MySQL",
    "Redis",
    "Docker",
    "Python",
    "FastAPI",
    "React",
    "TypeScript",
    "Vue",
    "PostgreSQL",
    "Linux",
]


def parse_jd(text: str, title: str) -> StructuredJD:
    skills = _find_skills(text)
    must_have = skills[:3] or ["Java", "Spring Boot", "MySQL"]
    nice_to_have = [skill for skill in skills[3:] if skill not in must_have] or ["Redis", "Docker"]
    return StructuredJD(
        position=title,
        must_have_skills=must_have,
        nice_to_have_skills=nice_to_have,
        experience_requirements="有相关项目经验" if "项目" in text else "",
        education_requirement="本科及以上优先" if "本科" in text or "大学" in text else "",
        responsibilities=["接口开发", "数据库设计", "后端服务维护"],
    )


def parse_candidate(text: str, filename: str) -> StructuredCandidate:
    email = _first_match(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
    phone = _first_match(r"(?<!\d)(?:1[3-9]\d{9}|\d{3,4}[- ]?\d{7,8})(?!\d)", text)
    name = _extract_name(text, filename)
    skills = _find_skills(text)
    projects = []
    if "项目" in text or any(skill in text for skill in skills):
        projects.append(
            ProjectItem(
                name="简历项目经历",
                description=_clip(text, 180),
                tech_stack=skills[:6],
            )
        )
    return StructuredCandidate(
        name=name,
        phone=phone,
        email=email,
        skills=skills,
        projects=projects,
        work_experience=["包含实习或项目经历"] if "实习" in text or "工作" in text else [],
        summary=f"{name} 的简历包含 {', '.join(skills[:5]) or '基础技能'} 等信息。",
    )


def score_candidate(jd: StructuredJD, candidate: StructuredCandidate) -> ScoreResult:
    candidate_skills = {skill.lower() for skill in candidate.skills}
    must_matches = [skill for skill in jd.must_have_skills if skill.lower() in candidate_skills]
    nice_matches = [skill for skill in jd.nice_to_have_skills if skill.lower() in candidate_skills]
    missing = [skill for skill in jd.must_have_skills if skill.lower() not in candidate_skills]

    skill_score = round(35 * (len(must_matches) / max(len(jd.must_have_skills), 1)))
    skill_score += min(len(nice_matches) * 3, 6)
    project_score = 20 if candidate.projects else 8
    experience_score = 12 if candidate.work_experience else 8
    education_score = 8 if candidate.education or "本科" in candidate.summary else 6
    bonus_score = min(len(nice_matches) * 4, 10)
    risk_score = min(len(missing) * 2, 5)

    matched_points = [f"匹配岗位技能：{skill}" for skill in must_matches + nice_matches]
    if candidate.projects:
        matched_points.append("简历中包含与岗位相关的项目经历")
    missing_points = [f"未明确体现必备技能：{skill}" for skill in missing]

    focus = (must_matches + nice_matches + jd.must_have_skills)[:2] or ["项目经验"]
    questions = [f"请介绍你在项目中使用 {item} 的具体场景。" for item in focus]
    questions.append("如果线上接口响应变慢，你会如何排查？")

    return ScoreResult(
        skill_score=skill_score,
        project_score=project_score,
        experience_score=experience_score,
        education_score=education_score,
        bonus_score=bonus_score,
        risk_score=risk_score,
        matched_points=matched_points or ["简历具备一定岗位相关背景"],
        missing_points=missing_points,
        interview_questions=questions,
        invitation_message=(
            f"您好 {candidate.name}，我们看到了您的简历，觉得您与 {jd.position} 岗位比较匹配，"
            "想邀请您参加一轮线上面试，期待与您进一步交流。"
        ),
        summary=f"{candidate.name} 与 {jd.position} 的匹配度由关键词和项目经历综合生成。",
    )


def _find_skills(text: str) -> list[str]:
    lowered = text.lower()
    return [skill for skill in KNOWN_SKILLS if skill.lower() in lowered]


def _first_match(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text)
    return match.group(0) if match else None


def _extract_name(text: str, filename: str) -> str:
    patterns = [r"姓名[:：]\s*([\u4e00-\u9fa5A-Za-z]{2,20})", r"Name[:：]\s*([A-Za-z ]{2,40})"]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    stem = re.sub(r"[_\-\d]+", " ", filename.rsplit(".", 1)[0]).strip()
    return stem or "Unknown Candidate"


def _clip(text: str, length: int) -> str:
    compact = " ".join(text.split())
    return compact[:length] + ("..." if len(compact) > length else "")
