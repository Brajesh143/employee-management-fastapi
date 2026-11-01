from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth.permissions import (
    can_access_employee,
    employee_scope_query,
    has_permission,
    require_any_permission,
    require_permission,
)
from database import get_db
from models.employee import Employee
from models.performance_goal import PerformanceGoal
from models.performance_review import PerformanceReview
from schemas.performance import (
    PerformanceGoalCreate,
    PerformanceGoalProgress,
    PerformanceGoalResponse,
    PerformanceReviewCreate,
    PerformanceReviewResponse,
    PerformanceReviewUpdate,
)
from services.audit import write_audit_log

router = APIRouter()


def _review_snapshot(review: PerformanceReview) -> dict[str, object]:
    return {
        "id": review.id,
        "employee_id": review.employee_id,
        "reviewer_id": review.reviewer_id,
        "period_start": review.period_start,
        "period_end": review.period_end,
        "rating": review.rating,
        "status": review.status,
    }


def _goal_snapshot(goal: PerformanceGoal) -> dict[str, object]:
    return {
        "id": goal.id,
        "employee_id": goal.employee_id,
        "title": goal.title,
        "metric": goal.metric,
        "target_value": goal.target_value,
        "current_value": goal.current_value,
        "status": goal.status,
    }


@router.post(
    "/reviews",
    response_model=PerformanceReviewResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_review(
    payload: PerformanceReviewCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission("performance:review")),
):
    if payload.employee_id == current_user.id or not can_access_employee(
        db, current_user, payload.employee_id
    ):
        raise HTTPException(status_code=404, detail="Employee not found.")
    if db.query(Employee.id).filter(Employee.id == payload.employee_id).first() is None:
        raise HTTPException(status_code=404, detail="Employee not found.")
    review = PerformanceReview(
        **payload.model_dump(),
        reviewer_id=current_user.id,
    )
    db.add(review)
    try:
        db.flush()
        write_audit_log(
            db,
            actor_id=current_user.id,
            action="performance.review.create",
            resource_type="performance_review",
            resource_id=review.id,
            after=_review_snapshot(review),
        )
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A review already exists for this employee and period.",
        ) from error
    db.refresh(review)
    return review


@router.get(
    "/reviews",
    response_model=list[PerformanceReviewResponse],
    dependencies=[
        Depends(require_any_permission("performance:read", "performance:review"))
    ],
)
def list_reviews(
    employee_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(
        require_any_permission("performance:read", "performance:review")
    ),
):
    query = employee_scope_query(
        db,
        current_user,
        db.query(PerformanceReview),
        PerformanceReview.employee_id,
    )
    if employee_id is not None:
        if not can_access_employee(db, current_user, employee_id):
            raise HTTPException(status_code=404, detail="Performance reviews not found.")
        query = query.filter(PerformanceReview.employee_id == employee_id)
    return query.order_by(
        PerformanceReview.period_end.desc(),
        PerformanceReview.id.desc(),
    ).all()


@router.patch(
    "/reviews/{review_id}",
    response_model=PerformanceReviewResponse,
)
def update_review(
    review_id: int,
    payload: PerformanceReviewUpdate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission("performance:review")),
):
    review = db.query(PerformanceReview).filter(
        PerformanceReview.id == review_id
    ).first()
    if review is None or review.reviewer_id != current_user.id:
        raise HTTPException(status_code=404, detail="Performance review not found.")
    if review.status == "Completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Completed performance reviews cannot be changed.",
        )
    before = _review_snapshot(review)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None or field == "comments":
            setattr(review, field, value)
    write_audit_log(
        db,
        actor_id=current_user.id,
        action="performance.review.update",
        resource_type="performance_review",
        resource_id=review.id,
        before=before,
        after=_review_snapshot(review),
    )
    db.commit()
    db.refresh(review)
    return review


@router.post(
    "/goals",
    response_model=PerformanceGoalResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_goal(
    payload: PerformanceGoalCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(
        require_permission("performance:goal:manage")
    ),
):
    if not can_access_employee(db, current_user, payload.employee_id):
        raise HTTPException(status_code=404, detail="Employee not found.")
    employee = db.query(Employee).filter(Employee.id == payload.employee_id).first()
    if employee is None or not employee.is_active:
        raise HTTPException(status_code=404, detail="Active employee not found.")
    goal = PerformanceGoal(
        **payload.model_dump(),
        created_by=current_user.id,
        status="Not started",
    )
    db.add(goal)
    db.flush()
    write_audit_log(
        db,
        actor_id=current_user.id,
        action="performance.goal.create",
        resource_type="performance_goal",
        resource_id=goal.id,
        after=_goal_snapshot(goal),
    )
    db.commit()
    db.refresh(goal)
    return goal


@router.get(
    "/goals",
    response_model=list[PerformanceGoalResponse],
    dependencies=[
        Depends(require_any_permission("performance:read", "performance:goal:manage"))
    ],
)
def list_goals(
    employee_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(
        require_any_permission("performance:read", "performance:goal:manage")
    ),
):
    query = employee_scope_query(
        db,
        current_user,
        db.query(PerformanceGoal),
        PerformanceGoal.employee_id,
    )
    if employee_id is not None:
        if not can_access_employee(db, current_user, employee_id):
            raise HTTPException(status_code=404, detail="Performance goals not found.")
        query = query.filter(PerformanceGoal.employee_id == employee_id)
    return query.order_by(
        PerformanceGoal.due_date,
        PerformanceGoal.id.desc(),
    ).all()


@router.patch(
    "/goals/{goal_id}/progress",
    response_model=PerformanceGoalResponse,
)
def update_goal_progress(
    goal_id: int,
    payload: PerformanceGoalProgress,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(
        require_any_permission(
            "performance:goal:update",
            "performance:goal:manage",
        )
    ),
):
    goal = db.query(PerformanceGoal).filter(PerformanceGoal.id == goal_id).first()
    if goal is None:
        raise HTTPException(status_code=404, detail="Performance goal not found.")
    can_manage_team_goal = (
        has_permission(db, current_user, "performance:goal:manage")
        and can_access_employee(db, current_user, goal.employee_id)
    )
    if (
        goal.employee_id != current_user.id
        and not can_manage_team_goal
    ):
        raise HTTPException(status_code=404, detail="Performance goal not found.")
    if payload.status == "Completed" and payload.current_value < goal.target_value:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A goal cannot be completed before its KPI target is reached.",
        )
    before = _goal_snapshot(goal)
    goal.current_value = payload.current_value
    goal.status = payload.status
    write_audit_log(
        db,
        actor_id=current_user.id,
        action="performance.goal.progress",
        resource_type="performance_goal",
        resource_id=goal.id,
        before=before,
        after=_goal_snapshot(goal),
    )
    db.commit()
    db.refresh(goal)
    return goal
