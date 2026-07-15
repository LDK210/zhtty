"""Add company talent candidates, resume versions, and applications.

Revision ID: 0002_add_talent_candidates_applications
Revises: 0001_initial_schema
Create Date: 2026-07-15
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002_add_talent_candidates_applications"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the talent candidate, resume version, and application tables."""
    op.create_table(
        "talent_candidates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("primary_email", sa.String(length=255), nullable=True),
        sa.Column("primary_phone", sa.String(length=64), nullable=True),
        sa.Column("current_company", sa.String(length=255), nullable=True),
        sa.Column("current_title", sa.String(length=255), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("profile_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_talent_candidates_id", "talent_candidates", ["id"], unique=False)

    op.create_table(
        "resume_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("talent_candidate_id", sa.Integer(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("stored_filename", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("file_hash", sa.String(length=128), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("parsed_profile_json", sa.JSON(), nullable=True),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["talent_candidate_id"], ["talent_candidates.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id",
            "talent_candidate_id",
            name="uq_resume_versions_id_talent_candidate_id",
        ),
        sa.UniqueConstraint(
            "talent_candidate_id",
            "version_number",
            name="uq_resume_versions_talent_candidate_id_version_number",
        ),
    )
    op.create_index("ix_resume_versions_file_hash", "resume_versions", ["file_hash"], unique=False)
    op.create_index(
        "ix_resume_versions_id", "resume_versions", ["id"], unique=False
    )
    op.create_index(
        "ix_resume_versions_talent_candidate_id",
        "resume_versions",
        ["talent_candidate_id"],
        unique=False,
    )

    op.create_table(
        "applications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("talent_candidate_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("resume_version_id", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_detail", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("current_stage", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["resume_version_id", "talent_candidate_id"],
            ["resume_versions.id", "resume_versions.talent_candidate_id"],
            name="fk_applications_resume_version_talent_candidate",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["talent_candidate_id"], ["talent_candidates.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "talent_candidate_id",
            "job_id",
            name="uq_applications_talent_candidate_id_job_id",
        ),
    )
    op.create_index("ix_applications_id", "applications", ["id"], unique=False)
    op.create_index("ix_applications_job_id", "applications", ["job_id"], unique=False)
    op.create_index(
        "ix_applications_resume_version_id", "applications", ["resume_version_id"], unique=False
    )
    op.create_index(
        "ix_applications_talent_candidate_id",
        "applications",
        ["talent_candidate_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop only the tables introduced by this revision."""
    op.drop_index("ix_applications_talent_candidate_id", table_name="applications")
    op.drop_index("ix_applications_resume_version_id", table_name="applications")
    op.drop_index("ix_applications_job_id", table_name="applications")
    op.drop_index("ix_applications_id", table_name="applications")
    op.drop_table("applications")

    op.drop_index("ix_resume_versions_talent_candidate_id", table_name="resume_versions")
    op.drop_index("ix_resume_versions_id", table_name="resume_versions")
    op.drop_index("ix_resume_versions_file_hash", table_name="resume_versions")
    op.drop_table("resume_versions")

    op.drop_index("ix_talent_candidates_id", table_name="talent_candidates")
    op.drop_table("talent_candidates")
