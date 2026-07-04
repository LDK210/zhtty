from __future__ import annotations

import json

from openai import OpenAI
from pydantic import ValidationError

from app.config import get_settings
from app.schemas.structured import ScoreResult, StructuredCandidate, StructuredJD
from app.services import mock_llm


class LLMClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = None
        if not self.settings.mock_mode:
            self.client = OpenAI(api_key=self.settings.openai_api_key, base_url=self.settings.openai_base_url)

    def parse_jd(self, title: str, text: str) -> StructuredJD:
        if self.settings.mock_mode:
            return mock_llm.parse_jd(text, title)
        payload = self._json_chat(
            "Extract a job description into the requested JSON shape.",
            f"Title: {title}\nJD:\n{text}",
        )
        return StructuredJD.model_validate(payload)

    def parse_candidate(self, text: str, filename: str) -> StructuredCandidate:
        if self.settings.mock_mode:
            return mock_llm.parse_candidate(text, filename)
        payload = self._json_chat(
            "Extract a resume into structured candidate JSON. Use empty arrays for missing lists.",
            f"Filename: {filename}\nResume text:\n{text[:12000]}",
        )
        return StructuredCandidate.model_validate(payload)

    def score_candidate(self, jd: StructuredJD, candidate: StructuredCandidate) -> ScoreResult:
        if self.settings.mock_mode:
            return mock_llm.score_candidate(jd, candidate)
        payload = self._json_chat(
            (
                "Score the candidate for the job. Return only JSON with skill_score, project_score, "
                "experience_score, education_score, bonus_score, risk_score, matched_points, "
                "missing_points, interview_questions, invitation_message, and summary."
            ),
            f"JD JSON:\n{jd.model_dump_json()}\nCandidate JSON:\n{candidate.model_dump_json()}",
        )
        try:
            return ScoreResult.model_validate(payload)
        except ValidationError as exc:
            raise ValueError(f"ScoreResult validation failed: {exc}") from exc

    def _json_chat(self, system: str, user: str) -> dict:
        assert self.client is not None
        response = self.client.chat.completions.create(
            model=self.settings.openai_model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)
