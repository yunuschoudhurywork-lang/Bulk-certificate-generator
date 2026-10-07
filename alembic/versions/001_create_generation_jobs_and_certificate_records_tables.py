"""create generation_jobs and certificate_records tables

Revision ID: 001
Revises: 
Create Date: 2024-01-15 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Enable UUID extension for PostgreSQL
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    
    # Create generation_jobs table
    op.create_table(
        'generation_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False, comment='Unique job identifier'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='PENDING', comment='Current job status'),
        sa.Column('total_recipients', sa.Integer(), nullable=False, comment='Total number of recipients in this job'),
        sa.Column('completed_count', sa.Integer(), nullable=False, server_default=sa.text('0'), comment='Number of successfully generated certificates'),
        sa.Column('failed_count', sa.Integer(), nullable=False, server_default=sa.text('0'), comment='Number of failed certificate generations'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False, comment='When the job was created'),
        sa.Column('started_at', sa.TIMESTAMP(timezone=True), nullable=True, comment='When the job processing started'),
        sa.Column('completed_at', sa.TIMESTAMP(timezone=True), nullable=True, comment='When the job finished (success or failure)'),
        sa.CheckConstraint("status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'COMPLETED_WITH_ERRORS', 'FAILED')", name='valid_job_status'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_generation_jobs_status', 'generation_jobs', ['status'])
    op.create_index('ix_generation_jobs_created_at_desc', 'generation_jobs', ['created_at'], postgresql_ops={'created_at': 'DESC'})
    
    # Create certificate_records table
    op.create_table(
        'certificate_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False, comment='Unique certificate record identifier'),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), nullable=False, comment='Reference to the parent generation job'),
        sa.Column('recipient_name', sa.String(length=200), nullable=False, comment='Full name of the certificate recipient'),
        sa.Column('recipient_email', sa.String(length=255), nullable=False, comment='Email address of the recipient'),
        sa.Column('course', sa.String(length=200), nullable=False, comment='Course name for the certificate'),
        sa.Column('completion_date', sa.Date(), nullable=False, comment='Course completion date'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='PENDING', comment='Certificate generation status'),
        sa.Column('error_message', sa.Text(), nullable=True, comment='Error message if generation failed'),
        sa.Column('file_path', sa.String(length=500), nullable=True, comment='Relative path to the generated PDF file'),
        sa.Column('file_size_bytes', sa.Integer(), nullable=True, comment='Size of the generated PDF in bytes'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False, comment='When the record was created'),
        sa.Column('generated_at', sa.TIMESTAMP(timezone=True), nullable=True, comment='When the certificate was successfully generated'),
        sa.CheckConstraint("status IN ('PENDING', 'SUCCESS', 'FAILED')", name='valid_certificate_status'),
        sa.ForeignKeyConstraint(['job_id'], ['generation_jobs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_certificate_records_job_id', 'certificate_records', ['job_id'])
    op.create_index('ix_certificate_records_status', 'certificate_records', ['status'])
    op.create_index('ix_certificate_records_recipient_email', 'certificate_records', ['recipient_email'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_certificate_records_recipient_email', table_name='certificate_records')
    op.drop_index('ix_certificate_records_status', table_name='certificate_records')
    op.drop_index('ix_certificate_records_job_id', table_name='certificate_records')
    op.drop_table('certificate_records')
    
    op.drop_index('ix_generation_jobs_created_at_desc', table_name='generation_jobs')
    op.drop_index('ix_generation_jobs_status', table_name='generation_jobs')
    op.drop_table('generation_jobs')
    
    op.execute('DROP EXTENSION IF EXISTS "uuid-ossp"')
