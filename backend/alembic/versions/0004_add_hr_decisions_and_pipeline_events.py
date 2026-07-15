"""Add HR decision and pipeline event audit history.

Revision ID: 0004_add_hr_decisions_and_pipeline_events
Revises: 0003_add_criteria_and_ai_analysis_versions
Create Date: 2026-07-16
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0004_add_hr_decisions_and_pipeline_events"
down_revision: Union[str, None] = "0003_add_criteria_and_ai_analysis_versions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create immutable HR decision and pipeline event audit tables."""
    op.create_table(
        "hr_decisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("analysis_id", sa.Integer(), nullable=True),
        sa.Column("decision", sa.String(length=64), nullable=False),
        sa.Column("reason_code", sa.String(length=128), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("decided_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["analysis_id"], ["ai_analysis_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hr_decisions_analysis_id", "hr_decisions", ["analysis_id"], unique=False)
    op.create_index("ix_hr_decisions_application_id", "hr_decisions", ["application_id"], unique=False)
    op.create_index("ix_hr_decisions_id", "hr_decisions", ["id"], unique=False)

    op.create_table(
        "pipeline_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("from_stage", sa.String(length=64), nullable=True),
        sa.Column("to_stage", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("actor_type", sa.String(length=64), nullable=False),
        sa.Column("actor_id", sa.String(length=255), nullable=True),
        sa.Column("reason_code", sa.String(length=128), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pipeline_events_application_id", "pipeline_events", ["application_id"], unique=False)
    op.create_index("ix_pipeline_events_id", "pipeline_events", ["id"], unique=False)


def downgrade() -> None:
    """Drop only the tables introduced by this revision."""
    op.drop_index("ix_pipeline_events_id", table_name="pipeline_events")
    op.drop_index("ix_pipeline_events_application_id", table_name="pipeline_events")
    op.drop_table("pipeline_events")

    op.drop_index("ix_hr_decisions_id", table_name="hr_decisions")
    op.drop_index("ix_hr_decisions_application_id", table_name="hr_decisions")
    op.drop_index("ix_hr_decisions_analysis_id", table_name="hr_decisions")
    op.drop_table("hr_decisions")
