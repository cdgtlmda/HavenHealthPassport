"""Migration to create patient-provider and patient-organization association tables.

This migration creates the necessary tables for managing access control relationships
between patients, providers, and organizations in the Haven Health Passport system.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# Revision identifiers
revision = 'add_access_control_associations'
down_revision = None  # Update this with the previous migration revision
branch_labels = None
depends_on = None


def upgrade():
    """Create association tables for access control."""
    
    # Create patient_provider_association table
    op.create_table(
        'patient_provider_association',
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('provider_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('relationship_type', sa.String(50), nullable=False, server_default='primary_care'),
        sa.Column('consent_given', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('consent_scope', sa.Text()),
        sa.Column('valid_from', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('valid_until', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('created_by', postgresql.UUID(as_uuid=True)),
        sa.Column('notes', sa.Text()),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['provider_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('patient_id', 'provider_id')
    )    
    # Create indexes for patient_provider_association
    op.create_index(
        'idx_patient_provider_patient',
        'patient_provider_association',
        ['patient_id']
    )
    op.create_index(
        'idx_patient_provider_provider',
        'patient_provider_association',
        ['provider_id']
    )
    op.create_index(
        'idx_patient_provider_valid',
        'patient_provider_association',
        ['consent_given', 'valid_until']
    )
    
    # Create patient_organization_association table
    op.create_table(
        'patient_organization_association',
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('relationship_type', sa.String(50), nullable=False, server_default='care_provider'),
        sa.Column('consent_given', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('consent_scope', sa.Text()),
        sa.Column('valid_from', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('valid_until', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('created_by', postgresql.UUID(as_uuid=True)),
        sa.Column('notes', sa.Text()),
        sa.Column('camp_location', sa.String(200)),
        sa.Column('program_enrollment', sa.Text()),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('patient_id', 'organization_id')
    )    
    # Create indexes for patient_organization_association
    op.create_index(
        'idx_patient_org_patient',
        'patient_organization_association',
        ['patient_id']
    )
    op.create_index(
        'idx_patient_org_organization',
        'patient_organization_association',
        ['organization_id']
    )
    op.create_index(
        'idx_patient_org_camp',
        'patient_organization_association',
        ['camp_location']
    )
    op.create_index(
        'idx_patient_org_valid',
        'patient_organization_association',
        ['consent_given', 'valid_until']
    )
    
    # Create provider_organization_association table
    op.create_table(
        'provider_organization_association',
        sa.Column('provider_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role', sa.String(100), nullable=False, server_default='healthcare_provider'),
        sa.Column('department', sa.String(200)),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('start_date', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('end_date', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['provider_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('provider_id', 'organization_id')
    )    
    # Create indexes for provider_organization_association
    op.create_index(
        'idx_provider_org_provider',
        'provider_organization_association',
        ['provider_id']
    )
    op.create_index(
        'idx_provider_org_organization',
        'provider_organization_association',
        ['organization_id']
    )
    op.create_index(
        'idx_provider_org_active',
        'provider_organization_association',
        ['active', 'end_date']
    )


def downgrade():
    """Drop association tables."""
    # Drop indexes first
    op.drop_index('idx_provider_org_active', table_name='provider_organization_association')
    op.drop_index('idx_provider_org_organization', table_name='provider_organization_association')
    op.drop_index('idx_provider_org_provider', table_name='provider_organization_association')
    
    op.drop_index('idx_patient_org_valid', table_name='patient_organization_association')
    op.drop_index('idx_patient_org_camp', table_name='patient_organization_association')
    op.drop_index('idx_patient_org_organization', table_name='patient_organization_association')
    op.drop_index('idx_patient_org_patient', table_name='patient_organization_association')
    
    op.drop_index('idx_patient_provider_valid', table_name='patient_provider_association')
    op.drop_index('idx_patient_provider_provider', table_name='patient_provider_association')
    op.drop_index('idx_patient_provider_patient', table_name='patient_provider_association')
    
    # Drop tables
    op.drop_table('provider_organization_association')
    op.drop_table('patient_organization_association')
    op.drop_table('patient_provider_association')
