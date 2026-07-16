"""Public API tests for hiring-criteria draft lifecycle operations."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.models import HiringCriteriaVersion


def _create_job(client: TestClient, jd_text: str = "Build reliable Python services.") -> int:
    """Create a minimal job and return its public identifier."""
    response = client.post("/api/jobs", json={"title": "Backend Engineer", "jd_text": jd_text})
    assert response.status_code == 201
    return response.json()["id"]


def _error_payload(response: object) -> None:
    """Assert the established error body and request correlation contract."""
    payload = response.json()
    assert set(("code", "message", "request_id")).issubset(payload)
    assert payload["request_id"]
    assert response.headers["X-Request-ID"] == payload["request_id"]


def _add_version(job_id: int, version_number: int, status: str) -> HiringCriteriaVersion:
    """Persist a historical criteria version directly for versioning test setup."""
    db = SessionLocal()
    try:
        criteria = HiringCriteriaVersion(
            job_id=job_id,
            version_number=version_number,
            status=status,
            source_jd_text="Historical JD",
            criteria_json={},
        )
        db.add(criteria)
        db.commit()
        db.refresh(criteria)
        return criteria
    finally:
        db.close()


def test_create_draft_uses_job_jd_and_first_version(client: TestClient) -> None:
    """Create a first draft with server-selected draft status and version number."""
    job_id = _create_job(client, "Job default JD")
    response = client.post(f"/api/jobs/{job_id}/criteria/draft", json={"criteria_json": {}})
    assert response.status_code == 201
    assert response.json()["job_id"] == job_id
    assert response.json()["version_number"] == 1
    assert response.json()["status"] == "draft"
    assert response.json()["source_jd_text"] == "Job default JD"


def test_create_draft_uses_next_version_after_historical_versions(client: TestClient) -> None:
    """Number a new draft after the greatest active or archived historical version."""
    job_id = _create_job(client)
    _add_version(job_id, 3, "archived")
    _add_version(job_id, 7, "active")
    response = client.post(f"/api/jobs/{job_id}/criteria/draft", json={"criteria_json": {"skills": []}})
    assert response.status_code == 201
    assert response.json()["version_number"] == 8


def test_create_draft_rejects_duplicate_and_missing_job(client: TestClient) -> None:
    """Reject duplicate drafts and drafts requested for absent jobs."""
    job_id = _create_job(client)
    assert client.post(f"/api/jobs/{job_id}/criteria/draft", json={}).status_code == 201
    duplicate = client.post(f"/api/jobs/{job_id}/criteria/draft", json={})
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "criteria_draft_already_exists"
    _error_payload(duplicate)
    missing = client.post("/api/jobs/999999/criteria/draft", json={})
    assert missing.status_code == 404
    assert missing.json()["code"] == "job_not_found"
    _error_payload(missing)


def test_get_draft_only_returns_current_draft(client: TestClient) -> None:
    """Read the job's draft rather than active or archived history."""
    job_id = _create_job(client)
    _add_version(job_id, 1, "active")
    draft = client.post(f"/api/jobs/{job_id}/criteria/draft", json={"criteria_json": {"level": "senior"}})
    response = client.get(f"/api/jobs/{job_id}/criteria/draft")
    assert response.status_code == 200
    assert response.json()["id"] == draft.json()["id"]
    assert response.json()["criteria_json"] == {"level": "senior"}


def test_get_draft_rejects_when_missing(client: TestClient) -> None:
    """Return a stable not-found error when a job has no draft."""
    job_id = _create_job(client)
    response = client.get(f"/api/jobs/{job_id}/criteria/draft")
    assert response.status_code == 404
    assert response.json()["code"] == "criteria_draft_not_found"
    _error_payload(response)


def test_patch_draft_updates_mutable_fields_atomically(client: TestClient) -> None:
    """Update JD and criteria JSON while retaining immutable persisted fields."""
    job_id = _create_job(client)
    created = client.post(
        f"/api/jobs/{job_id}/criteria/draft",
        json={"source_jd_text": "Original JD", "criteria_json": {"skills": ["Python"]}},
    ).json()
    response = client.patch(
        f"/api/jobs/{job_id}/criteria/draft/{created['id']}",
        json={
            "source_jd_text": "Updated JD",
            "criteria_json": {"skills": ["Python", "FastAPI"]},
            "created_by": "HR reviewer",
        },
    )
    assert response.status_code == 200
    assert response.json()["source_jd_text"] == "Updated JD"
    assert response.json()["criteria_json"] == {"skills": ["Python", "FastAPI"]}
    assert response.json()["created_by"] == "HR reviewer"
    invalid = client.patch(
        f"/api/jobs/{job_id}/criteria/draft/{created['id']}", json={"source_jd_text": ""}
    )
    assert invalid.status_code == 422
    assert client.get(f"/api/jobs/{job_id}/criteria/draft").json()["source_jd_text"] == "Updated JD"


def test_patch_rejects_non_draft_and_cross_job_version(client: TestClient) -> None:
    """Allow updates only to the requested job's persisted draft version."""
    first_job_id = _create_job(client)
    active = _add_version(first_job_id, 1, "active")
    non_draft = client.patch(
        f"/api/jobs/{first_job_id}/criteria/draft/{active.id}", json={"created_by": "HR"}
    )
    assert non_draft.status_code == 409
    assert non_draft.json()["code"] == "criteria_version_not_draft"
    _error_payload(non_draft)
    second_job_id = _create_job(client)
    foreign_draft = client.post(f"/api/jobs/{second_job_id}/criteria/draft", json={}).json()
    cross_job = client.patch(
        f"/api/jobs/{first_job_id}/criteria/draft/{foreign_draft['id']}", json={"created_by": "HR"}
    )
    assert cross_job.status_code == 404
    assert cross_job.json()["code"] == "criteria_version_not_found"
    _error_payload(cross_job)


def test_draft_schema_rejects_non_objects_and_server_controlled_fields(client: TestClient) -> None:
    """Reject invalid JSON shapes and attempts to control immutable draft properties."""
    job_id = _create_job(client)
    for payload in (
        {"criteria_json": []},
        {"criteria_json": "not-an-object"},
        {"criteria_json": 7},
        {"status": "active"},
        {"version_number": 99},
        {"job_id": 999},
    ):
        response = client.post(f"/api/jobs/{job_id}/criteria/draft", json=payload)
        assert response.status_code == 422
        _error_payload(response)


def test_patch_rejects_server_controlled_fields(client: TestClient) -> None:
    """Reject updates that attempt to change non-draft mutable metadata."""
    job_id = _create_job(client)
    created = client.post(f"/api/jobs/{job_id}/criteria/draft", json={}).json()
    for payload in ({"status": "active"}, {"version_number": 5}, {"confirmed_by": "HR"}):
        response = client.patch(f"/api/jobs/{job_id}/criteria/draft/{created['id']}", json=payload)
        assert response.status_code == 422
        _error_payload(response)
