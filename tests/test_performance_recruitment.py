from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import main  # noqa: F401
from auth.dependencies import get_current_user
from database import get_db
from database.database import Base
from models.employee import Employee
from models.permission import Permission
from models.role import Role
from models.role_permission import RolePermission
from routers.performance import router as performance_router
from routers.recruitment import router as recruitment_router


@pytest.fixture
def performance_recruitment_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    permissions_by_role = {
        "Performance Employee": {
            "performance:read",
            "performance:goal:update",
        },
        "Performance Manager": {
            "employee:team:read",
            "performance:read",
            "performance:review",
            "performance:goal:manage",
        },
        "Recruitment Manager": {"recruitment:manage"},
    }

    with Session(engine) as db:
        roles = {
            name: Role(name=name) for name in permissions_by_role
        }
        permission_names = set().union(*permissions_by_role.values())
        permissions = {
            name: Permission(name=name) for name in permission_names
        }
        db.add_all([*roles.values(), *permissions.values()])
        db.flush()
        db.add_all(
            RolePermission(
                role_id=roles[role_name].id,
                permission_id=permissions[permission_name].id,
            )
            for role_name, names in permissions_by_role.items()
            for permission_name in names
        )
        manager = Employee(
            employee_code="MGR-PERF",
            first_name="Parker",
            last_name="Manager",
            email="manager.performance@example.com",
            password_hash="",
            role_id=roles["Performance Manager"].id,
        )
        employee = Employee(
            employee_code="EMP-PERF",
            first_name="Emery",
            last_name="Employee",
            email="employee.performance@example.com",
            password_hash="",
            role_id=roles["Performance Employee"].id,
        )
        recruiter = Employee(
            employee_code="REC-PERF",
            first_name="Reese",
            last_name="Recruiter",
            email="recruiter.performance@example.com",
            password_hash="",
            role_id=roles["Recruitment Manager"].id,
        )
        db.add_all([manager, employee, recruiter])
        db.flush()
        employee.reporting_manager_id = manager.id
        db.commit()
        users = {
            "employee": SimpleNamespace(
                id=employee.id,
                role_id=employee.role_id,
                role=SimpleNamespace(name="Performance Employee"),
                reporting_manager_id=manager.id,
            ),
            "manager": SimpleNamespace(
                id=manager.id,
                role_id=manager.role_id,
                role=SimpleNamespace(name="Performance Manager"),
                reporting_manager_id=None,
            ),
            "recruiter": SimpleNamespace(
                id=recruiter.id,
                role_id=recruiter.role_id,
                role=SimpleNamespace(name="Recruitment Manager"),
                reporting_manager_id=None,
            ),
        }

    users["current"] = users["employee"]
    app = FastAPI()
    app.include_router(performance_router, prefix="/performance")
    app.include_router(recruitment_router, prefix="/recruitment")

    def override_get_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: users["current"]
    with TestClient(app) as client:
        yield client, engine, users
    engine.dispose()


