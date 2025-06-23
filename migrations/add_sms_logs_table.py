"""Add SMS logs table for rate limiting

Revision ID: add_sms_logs_table
Revises: 
Create Date: 2025-06-08
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_sms_logs_table'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create sms_logs table for tracking SMS messages and rate limiting."""
    op.create_table(
        'sms_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('phone_number', sa.String(length=20), nullable=False),
        sa.Column('message_type', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user_auth.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for performance
    op.create_index('idx_sms_logs_user_id', 'sms_logs', ['user_id'])
    op.create_index('idx_sms_logs_created_at', 'sms_logs', ['created_at'])
    op.create_index('idx_sms_logs_status', 'sms_logs', ['status'])


def downgrade() -> None:
    """Drop sms_logs table."""
    op.drop_index('idx_sms_logs_status', table_name='sms_logs')
    op.drop_index('idx_sms_logs_created_at', table_name='sms_logs')
    op.drop_index('idx_sms_logs_user_id', table_name='sms_logs')
    op.drop_table('sms_logs')
