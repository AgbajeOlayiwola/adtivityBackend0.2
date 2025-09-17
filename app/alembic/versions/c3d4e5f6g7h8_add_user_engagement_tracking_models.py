"""add_user_engagement_tracking_models

Revision ID: c3d4e5f6g7h8
Revises: b5c6d7e8f901
Create Date: 2024-01-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'c3d4e5f6g7h8'
down_revision = 'b5c6d7e8f901'
branch_labels = None
depends_on = None


def upgrade():
    # Create user_sessions table
    op.create_table('user_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('session_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('session_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_activity', sa.DateTime(timezone=True), nullable=False),
        sa.Column('total_events', sa.Integer(), nullable=True),
        sa.Column('active_time_seconds', sa.Integer(), nullable=True),
        sa.Column('page_views', sa.Integer(), nullable=True),
        sa.Column('unique_pages', sa.Integer(), nullable=True),
        sa.Column('country', sa.String(length=2), nullable=True),
        sa.Column('region', sa.String(length=100), nullable=True),
        sa.Column('city', sa.String(length=100), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(), nullable=True),
        sa.Column('referrer', sa.String(), nullable=True),
        sa.Column('device_type', sa.String(), nullable=True),
        sa.Column('browser', sa.String(), nullable=True),
        sa.Column('os', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['client_companies.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_company_session', 'user_sessions', ['company_id', 'session_id'], unique=False)
    op.create_index('idx_session_timing', 'user_sessions', ['session_start', 'session_end'], unique=False)
    op.create_index('idx_user_activity', 'user_sessions', ['user_id', 'last_activity'], unique=False)
    op.create_index('idx_user_session_company', 'user_sessions', ['company_id', 'user_id'], unique=False)
    op.create_index(op.f('ix_user_sessions_browser'), 'user_sessions', ['browser'], unique=False)
    op.create_index(op.f('ix_user_sessions_city'), 'user_sessions', ['city'], unique=False)
    op.create_index(op.f('ix_user_sessions_company_id'), 'user_sessions', ['company_id'], unique=False)
    op.create_index(op.f('ix_user_sessions_country'), 'user_sessions', ['country'], unique=False)
    op.create_index(op.f('ix_user_sessions_device_type'), 'user_sessions', ['device_type'], unique=False)
    op.create_index(op.f('ix_user_sessions_id'), 'user_sessions', ['id'], unique=False)
    op.create_index(op.f('ix_user_sessions_ip_address'), 'user_sessions', ['ip_address'], unique=False)
    op.create_index(op.f('ix_user_sessions_last_activity'), 'user_sessions', ['last_activity'], unique=False)
    op.create_index(op.f('ix_user_sessions_os'), 'user_sessions', ['os'], unique=False)
    op.create_index(op.f('ix_user_sessions_region'), 'user_sessions', ['region'], unique=False)
    op.create_index(op.f('ix_user_sessions_session_end'), 'user_sessions', ['session_end'], unique=False)
    op.create_index(op.f('ix_user_sessions_session_id'), 'user_sessions', ['session_id'], unique=False)
    op.create_index(op.f('ix_user_sessions_session_start'), 'user_sessions', ['session_start'], unique=False)
    op.create_index(op.f('ix_user_sessions_user_id'), 'user_sessions', ['user_id'], unique=False)

    # Create user_engagement table
    op.create_table('user_engagement',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('event_name', sa.String(), nullable=False),
        sa.Column('event_timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('engagement_duration_seconds', sa.Integer(), nullable=True),
        sa.Column('page_url', sa.String(), nullable=True),
        sa.Column('page_title', sa.String(), nullable=True),
        sa.Column('event_properties', sa.JSON(), nullable=True),
        sa.Column('country', sa.String(length=2), nullable=True),
        sa.Column('region', sa.String(length=100), nullable=True),
        sa.Column('city', sa.String(length=100), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['client_companies.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_engagement_timing', 'user_engagement', ['event_timestamp'], unique=False)
    op.create_index('idx_session_engagement', 'user_engagement', ['session_id', 'event_timestamp'], unique=False)
    op.create_index('idx_user_engagement_company', 'user_engagement', ['company_id', 'user_id'], unique=False)
    op.create_index('idx_user_events', 'user_engagement', ['user_id', 'event_timestamp'], unique=False)
    op.create_index(op.f('ix_user_engagement_city'), 'user_engagement', ['city'], unique=False)
    op.create_index(op.f('ix_user_engagement_company_id'), 'user_engagement', ['company_id'], unique=False)
    op.create_index(op.f('ix_user_engagement_country'), 'user_engagement', ['country'], unique=False)
    op.create_index(op.f('ix_user_engagement_event_name'), 'user_engagement', ['event_name'], unique=False)
    op.create_index(op.f('ix_user_engagement_event_timestamp'), 'user_engagement', ['event_timestamp'], unique=False)
    op.create_index(op.f('ix_user_engagement_id'), 'user_engagement', ['id'], unique=False)
    op.create_index(op.f('ix_user_engagement_ip_address'), 'user_engagement', ['ip_address'], unique=False)
    op.create_index(op.f('ix_user_engagement_region'), 'user_engagement', ['region'], unique=False)
    op.create_index(op.f('ix_user_engagement_session_id'), 'user_engagement', ['session_id'], unique=False)
    op.create_index(op.f('ix_user_engagement_user_id'), 'user_engagement', ['user_id'], unique=False)

    # Create user_activity_summary table
    op.create_table('user_activity_summary',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('summary_date', sa.Date(), nullable=False),
        sa.Column('hour', sa.Integer(), nullable=True),
        sa.Column('total_active_users', sa.Integer(), nullable=True),
        sa.Column('total_new_users', sa.Integer(), nullable=True),
        sa.Column('total_returning_users', sa.Integer(), nullable=True),
        sa.Column('total_sessions', sa.Integer(), nullable=True),
        sa.Column('total_engagement_time_seconds', sa.Integer(), nullable=True),
        sa.Column('avg_engagement_time_per_user', sa.Float(), nullable=True),
        sa.Column('avg_engagement_time_per_session', sa.Float(), nullable=True),
        sa.Column('total_events', sa.Integer(), nullable=True),
        sa.Column('total_page_views', sa.Integer(), nullable=True),
        sa.Column('unique_pages_viewed', sa.Integer(), nullable=True),
        sa.Column('country_breakdown', sa.JSON(), nullable=True),
        sa.Column('region_breakdown', sa.JSON(), nullable=True),
        sa.Column('city_breakdown', sa.JSON(), nullable=True),
        sa.Column('device_breakdown', sa.JSON(), nullable=True),
        sa.Column('browser_breakdown', sa.JSON(), nullable=True),
        sa.Column('operating_system_breakdown', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['client_companies.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'summary_date', 'hour', name='unique_company_date_hour')
    )
    op.create_index('idx_activity_company_date', 'user_activity_summary', ['company_id', 'summary_date'], unique=False)
    op.create_index('idx_activity_date', 'user_activity_summary', ['summary_date'], unique=False)
    op.create_index(op.f('ix_user_activity_summary_company_id'), 'user_activity_summary', ['company_id'], unique=False)
    op.create_index(op.f('ix_user_activity_summary_date'), 'user_activity_summary', ['summary_date'], unique=False)
    op.create_index(op.f('ix_user_activity_summary_hour'), 'user_activity_summary', ['hour'], unique=False)
    op.create_index(op.f('ix_user_activity_summary_id'), 'user_activity_summary', ['id'], unique=False)


def downgrade():
    # Drop user_activity_summary table
    op.drop_index(op.f('ix_user_activity_summary_id'), table_name='user_activity_summary')
    op.drop_index(op.f('ix_user_activity_summary_hour'), table_name='user_activity_summary')
    op.drop_index(op.f('ix_user_activity_summary_date'), table_name='user_activity_summary')
    op.drop_index(op.f('ix_user_activity_summary_company_id'), table_name='user_activity_summary')
    op.drop_index('idx_activity_date', table_name='user_activity_summary')
    op.drop_index('idx_activity_company_date', table_name='user_activity_summary')
    op.drop_table('user_activity_summary')

    # Drop user_engagement table
    op.drop_index(op.f('ix_user_engagement_user_id'), table_name='user_engagement')
    op.drop_index(op.f('ix_user_engagement_session_id'), table_name='user_engagement')
    op.drop_index(op.f('ix_user_engagement_region'), table_name='user_engagement')
    op.drop_index(op.f('ix_user_engagement_ip_address'), table_name='user_engagement')
    op.drop_index(op.f('ix_user_engagement_id'), table_name='user_engagement')
    op.drop_index(op.f('ix_user_engagement_event_timestamp'), table_name='user_engagement')
    op.drop_index(op.f('ix_user_engagement_event_name'), table_name='user_engagement')
    op.drop_index(op.f('ix_user_engagement_country'), table_name='user_engagement')
    op.drop_index(op.f('ix_user_engagement_company_id'), table_name='user_engagement')
    op.drop_index(op.f('ix_user_engagement_city'), table_name='user_engagement')
    op.drop_index('idx_user_events', table_name='user_engagement')
    op.drop_index('idx_user_engagement_company', table_name='user_engagement')
    op.drop_index('idx_session_engagement', table_name='user_engagement')
    op.drop_index('idx_engagement_timing', table_name='user_engagement')
    op.drop_table('user_engagement')

    # Drop user_sessions table
    op.drop_index(op.f('ix_user_sessions_user_id'), table_name='user_sessions')
    op.drop_index(op.f('ix_user_sessions_session_start'), table_name='user_sessions')
    op.drop_index(op.f('ix_user_sessions_session_id'), table_name='user_sessions')
    op.drop_index(op.f('ix_user_sessions_session_end'), table_name='user_sessions')
    op.drop_index(op.f('ix_user_sessions_region'), table_name='user_sessions')
    op.drop_index(op.f('ix_user_sessions_os'), table_name='user_sessions')
    op.drop_index(op.f('ix_user_sessions_last_activity'), table_name='user_sessions')
    op.drop_index(op.f('ix_user_sessions_ip_address'), table_name='user_sessions')
    op.drop_index(op.f('ix_user_sessions_id'), table_name='user_sessions')
    op.drop_index(op.f('ix_user_sessions_device_type'), table_name='user_sessions')
    op.drop_index(op.f('ix_user_sessions_country'), table_name='user_sessions')
    op.drop_index(op.f('ix_user_sessions_company_id'), table_name='user_sessions')
    op.drop_index(op.f('ix_user_sessions_city'), table_name='user_sessions')
    op.drop_index(op.f('ix_user_sessions_browser'), table_name='user_sessions')
    op.drop_index('idx_user_session_company', table_name='user_sessions')
    op.drop_index('idx_user_activity', table_name='user_sessions')
    op.drop_index('idx_session_timing', table_name='user_sessions')
    op.drop_index('idx_company_session', table_name='user_sessions')
    op.drop_table('user_sessions')
