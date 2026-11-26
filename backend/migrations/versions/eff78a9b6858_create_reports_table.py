"""create_reports_table

Revision ID: eff78a9b6858
Revises: 0c9ec998ac61
Create Date: 2026-11-26 17:31:16.371562

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "eff78a9b6858"
down_revision: Union[str, Sequence[str], None] = "0c9ec998ac61"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to add reports table."""
    op.create_table(
        "reports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("dataset_id", sa.UUID(), nullable=False),
        sa.Column("analysis_session_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="ready"),
        sa.Column("schema_version", sa.String(length=20), nullable=False, server_default="1.0.0"),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("document", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["analysis_session_id"], ["analysis_sessions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_reports_analysis_session_id"), "reports", ["analysis_session_id"], unique=False
    )
    op.create_index(op.f("ix_reports_dataset_id"), "reports", ["dataset_id"], unique=False)
    op.create_index(op.f("ix_reports_user_id"), "reports", ["user_id"], unique=False)
    op.create_index(
        "ix_reports_dataset_created", "reports", ["dataset_id", "created_at"], unique=False
    )
    op.create_index(
        "ix_reports_session_created", "reports", ["analysis_session_id", "created_at"], unique=False
    )
    op.create_index("ix_reports_status", "reports", ["status"], unique=False)
    op.create_index("ix_reports_user_updated", "reports", ["user_id", "updated_at"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_reports_user_updated", table_name="reports")
    op.drop_index("ix_reports_status", table_name="reports")
    op.drop_index("ix_reports_session_created", table_name="reports")
    op.drop_index("ix_reports_dataset_created", table_name="reports")
    op.drop_index(op.f("ix_reports_user_id"), table_name="reports")
    op.drop_index(op.f("ix_reports_dataset_id"), table_name="reports")
    op.drop_index(op.f("ix_reports_analysis_session_id"), table_name="reports")
    op.drop_table("reports")
