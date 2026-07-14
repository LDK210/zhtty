"""Create the initial HirePilot application schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-07-14
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all tables, foreign keys, indexes, and unique indexes."""
    job_status = sa.Enum("draft", "ready", "running", "completed", "failed", name="jobstatus")
    resume_status = sa.Enum(
        "uploaded", "extracting", "parsed", "scored", "completed", "failed", name="resumestatus"
    )

    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("jd_text", sa.Text(), nullable=False),
        sa.Column("jd_structured_json", sa.JSON(), nullable=True),
        sa.Column("status", job_status, nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_jobs_id", "jobs", ["id"], unique=False)

    op.create_table(
        "resumes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("status", resume_status, nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_resumes_id", "resumes", ["id"], unique=False)
    op.create_index("ix_resumes_job_id", "resumes", ["job_id"], unique=False)

    op.create_table(
        "candidates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("resume_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("structured_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_candidates_id", "candidates", ["id"], unique=False)
    op.create_index("ix_candidates_resume_id", "candidates", ["resume_id"], unique=True)

    op.create_table(
        "scores",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("total_score", sa.Integer(), nullable=False),
        sa.Column("level", sa.String(length=64), nullable=False),
        sa.Column("score_detail_json", sa.JSON(), nullable=False),
        sa.Column("matched_points_json", sa.JSON(), nullable=False),
        sa.Column("missing_points_json", sa.JSON(), nullable=False),
        sa.Column("interview_questions_json", sa.JSON(), nullable=False),
        sa.Column("invitation_message", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"]),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scores_candidate_id", "scores", ["candidate_id"], unique=True)
    op.create_index("ix_scores_id", "scores", ["id"], unique=False)
    op.create_index("ix_scores_job_id", "scores", ["job_id"], unique=False)

    op.create_table(
        "agent_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("resume_id", sa.Integer(), nullable=True),
        sa.Column("step", sa.String(length=120), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"]),
        sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_logs_id", "agent_logs", ["id"], unique=False)
    op.create_index("ix_agent_logs_job_id", "agent_logs", ["job_id"], unique=False)
    op.create_index("ix_agent_logs_resume_id", "agent_logs", ["resume_id"], unique=False)


def downgrade() -> None:
    """Drop the initial schema in reverse dependency order."""
    op.drop_index("ix_agent_logs_resume_id", table_name="agent_logs")
    op.drop_index("ix_agent_logs_job_id", table_name="agent_logs")
    op.drop_index("ix_agent_logs_id", table_name="agent_logs")
    op.drop_table("agent_logs")

    op.drop_index("ix_scores_job_id", table_name="scores")
    op.drop_index("ix_scores_id", table_name="scores")
    op.drop_index("ix_scores_candidate_id", table_name="scores")
    op.drop_table("scores")

    op.drop_index("ix_candidates_resume_id", table_name="candidates")
    op.drop_index("ix_candidates_id", table_name="candidates")
    op.drop_table("candidates")

    op.drop_index("ix_resumes_job_id", table_name="resumes")
    op.drop_index("ix_resumes_id", table_name="resumes")
    op.drop_table("resumes")

    op.drop_index("ix_jobs_id", table_name="jobs")
    op.drop_table("jobs")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        sa.Enum(name="resumestatus").drop(bind, checkfirst=True)
        sa.Enum(name="jobstatus").drop(bind, checkfirst=True)
