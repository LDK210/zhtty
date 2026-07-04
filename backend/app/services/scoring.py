from __future__ import annotations

from app.schemas.structured import ScoreResult


MAX_SCORES = {
    "skill_score": 35,
    "project_score": 25,
    "experience_score": 15,
    "education_score": 10,
    "bonus_score": 10,
    "risk_score": 5,
}


def clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, int(value or 0)))


def normalize_score(score: ScoreResult) -> tuple[int, str, dict]:
    detail = {
        "skill_score": clamp(score.skill_score, 0, MAX_SCORES["skill_score"]),
        "project_score": clamp(score.project_score, 0, MAX_SCORES["project_score"]),
        "experience_score": clamp(score.experience_score, 0, MAX_SCORES["experience_score"]),
        "education_score": clamp(score.education_score, 0, MAX_SCORES["education_score"]),
        "bonus_score": clamp(score.bonus_score, 0, MAX_SCORES["bonus_score"]),
        "risk_score": clamp(score.risk_score, 0, MAX_SCORES["risk_score"]),
    }
    total = (
        detail["skill_score"]
        + detail["project_score"]
        + detail["experience_score"]
        + detail["education_score"]
        + detail["bonus_score"]
        - detail["risk_score"]
    )
    total = clamp(total, 0, 100)
    return total, recommendation_level(total), detail


def recommendation_level(total: int) -> str:
    if total >= 80:
        return "strong_recommend"
    if total >= 65:
        return "recommend"
    if total >= 50:
        return "maybe"
    return "not_recommend"
