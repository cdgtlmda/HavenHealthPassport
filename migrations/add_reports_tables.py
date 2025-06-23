"""Add reports and scheduled reports tables

Revision ID: add_reports_tables
Revises: 
Create Date: 2025-06-07 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_reports_tables'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create report status enum
    op.execute("CREATE TYPE reportstatus AS ENUM ('pending', 'processing', 'completed', 'failed', 'cancelled')")
    
    # Create report type enum
    op.execute("""
        CREATE TYPE reporttype AS ENUM (
            'patient_summary', 'health_trends', 'compliance_hipaa', 
            'compliance_audit', 'access_logs', 'usage_analytics',
            'demographic_analysis', 'resource_utilization', 'custom'
        )
    """)
    
    # Create report format enum
    op.execute("CREATE TYPE reportformat AS ENUM ('pdf', 'excel', 'csv', 'json')")
    
    # Create reports table
    op.create_table('reports',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('type', postgresql.ENUM('patient_summary', 'health_trends', 'compliance_hipaa', 
                                         'compliance_audit', 'access_logs', 'usage_analytics',
                                         'demographic_analysis', 'resource_utilization', 'custom',
                                         name='reporttype'), nullable=False),
        sa.Column('format', postgresql.ENUM('pdf', 'excel', 'csv', 'json', name='reportformat'), nullable=False),
        sa.Column('status', postgresql.ENUM('pending', 'processing', 'completed', 'failed', 'cancelled',
                                           name='reportstatus'), nullable=True),
        sa.Column('config', sa.JSON(), nullable=False),
        sa.Column('file_path', sa.String(length=500), nullable=True),
        sa.Column('file_size', sa.Float(), nullable=True),
        sa.Column('download_url', sa.String(length=500), nullable=True),
        sa.Column('created_by', sa.String(length=50), nullable=False),
        sa.Column('organization_id', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create scheduled_reports table
    op.create_table('scheduled_reports',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('type', postgresql.ENUM('patient_summary', 'health_trends', 'compliance_hipaa', 
                                         'compliance_audit', 'access_logs', 'usage_analytics',
                                         'demographic_analysis', 'resource_utilization', 'custom',
                                         name='reporttype'), nullable=False),
        sa.Column('format', postgresql.ENUM('pdf', 'excel', 'csv', 'json', name='reportformat'), nullable=False),
        sa.Column('schedule', sa.String(length=100), nullable=False),
        sa.Column('timezone', sa.String(length=50), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=True),
        sa.Column('config', sa.JSON(), nullable=False),
        sa.Column('recipients', sa.JSON(), nullable=True),
        sa.Column('delivery_method', sa.String(length=50), nullable=True),
        sa.Column('created_by', sa.String(length=50), nullable=False),
        sa.Column('organization_id', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('run_count', sa.Integer(), nullable=True),
        sa.Column('success_count', sa.Integer(), nullable=True),
        sa.Column('failure_count', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('idx_reports_created_by', 'reports', ['created_by'], unique=False)
    op.create_index('idx_reports_organization', 'reports', ['organization_id'], unique=False)
    op.create_index('idx_reports_status', 'reports', ['status'], unique=False)
    op.create_index('idx_reports_type', 'reports', ['type'], unique=False)
    op.create_index('idx_reports_created_at', 'reports', ['created_at'], unique=False)
    
    op.create_index('idx_scheduled_reports_enabled', 'scheduled_reports', ['enabled'], unique=False)
    op.create_index('idx_scheduled_reports_next_run', 'scheduled_reports', ['next_run_at'], unique=False)
    op.create_index('idx_scheduled_reports_organization', 'scheduled_reports', ['organization_id'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_scheduled_reports_organization', table_name='scheduled_reports')
    op.drop_index('idx_scheduled_reports_next_run', table_name='scheduled_reports')
    op.drop_index('idx_scheduled_reports_enabled', table_name='scheduled_reports')
    
    op.drop_index('idx_reports_created_at', table_name='reports')
    op.drop_index('idx_reports_type', table_name='reports')
    op.drop_index('idx_reports_status', table_name='reports')
    op.drop_index('idx_reports_organization', table_name='reports')
    op.drop_index('idx_reports_created_by', table_name='reports')
    
    # Drop tables
    op.drop_table('scheduled_reports')
    op.drop_table('reports')
    
    # Drop enums
    op.execute('DROP TYPE reportformat')
    op.execute('DROP TYPE reporttype')
    op.execute('DROP TYPE reportstatus')
