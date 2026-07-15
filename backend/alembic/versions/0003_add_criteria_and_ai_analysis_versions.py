"""Add hiring criteria and AI analysis version history.

Revision ID: 0003_add_criteria_and_ai_analysis_versions
Revises: 0002_add_talent_candidates_applications
Create Date: 2026-07-16
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0003_add_criteria_and_ai_analysis_versions"
down_revision: Union[str, None] = "0002_add_talent_candidates_applications"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create job criteria and application analysis version tables."""
    op.create_table(
        "hiring_criteria_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source_jd_text", sa.Text(), nullable=False),
        sa.Column("criteria_json", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("confirmed_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("activated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "job_id",
            "version_number",
            name="uq_hiring_criteria_versions_job_id_version_number",
        ),
    )
    op.create_index("ix_hiring_criteria_versions_id", "hiring_criteria_versions", ["id"], unique=False)
    op.create_index(
        "ix_hiring_criteria_versions_job_id", "hiring_criteria_versions", ["job_id"], unique=False
    )

    op.create_table(
        "ai_analysis_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("criteria_version_id", sa.Integer(), nullable=False),
        sa.Column("resume_version_id", sa.Integer(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("analysis_stage", sa.String(length=64), nullable=False),
        sa.Column("recommendation_pool", sa.String(length=64), nullable=False),
        sa.Column("job_match_score", sa.Float(), nullable=True),
        sa.Column("capability_evidence_score", sa.Float(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("model_provider", sa.String(length=128), nullable=True),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("model_version", sa.String(length=128), nullable=True),
        sa.Column("prompt_version", sa.String(length=128), nullable=True),
        sa.Column("analysis_schema_version", sa.String(length=128), nullable=True),
        sa.Column("analysis_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["criteria_version_id"], ["hiring_criteria_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["resume_version_id"], ["resume_versions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "application_id",
            "version_number",
            name="uq_ai_analysis_versions_application_id_version_number",
        ),
    )
    op.create_index("ix_ai_analysis_versions_application_id", "ai_analysis_versions", ["application_id"], unique=False)
    op.create_index(
        "ix_ai_analysis_versions_criteria_version_id",
        "ai_analysis_versions",
        ["criteria_version_id"],
        unique=False,
    )
    op.create_index("ix_ai_analysis_versions_id", "ai_analysis_versions", ["id"], unique=False)
    op.create_index(
        "ix_ai_analysis_versions_resume_version_id",
        "ai_analysis_versions",
        ["resume_version_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop only the tables introduced by this revision."""
    op.drop_index("ix_ai_analysis_versions_resume_version_id", table_name="ai_analysis_versions")
    op.drop_index("ix_ai_analysis_versions_id", table_name="ai_analysis_versions")
    op.drop_index("ix_ai_analysis_versions_criteria_version_id", table_name="ai_analysis_versions")
    op.drop_index("ix_ai_analysis_versions_application_id", table_name="ai_analysis_versions")
    op.drop_table("ai_analysis_versions")

    op.drop_index("ix_hiring_criteria_versions_job_id", table_name="hiring_criteria_versions")
    op.drop_index("ix_hiring_criteria_versions_id", table_name="hiring_criteria_versions")
    op.drop_table("hiring_criteria_versions")
