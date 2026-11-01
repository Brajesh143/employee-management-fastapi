"""Add performance management and recruitment workflows.

Revision ID: f28c3d91a604
Revises: a6c8d0e2f415
Create Date: 2026-11-01 11:10:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f28c3d91a604"
down_revision: Union[str, Sequence[str], None] = "a6c8d0e2f415"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "performance_reviews",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("reviewer_id", sa.Integer(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("rating", sa.Float(), nullable=False),
        sa.Column("strengths", sa.Text(), nullable=False),
        sa.Column("areas_to_improve", sa.Text(), nullable=False),
        sa.Column("comments", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.ForeignKeyConstraint(["reviewer_id"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "employee_id",
            "period_start",
            "period_end",
            name="uq_performance_review_employee_period",
        ),
    )
    op.create_index(
        "ix_performance_reviews_employee_id",
        "performance_reviews",
        ["employee_id"],
    )
    op.create_index(
        "ix_performance_reviews_status",
        "performance_reviews",
        ["status"],
    )
    op.create_index("ix_performance_reviews_id", "performance_reviews", ["id"])

    op.create_table(
        "performance_goals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("metric", sa.String(length=100), nullable=False),
        sa.Column("target_value", sa.Float(), nullable=False),
        sa.Column("current_value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=30), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["employees.id"]),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_performance_goals_employee_id",
        "performance_goals",
        ["employee_id"],
    )
    op.create_index(
        "ix_performance_goals_status",
        "performance_goals",
        ["status"],
    )
    op.create_index("ix_performance_goals_id", "performance_goals", ["id"])

    op.create_table(
        "job_openings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=150), nullable=False),
        sa.Column("department", sa.String(length=100), nullable=False),
        sa.Column("location", sa.String(length=150), nullable=False),
        sa.Column("employment_type", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("opened_on", sa.Date(), nullable=False),
        sa.Column("closes_on", sa.Date(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_job_openings_title", "job_openings", ["title"])
    op.create_index("ix_job_openings_status", "job_openings", ["status"])
    op.create_index("ix_job_openings_id", "job_openings", ["id"])

    op.create_table(
        "candidates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_opening_id", sa.Integer(), nullable=False),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("phone", sa.String(length=30), nullable=True),
        sa.Column("resume_url", sa.String(length=500), nullable=True),
        sa.Column("source", sa.String(length=100), nullable=True),
        sa.Column("stage", sa.String(length=30), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("applied_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["job_opening_id"], ["job_openings.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_candidates_job_opening_id", "candidates", ["job_opening_id"])
    op.create_index("ix_candidates_email", "candidates", ["email"])
    op.create_index("ix_candidates_stage", "candidates", ["stage"])
    op.create_index("ix_candidates_id", "candidates", ["id"])

    op.create_table(
        "interviews",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("interviewer_id", sa.Integer(), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("interview_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"]),
        sa.ForeignKeyConstraint(["interviewer_id"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_interviews_candidate_id", "interviews", ["candidate_id"])
    op.create_index("ix_interviews_interviewer_id", "interviews", ["interviewer_id"])
    op.create_index("ix_interviews_scheduled_at", "interviews", ["scheduled_at"])
    op.create_index("ix_interviews_status", "interviews", ["status"])
    op.create_index("ix_interviews_id", "interviews", ["id"])


def downgrade() -> None:
    op.drop_index("ix_interviews_id", table_name="interviews")
    op.drop_index("ix_interviews_status", table_name="interviews")
    op.drop_index("ix_interviews_scheduled_at", table_name="interviews")
    op.drop_index("ix_interviews_interviewer_id", table_name="interviews")
    op.drop_index("ix_interviews_candidate_id", table_name="interviews")
    op.drop_table("interviews")
    op.drop_index("ix_candidates_id", table_name="candidates")
    op.drop_index("ix_candidates_stage", table_name="candidates")
    op.drop_index("ix_candidates_email", table_name="candidates")
    op.drop_index("ix_candidates_job_opening_id", table_name="candidates")
    op.drop_table("candidates")
    op.drop_index("ix_job_openings_id", table_name="job_openings")
    op.drop_index("ix_job_openings_status", table_name="job_openings")
    op.drop_index("ix_job_openings_title", table_name="job_openings")
    op.drop_table("job_openings")
    op.drop_index("ix_performance_goals_id", table_name="performance_goals")
    op.drop_index("ix_performance_goals_status", table_name="performance_goals")
    op.drop_index("ix_performance_goals_employee_id", table_name="performance_goals")
    op.drop_table("performance_goals")
    op.drop_index("ix_performance_reviews_id", table_name="performance_reviews")
    op.drop_index("ix_performance_reviews_status", table_name="performance_reviews")
    op.drop_index(
        "ix_performance_reviews_employee_id",
        table_name="performance_reviews",
    )
    op.drop_table("performance_reviews")
