"""hr_module_attendance_payroll_process_monitoring

Revision ID: e1ff5060435d
Revises: 7f3a9c2e5b81
Create Date: 2026-09-29 16:09:45.339536

Hand-trimmed from the raw `alembic revision --autogenerate` output: that
run also re-detected the recurring 'uq_role_permission' false positive
noted in a147ba0be789's own migration (Postgres representing a UNIQUE
constraint as a unique index, which autogenerate keeps flip-flopping
between forms), plus the same false-positive pattern on several other
tables (assets.qr_token, indent_requests, locations, medicine_templates,
pharmacy_purchase_orders/returns/purchases, vendors, webauthn_*) that
have nothing to do with this change. All of that noise is stripped —
only the genuine new HR/appointment-history tables and columns remain.
Added explicit server_defaults on the new NOT NULL columns so this
applies cleanly against the already-seeded demo employees/attendance
rows, not just an empty database.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'e1ff5060435d'
down_revision: Union[str, None] = '7f3a9c2e5b81'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('hr_alert_resolutions',
    sa.Column('alert_key', sa.String(length=255), nullable=False),
    sa.Column('resolved_by_id', sa.UUID(), nullable=False),
    sa.Column('note', sa.String(length=500), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_hr_alert_resolutions_alert_key'), 'hr_alert_resolutions', ['alert_key'], unique=True)

    op.create_table('hr_process_thresholds',
    sa.Column('stage', sa.String(length=32), nullable=False),
    sa.Column('threshold_minutes', sa.Integer(), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('stage')
    )

    op.create_table('hr_settings',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('full_day_hours', sa.Numeric(precision=4, scale=2), nullable=False),
    sa.Column('half_day_min_hours', sa.Numeric(precision=4, scale=2), nullable=False),
    sa.Column('late_arrival_grace_minutes', sa.Integer(), nullable=False),
    sa.Column('early_departure_grace_minutes', sa.Integer(), nullable=False),
    sa.Column('standard_start_time', sa.String(length=5), nullable=False),
    sa.Column('standard_end_time', sa.String(length=5), nullable=False),
    sa.Column('working_days_per_month', sa.Integer(), nullable=False),
    sa.Column('half_day_pay_fraction', sa.Numeric(precision=3, scale=2), nullable=False),
    sa.Column('overtime_rate_per_hour_rupees', sa.Integer(), nullable=False),
    sa.Column('updated_by_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('attendance_imports',
    sa.Column('filename', sa.String(length=255), nullable=False),
    sa.Column('uploaded_by_id', sa.UUID(), nullable=False),
    sa.Column('status', sa.Enum('PREVIEWED', 'CONFIRMED', name='attendanceimportstatus'), nullable=False),
    sa.Column('records_found', sa.Integer(), nullable=False),
    sa.Column('matched_count', sa.Integer(), nullable=False),
    sa.Column('unknown_count', sa.Integer(), nullable=False),
    sa.Column('duplicate_count', sa.Integer(), nullable=False),
    sa.Column('error_count', sa.Integer(), nullable=False),
    sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('confirmed_by_id', sa.UUID(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['confirmed_by_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['uploaded_by_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_attendance_imports_status'), 'attendance_imports', ['status'], unique=False)

    op.create_table('attendance_import_rows',
    sa.Column('import_id', sa.UUID(), nullable=False),
    sa.Column('row_number', sa.Integer(), nullable=False),
    sa.Column('biometric_id', sa.String(length=64), nullable=False),
    sa.Column('employee_id', sa.UUID(), nullable=True),
    sa.Column('attendance_date', sa.Date(), nullable=True),
    sa.Column('entry_time', sa.DateTime(timezone=True), nullable=True),
    sa.Column('exit_time', sa.DateTime(timezone=True), nullable=True),
    sa.Column('is_unknown', sa.Boolean(), nullable=False),
    sa.Column('is_duplicate', sa.Boolean(), nullable=False),
    sa.Column('error', sa.String(length=255), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], ),
    sa.ForeignKeyConstraint(['import_id'], ['attendance_imports.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_attendance_import_rows_import_id'), 'attendance_import_rows', ['import_id'], unique=False)

    op.create_table('payroll_records',
    sa.Column('employee_id', sa.UUID(), nullable=False),
    sa.Column('month', sa.Integer(), nullable=False),
    sa.Column('year', sa.Integer(), nullable=False),
    sa.Column('base_salary_rupees', sa.Integer(), nullable=False),
    sa.Column('working_days', sa.Integer(), nullable=False),
    sa.Column('present_days', sa.Integer(), nullable=False),
    sa.Column('half_days', sa.Integer(), nullable=False),
    sa.Column('absent_days', sa.Integer(), nullable=False),
    sa.Column('payable_days', sa.Numeric(precision=6, scale=2), nullable=False),
    sa.Column('per_day_rupees', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('deduction_rupees', sa.Integer(), nullable=False),
    sa.Column('overtime_hours', sa.Numeric(precision=6, scale=2), nullable=False),
    sa.Column('overtime_amount_rupees', sa.Integer(), nullable=False),
    sa.Column('net_salary_rupees', sa.Integer(), nullable=False),
    sa.Column('status', sa.Enum('CALCULATED', 'APPROVED', 'PAID', name='payrollstatus'), nullable=False),
    sa.Column('calculated_at', sa.DateTime(), nullable=False),
    sa.Column('calculated_by_id', sa.UUID(), nullable=False),
    sa.Column('approved_at', sa.DateTime(), nullable=True),
    sa.Column('approved_by_id', sa.UUID(), nullable=True),
    sa.Column('paid_at', sa.DateTime(), nullable=True),
    sa.Column('paid_by_id', sa.UUID(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['approved_by_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['calculated_by_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], ),
    sa.ForeignKeyConstraint(['paid_by_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('employee_id', 'month', 'year', name='uq_payroll_employee_month_year')
    )
    op.create_index(op.f('ix_payroll_records_employee_id'), 'payroll_records', ['employee_id'], unique=False)
    op.create_index(op.f('ix_payroll_records_status'), 'payroll_records', ['status'], unique=False)

    # appointmentstatus already exists as a Postgres type (from
    # appointments.status) — create_type=False so this reuses it instead
    # of trying (and failing) to CREATE TYPE a second time.
    _appointment_status_enum = postgresql.ENUM(
        'REGISTERED', 'ARRIVED', 'WAITING', 'CONSULTATION', 'INVESTIGATION', 'BILLING', 'PHARMACY', 'FOLLOW_UP', 'COMPLETED', 'CANCELLED', 'NO_SHOW',
        name='appointmentstatus', create_type=False,
    )
    op.create_table('appointment_status_events',
    sa.Column('appointment_id', sa.UUID(), nullable=False),
    sa.Column('from_status', _appointment_status_enum, nullable=False),
    sa.Column('to_status', _appointment_status_enum, nullable=False),
    sa.Column('changed_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('changed_by_id', sa.UUID(), nullable=False),
    sa.Column('delay_reason', sa.String(length=255), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['appointment_id'], ['appointments.id'], ),
    sa.ForeignKeyConstraint(['changed_by_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_appointment_status_events_appointment_id'), 'appointment_status_events', ['appointment_id'], unique=False)
    op.create_index(op.f('ix_appointment_status_events_changed_at'), 'appointment_status_events', ['changed_at'], unique=False)
    op.create_index(op.f('ix_appointment_status_events_to_status'), 'appointment_status_events', ['to_status'], unique=False)

    # Enum types used only via add_column (not create_table) aren't
    # auto-created by SQLAlchemy the way create_table's are — create them
    # explicitly first, then reference with create_type=False.
    attendance_source_enum = postgresql.ENUM('MANUAL', 'BIOMETRIC_IMPORT', name='attendancesource')
    attendance_source_enum.create(op.get_bind(), checkfirst=True)
    employment_status_enum = postgresql.ENUM('ACTIVE', 'INACTIVE', name='employmentstatus')
    employment_status_enum.create(op.get_bind(), checkfirst=True)

    op.add_column('attendance_records', sa.Column('entry_time', sa.DateTime(timezone=True), nullable=True))
    op.add_column('attendance_records', sa.Column('exit_time', sa.DateTime(timezone=True), nullable=True))
    op.add_column('attendance_records', sa.Column('working_minutes', sa.Integer(), nullable=True))
    op.add_column('attendance_records', sa.Column('source', postgresql.ENUM('MANUAL', 'BIOMETRIC_IMPORT', name='attendancesource', create_type=False), nullable=False, server_default='MANUAL'))
    op.add_column('attendance_records', sa.Column('import_id', sa.UUID(), nullable=True))
    op.add_column('attendance_records', sa.Column('missing_entry', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('attendance_records', sa.Column('missing_exit', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('attendance_records', sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('attendance_records', sa.Column('resolved_by_id', sa.UUID(), nullable=True))
    attendance_status_enum = postgresql.ENUM('PRESENT', 'HALF_DAY', 'ABSENT', name='attendancestatus')
    attendance_status_enum.create(op.get_bind(), checkfirst=True)
    op.alter_column('attendance_records', 'status',
               existing_type=sa.VARCHAR(length=32),
               type_=postgresql.ENUM('PRESENT', 'HALF_DAY', 'ABSENT', name='attendancestatus', create_type=False),
               existing_nullable=False,
               postgresql_using="upper(status)::attendancestatus")
    op.create_index(op.f('ix_attendance_records_status'), 'attendance_records', ['status'], unique=False)
    op.create_unique_constraint('uq_attendance_employee_date', 'attendance_records', ['employee_id', 'attendance_date'])
    op.create_foreign_key(None, 'attendance_records', 'users', ['resolved_by_id'], ['id'])
    op.create_foreign_key(None, 'attendance_records', 'attendance_imports', ['import_id'], ['id'])

    op.add_column('employees', sa.Column('email', sa.String(length=255), nullable=True))
    op.add_column('employees', sa.Column('employment_status', postgresql.ENUM('ACTIVE', 'INACTIVE', name='employmentstatus', create_type=False), nullable=False, server_default='ACTIVE'))
    op.add_column('employees', sa.Column('monthly_salary_rupees', sa.Integer(), nullable=True))
    op.add_column('employees', sa.Column('working_hours_per_day', sa.Integer(), nullable=False, server_default='8'))
    op.add_column('employees', sa.Column('biometric_id', sa.String(length=64), nullable=True))
    op.create_index(op.f('ix_employees_biometric_id'), 'employees', ['biometric_id'], unique=True)
    op.create_index(op.f('ix_employees_employment_status'), 'employees', ['employment_status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_employees_employment_status'), table_name='employees')
    op.drop_index(op.f('ix_employees_biometric_id'), table_name='employees')
    op.drop_column('employees', 'biometric_id')
    op.drop_column('employees', 'working_hours_per_day')
    op.drop_column('employees', 'monthly_salary_rupees')
    op.drop_column('employees', 'employment_status')
    op.drop_column('employees', 'email')

    op.drop_constraint(None, 'attendance_records', type_='foreignkey')
    op.drop_constraint(None, 'attendance_records', type_='foreignkey')
    op.drop_constraint('uq_attendance_employee_date', 'attendance_records', type_='unique')
    op.drop_index(op.f('ix_attendance_records_status'), table_name='attendance_records')
    op.alter_column('attendance_records', 'status',
               existing_type=sa.Enum('PRESENT', 'HALF_DAY', 'ABSENT', name='attendancestatus'),
               type_=sa.VARCHAR(length=32),
               existing_nullable=False)
    op.drop_column('attendance_records', 'resolved_by_id')
    op.drop_column('attendance_records', 'resolved_at')
    op.drop_column('attendance_records', 'missing_exit')
    op.drop_column('attendance_records', 'missing_entry')
    op.drop_column('attendance_records', 'import_id')
    op.drop_column('attendance_records', 'source')
    op.drop_column('attendance_records', 'working_minutes')
    op.drop_column('attendance_records', 'exit_time')
    op.drop_column('attendance_records', 'entry_time')

    op.drop_index(op.f('ix_appointment_status_events_to_status'), table_name='appointment_status_events')
    op.drop_index(op.f('ix_appointment_status_events_changed_at'), table_name='appointment_status_events')
    op.drop_index(op.f('ix_appointment_status_events_appointment_id'), table_name='appointment_status_events')
    op.drop_table('appointment_status_events')

    op.drop_index(op.f('ix_payroll_records_status'), table_name='payroll_records')
    op.drop_index(op.f('ix_payroll_records_employee_id'), table_name='payroll_records')
    op.drop_table('payroll_records')

    op.drop_index(op.f('ix_attendance_import_rows_import_id'), table_name='attendance_import_rows')
    op.drop_table('attendance_import_rows')

    op.drop_index(op.f('ix_attendance_imports_status'), table_name='attendance_imports')
    op.drop_table('attendance_imports')

    op.drop_table('hr_settings')
    op.drop_table('hr_process_thresholds')

    op.drop_index(op.f('ix_hr_alert_resolutions_alert_key'), table_name='hr_alert_resolutions')
    op.drop_table('hr_alert_resolutions')
