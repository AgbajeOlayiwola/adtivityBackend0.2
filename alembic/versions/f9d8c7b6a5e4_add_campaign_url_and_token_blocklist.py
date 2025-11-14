"""Add campaign_url to client_companies and create token_blocklist table

Revision ID: f9d8c7b6a5e4
Revises: 087c2df23c2c
Create Date: 2025-11-14 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'f9d8c7b6a5e4'
down_revision = '087c2df23c2c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add campaign_url column to client_companies
    op.add_column(
        'client_companies',
        sa.Column('campaign_url', sa.String(length=2048), nullable=True)
    )

    # Create token_blocklist table
    op.create_table(
        'token_blocklist',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('token', sa.Text(), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('platform_users.id'), nullable=True),
    )
    op.create_index('ix_token_blocklist_token', 'token_blocklist', ['token'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_token_blocklist_token', table_name='token_blocklist')
    op.drop_table('token_blocklist')
    op.drop_column('client_companies', 'campaign_url')

