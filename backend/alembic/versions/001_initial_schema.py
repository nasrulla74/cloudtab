"""Initial schema — all tables

Revision ID: 001_initial
Revises:
Create Date: 2026-02-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # === users ===
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    # === servers ===
    op.create_table(
        'servers',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('owner_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('host', sa.String(255), nullable=False),
        sa.Column('port', sa.Integer(), nullable=False, server_default=sa.text('22')),
        sa.Column('ssh_user', sa.String(100), nullable=False, server_default=sa.text("'root'")),
        sa.Column('ssh_key_encrypted', sa.Text(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default=sa.text("'unknown'")),
        sa.Column('last_connected_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('os_version', sa.String(100), nullable=True),
        sa.Column('cpu_cores', sa.Integer(), nullable=True),
        sa.Column('ram_total_bytes', sa.BigInteger(), nullable=True),
        sa.Column('disk_total_bytes', sa.BigInteger(), nullable=True),
        sa.Column('docker_version', sa.String(50), nullable=True),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_servers_owner_id', 'servers', ['owner_id'])

    # === odoo_instances ===
    op.create_table(
        'odoo_instances',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('server_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('odoo_version', sa.String(10), nullable=False),
        sa.Column('edition', sa.String(20), nullable=False, server_default=sa.text("'community'")),
        sa.Column('container_name', sa.String(100), nullable=False),
        sa.Column('container_id', sa.String(100), nullable=True),
        sa.Column('host_port', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column('odoo_config', sa.Text(), nullable=True),
        sa.Column('addons_path', sa.String(500), nullable=True),
        sa.Column('pg_container_name', sa.String(100), nullable=True),
        sa.Column('pg_port', sa.Integer(), nullable=True),
        sa.Column('pg_password', sa.String(255), nullable=True),
        sa.ForeignKeyConstraint(['server_id'], ['servers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('container_name'),
    )
    op.create_index('ix_odoo_instances_server_id', 'odoo_instances', ['server_id'])

    # === domains ===
    op.create_table(
        'domains',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('instance_id', sa.Integer(), nullable=False),
        sa.Column('domain_name', sa.String(255), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column('ssl_status', sa.String(20), nullable=False, server_default=sa.text("'none'")),
        sa.Column('ssl_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['instance_id'], ['odoo_instances.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('domain_name'),
    )
    op.create_index('ix_domains_instance_id', 'domains', ['instance_id'])

    # === backup_schedules ===
    op.create_table(
        'backup_schedules',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('instance_id', sa.Integer(), nullable=False),
        sa.Column('frequency', sa.String(20), nullable=False),
        sa.Column('retention_days', sa.Integer(), nullable=False, server_default=sa.text('30')),
        sa.Column('storage_type', sa.String(20), nullable=False, server_default=sa.text("'local'")),
        sa.Column('s3_bucket', sa.String(255), nullable=True),
        sa.Column('s3_prefix', sa.String(255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['instance_id'], ['odoo_instances.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_backup_schedules_instance_id', 'backup_schedules', ['instance_id'])

    # === backup_records ===
    op.create_table(
        'backup_records',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('instance_id', sa.Integer(), nullable=False),
        sa.Column('schedule_id', sa.Integer(), nullable=True),
        sa.Column('file_path', sa.String(500), nullable=True),
        sa.Column('file_size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('storage_type', sa.String(20), nullable=False, server_default=sa.text("'local'")),
        sa.Column('status', sa.String(20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['instance_id'], ['odoo_instances.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['schedule_id'], ['backup_schedules.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_backup_records_instance_id', 'backup_records', ['instance_id'])

    # === git_repos ===
    op.create_table(
        'git_repos',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('instance_id', sa.Integer(), nullable=False),
        sa.Column('repo_url', sa.String(500), nullable=False),
        sa.Column('branch', sa.String(100), nullable=False, server_default=sa.text("'main'")),
        sa.Column('deploy_key_encrypted', sa.Text(), nullable=True),
        sa.Column('last_deployed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_commit_sha', sa.String(40), nullable=True),
        sa.ForeignKeyConstraint(['instance_id'], ['odoo_instances.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('instance_id'),
    )

    # === task_logs ===
    op.create_table(
        'task_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('celery_task_id', sa.String(255), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('task_type', sa.String(50), nullable=False),
        sa.Column('target_id', sa.Integer(), nullable=True),
        sa.Column('target_type', sa.String(20), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column('result', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_task_logs_celery_task_id', 'task_logs', ['celery_task_id'], unique=True)
    op.create_index('ix_task_logs_user_id', 'task_logs', ['user_id'])


def downgrade() -> None:
    op.drop_table('task_logs')
    op.drop_table('git_repos')
    op.drop_table('backup_records')
    op.drop_table('backup_schedules')
    op.drop_table('domains')
    op.drop_table('odoo_instances')
    op.drop_table('servers')
    op.drop_table('users')
