"""add team membership and activity log tables

Revision ID: 20251130_add_team_models
Revises: f9d8c7b6a5e4
Create Date: 2025-11-30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers, used by Alembic.
revision = "20251130_add_team_models"
down_revision = "f9d8c7b6a5e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "team_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, index=True, default=uuid.uuid4),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("client_companies.id"), nullable=False, index=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("platform_users.id"), nullable=True, index=True),
        sa.Column("email", sa.String(), nullable=False, index=True),
        sa.Column("role", sa.String(), nullable=False, server_default="owner"),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("invite_token", sa.String(), nullable=True, unique=True, index=True),
        sa.Column("invited_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("platform_users.id"), nullable=True, index=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("company_id", "email", name="uq_team_membership_company_email"),
    )

    op.create_table(
        "team_activity_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, index=True, default=uuid.uuid4),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("client_companies.id"), nullable=False, index=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("platform_users.id"), nullable=True, index=True),
        sa.Column("action_type", sa.String(), nullable=False, index=True),
        sa.Column("target_type", sa.String(), nullable=True, index=True),
        sa.Column("target_id", sa.String(), nullable=True, index=True),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("team_activity_logs")
    op.drop_table("team_memberships")

