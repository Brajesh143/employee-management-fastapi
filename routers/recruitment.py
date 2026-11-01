from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from auth.permissions import require_permission
from database import get_db
from models.candidate import Candidate
from models.employee import Employee
from models.interview import Interview
from models.job_opening import JobOpening
from schemas.recruitment import (
    CandidateCreate,
    CandidateResponse,
    CandidateUpdate,
    InterviewCreate,
    InterviewResponse,
    InterviewUpdate,
    JobOpeningCreate,
    JobOpeningResponse,
    JobOpeningUpdate,
)
from services.audit import write_audit_log

router = APIRouter()


def _snapshot(record: JobOpening | Candidate | Interview) -> dict[str, object]:
    if isinstance(record, JobOpening):
        return {
            "id": record.id,
            "title": record.title,
            "department": record.department,
            "status": record.status,
        }
    if isinstance(record, Candidate):
        return {
            "id": record.id,
            "job_opening_id": record.job_opening_id,
            "full_name": record.full_name,
            "email": record.email,
            "stage": record.stage,
        }
    return {
        "id": record.id,
        "candidate_id": record.candidate_id,
        "interviewer_id": record.interviewer_id,
        "scheduled_at": record.scheduled_at,
        "status": record.status,
    }


def _log_change(
    db: Session,
    actor_id: int,
    action: str,
    resource_type: str,
    record: JobOpening | Candidate | Interview,
    before: dict[str, object] | None = None,
) -> None:
    write_audit_log(
        db,
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=record.id,
        before=before,
        after=_snapshot(record),
    )
    db.commit()
    db.refresh(record)


def _interviewer_has_conflict(
    db: Session,
    *,
    interviewer_id: int,
    scheduled_at: datetime,
    duration_minutes: int,
    exclude_interview_id: int | None = None,
) -> bool:
    interview_end = scheduled_at + timedelta(minutes=duration_minutes)
    earliest_possible_start = scheduled_at - timedelta(minutes=480)
    query = db.query(Interview).filter(
        Interview.interviewer_id == interviewer_id,
        Interview.status == "Scheduled",
        Interview.scheduled_at >= earliest_possible_start,
        Interview.scheduled_at < interview_end,
    )
    if exclude_interview_id is not None:
        query = query.filter(Interview.id != exclude_interview_id)
    return any(
        item.scheduled_at + timedelta(minutes=item.duration_minutes) > scheduled_at
        for item in query.all()
    )


@router.post(
    "/openings",
    response_model=JobOpeningResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_opening(
    payload: JobOpeningCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission("recruitment:manage")),
):
    opening = JobOpening(**payload.model_dump(), created_by=current_user.id)
    db.add(opening)
    db.flush()
    _log_change(
        db,
        current_user.id,
        "recruitment.opening.create",
        "job_opening",
        opening,
    )
    return opening


@router.get(
    "/openings",
    response_model=list[JobOpeningResponse],
    dependencies=[Depends(require_permission("recruitment:manage"))],
)
def list_openings(
    opening_status: str | None = Query(
        default=None,
        alias="status",
        pattern="^(Open|On hold|Closed)$",
    ),
    db: Session = Depends(get_db),
):
    query = db.query(JobOpening)
    if opening_status:
        query = query.filter(JobOpening.status == opening_status)
    return query.order_by(JobOpening.created_at.desc(), JobOpening.id.desc()).all()


@router.patch(
    "/openings/{opening_id}",
    response_model=JobOpeningResponse,
)
def update_opening(
    opening_id: int,
    payload: JobOpeningUpdate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission("recruitment:manage")),
):
    opening = db.query(JobOpening).filter(JobOpening.id == opening_id).first()
    if opening is None:
        raise HTTPException(status_code=404, detail="Job opening not found.")
    values = payload.model_dump(exclude_unset=True)
    new_opened_on = values.get("opened_on", opening.opened_on)
    new_closes_on = values.get("closes_on", opening.closes_on)
    if new_closes_on is not None and new_closes_on < new_opened_on:
        raise HTTPException(
            status_code=422,
            detail="Closing date cannot be before opening date.",
        )
    before = _snapshot(opening)
    for field, value in values.items():
        setattr(opening, field, value)
    _log_change(
        db,
        current_user.id,
        "recruitment.opening.update",
        "job_opening",
        opening,
        before,
    )
    return opening