def test_reviews_and_goals_are_scoped_and_progress_is_self_service(
    performance_recruitment_client,
):
    client, _, users = performance_recruitment_client
    users["current"] = users["manager"]
    review_response = client.post(
        "/performance/reviews",
        json={
            "employee_id": users["employee"].id,
            "period_start": "2026-01-01",
            "period_end": "2026-06-30",
            "rating": 4.5,
            "strengths": "Reliable delivery and collaboration",
            "areas_to_improve": "Delegate more work",
            "status": "Draft",
        },
    )
    assert review_response.status_code == 201
    review_id = review_response.json()["id"]

    duplicate_review = client.post(
        "/performance/reviews",
        json={
            "employee_id": users["employee"].id,
            "period_start": "2026-01-01",
            "period_end": "2026-06-30",
            "rating": 4,
            "strengths": "Consistent",
            "areas_to_improve": "Communicate earlier",
        },
    )
    assert duplicate_review.status_code == 409

    unauthorized_review = client.post(
        "/performance/reviews",
        json={
            "employee_id": users["recruiter"].id,
            "period_start": "2026-01-01",
            "period_end": "2026-06-30",
            "rating": 4,
            "strengths": "Consistent",
            "areas_to_improve": "Communicate earlier",
        },
    )
    assert unauthorized_review.status_code == 404

    users["current"] = users["employee"]
    reviews = client.get("/performance/reviews")
    assert reviews.status_code == 200
    assert [item["id"] for item in reviews.json()] == [review_id]

    users["current"] = users["manager"]
    completed_review = client.patch(
        f"/performance/reviews/{review_id}",
        json={"status": "Completed"},
    )
    assert completed_review.status_code == 200
    assert completed_review.json()["status"] == "Completed"
    immutable_review = client.patch(
        f"/performance/reviews/{review_id}",
        json={"comments": "Late change"},
    )
    assert immutable_review.status_code == 409

    goal_response = client.post(
        "/performance/goals",
        json={
            "employee_id": users["employee"].id,
            "title": "Improve customer satisfaction",
            "description": "Raise quarterly survey score.",
            "metric": "Customer satisfaction score",
            "target_value": 90,
            "unit": "points",
            "due_date": "2026-12-31",
        },
    )
    assert goal_response.status_code == 201
    goal_id = goal_response.json()["id"]

    users["current"] = users["employee"]
    goals = client.get("/performance/goals")
    assert goals.status_code == 200
    assert [item["id"] for item in goals.json()] == [goal_id]
    premature_completion = client.patch(
        f"/performance/goals/{goal_id}/progress",
        json={"current_value": 72, "status": "Completed"},
    )
    assert premature_completion.status_code == 422
    progress = client.patch(
        f"/performance/goals/{goal_id}/progress",
        json={"current_value": 72, "status": "In progress"},
    )
    assert progress.status_code == 200
    assert progress.json()["current_value"] == 72


def test_recruitment_openings_candidate_pipeline_and_interview_schedule(
    performance_recruitment_client,
):
    client, _, users = performance_recruitment_client
    forbidden = client.get("/recruitment/openings")
    assert forbidden.status_code == 403

    users["current"] = users["recruiter"]
    opening_response = client.post(
        "/recruitment/openings",
        json={
            "title": "Backend Engineer",
            "department": "Engineering",
            "location": "Remote",
            "employment_type": "Full-time",
            "description": "Build and maintain API services.",
            "opened_on": date.today().isoformat(),
            "closes_on": None,
        },
    )
    assert opening_response.status_code == 201
    opening_id = opening_response.json()["id"]

    candidate_response = client.post(
        "/recruitment/candidates",
        json={
            "job_opening_id": opening_id,
            "full_name": "Casey Candidate",
            "email": "CASEY.CANDIDATE@EXAMPLE.COM",
            "source": "Referral",
        },
    )
    assert candidate_response.status_code == 201
    candidate = candidate_response.json()
    assert candidate["email"] == "casey.candidate@example.com"

    stage_update = client.patch(
        f"/recruitment/candidates/{candidate['id']}",
        json={"stage": "Screening"},
    )
    assert stage_update.status_code == 200
    assert stage_update.json()["stage"] == "Screening"

    interview_response = client.post(
        "/recruitment/interviews",
        json={
            "candidate_id": candidate["id"],
            "interviewer_id": users["employee"].id,
            "scheduled_at": "2026-12-10T10:00:00",
            "duration_minutes": 45,
            "interview_type": "Technical",
        },
    )
    assert interview_response.status_code == 201
    interview_id = interview_response.json()["id"]
    overlapping_interview = client.post(
        "/recruitment/interviews",
        json={
            "candidate_id": candidate["id"],
            "interviewer_id": users["employee"].id,
            "scheduled_at": "2026-12-10T10:30:00",
            "duration_minutes": 30,
            "interview_type": "Follow-up",
        },
    )
    assert overlapping_interview.status_code == 409
    interview_update = client.patch(
        f"/recruitment/interviews/{interview_id}",
        json={"status": "Completed", "notes": "Strong technical discussion."},
    )
    assert interview_update.status_code == 200
    assert interview_update.json()["status"] == "Completed"

    closed_opening = client.patch(
        f"/recruitment/openings/{opening_id}",
        json={"status": "Closed"},
    )
    assert closed_opening.status_code == 200
    closed_candidate = client.post(
        "/recruitment/candidates",
        json={
            "job_opening_id": opening_id,
            "full_name": "Another Candidate",
            "email": "another@example.com",
        },
    )
    assert closed_candidate.status_code == 404
