import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict

from app.hr.models import EmploymentStatus, LeaveStatus


class EmployeeCreate(BaseModel):
    user_id: uuid.UUID | None = None
    full_name: str
    department: str
    designation: str
    phone: str | None = None
    email: str | None = None
    joined_date: date
    reporting_manager_id: uuid.UUID | None = None
    monthly_salary_rupees: int | None = None
    working_hours_per_day: int = 8
    biometric_id: str | None = None


class EmployeeUpdate(BaseModel):
    full_name: str | None = None
    department: str | None = None
    designation: str | None = None
    phone: str | None = None
    email: str | None = None
    reporting_manager_id: uuid.UUID | None = None
    monthly_salary_rupees: int | None = None
    working_hours_per_day: int | None = None
    biometric_id: str | None = None
    employment_status: EmploymentStatus | None = None


class EmployeeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    full_name: str
    department: str
    designation: str
    phone: str | None
    email: str | None
    joined_date: date
    leave_balance_days: int
    employment_status: EmploymentStatus
    monthly_salary_rupees: int | None
    working_hours_per_day: int
    biometric_id: str | None


class LeaveRequestCreate(BaseModel):
    employee_id: uuid.UUID
    leave_type: str
    from_date: date
    to_date: date


class LeaveRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    employee_id: uuid.UUID
    leave_type: str
    from_date: date
    to_date: date
    status: LeaveStatus