@router.post(
    "/candidates",
    response_model=CandidateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_candidate(
    payload: CandidateCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission("recruitment:manage")),
):
    opening = (
        db.query(JobOpening)
        .filter(JobOpening.id == payload.job_opening_id)
        .first()
    )
    if opening is None or opening.status != "Open":
        raise HTTPException(
            status_code=404,
            detail="Open job opening not found.",
        )
    candidate = Candidate(**payload.model_dump())
    db.add(candidate)
    db.flush()
    _log_change(
        db,
        current_user.id,
        "recruitment.candidate.create",
        "candidate",
        candidate,
    )
    return candidate


@router.get(
    "/candidates",
    response_model=list[CandidateResponse],
    dependencies=[Depends(require_permission("recruitment:manage"))],
)
def list_candidates(
    job_opening_id: int | None = Query(default=None, ge=1),
    stage: str | None = Query(
        default=None,
        pattern="^(Applied|Screening|Interview|Offer|Hired|Rejected|Withdrawn)$",
    ),
    db: Session = Depends(get_db),
):
    query = db.query(Candidate)
    if job_opening_id is not None:
        query = query.filter(Candidate.job_opening_id == job_opening_id)
    if stage is not None:
        query = query.filter(Candidate.stage == stage)
    return query.order_by(Candidate.applied_at.desc(), Candidate.id.desc()).all()


@router.patch(
    "/candidates/{candidate_id}",
    response_model=CandidateResponse,
)
def update_candidate(
    candidate_id: int,
    payload: CandidateUpdate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission("recruitment:manage")),
):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    before = _snapshot(candidate)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(candidate, field, value)
    _log_change(
        db,
        current_user.id,
        "recruitment.candidate.update",
        "candidate",
        candidate,
        before,
    )
    return candidate


@router.post(
    "/interviews",
    response_model=InterviewResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_interview(
    payload: InterviewCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission("recruitment:manage")),
):
    candidate = db.query(Candidate).filter(
        Candidate.id == payload.candidate_id
    ).first()
    interviewer = db.query(Employee).filter(
        Employee.id == payload.interviewer_id,
        Employee.is_active.is_(True),
    ).first()
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    if interviewer is None:
        raise HTTPException(status_code=404, detail="Active interviewer not found.")
    if _interviewer_has_conflict(
        db,
        interviewer_id=payload.interviewer_id,
        scheduled_at=payload.scheduled_at,
        duration_minutes=payload.duration_minutes,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The interviewer already has an interview scheduled during this time.",
        )
    interview = Interview(**payload.model_dump())
    db.add(interview)
    db.flush()
    _log_change(
        db,
        current_user.id,
        "recruitment.interview.schedule",
        "interview",
        interview,
    )
    return interview


@router.get(
    "/interviews",
    response_model=list[InterviewResponse],
    dependencies=[Depends(require_permission("recruitment:manage"))],
)
def list_interviews(
    candidate_id: int | None = Query(default=None, ge=1),
    interviewer_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
):
    query = db.query(Interview)
    if candidate_id is not None:
        query = query.filter(Interview.candidate_id == candidate_id)
    if interviewer_id is not None:
        query = query.filter(Interview.interviewer_id == interviewer_id)
    return query.order_by(Interview.scheduled_at, Interview.id).all()


@router.patch(
    "/interviews/{interview_id}",
    response_model=InterviewResponse,
)
def update_interview(
    interview_id: int,
    payload: InterviewUpdate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission("recruitment:manage")),
):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if interview is None:
        raise HTTPException(status_code=404, detail="Interview not found.")
    values = payload.model_dump(exclude_unset=True)
    interviewer_id = values.get("interviewer_id", interview.interviewer_id)
    if "interviewer_id" in values and values["interviewer_id"] is not None:
        interviewer = db.query(Employee.id).filter(
            Employee.id == interviewer_id,
            Employee.is_active.is_(True),
        ).first()
        if interviewer is None:
            raise HTTPException(
                status_code=404,
                detail="Active interviewer not found.",
            )
    scheduled_at = values.get("scheduled_at", interview.scheduled_at)
    duration_minutes = values.get("duration_minutes", interview.duration_minutes)
    interview_status = values.get("status", interview.status)
    if interview_status == "Scheduled" and _interviewer_has_conflict(
        db,
        interviewer_id=interviewer_id,
        scheduled_at=scheduled_at,
        duration_minutes=duration_minutes,
        exclude_interview_id=interview.id,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The interviewer already has an interview scheduled during this time.",
        )
    before = _snapshot(interview)
    for field, value in values.items():
        setattr(interview, field, value)
    _log_change(
        db,
        current_user.id,
        "recruitment.interview.update",
        "interview",
        interview,
        before,
    )
    return interview
