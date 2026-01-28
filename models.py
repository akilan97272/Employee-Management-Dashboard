from sqlalchemy import Column, Integer, DateTime, Boolean, Float, Date, ForeignKey
from sqlalchemy.orm import relationship
from database import Base
import datetime
from enum import Enum as PyEnum
from Security.encrypted_defaults import EncryptedString as String, EncryptedText as Text, PlainString, PlainText

# Define User Roles as Enum (for application logic)
class UserRole(PyEnum):
    """
    User Role Types:
    - ADMIN: Full system access, can manage users, departments, and settings
    - EMPLOYEE: Limited access, can only view own profile and assigned data
    """
    ADMIN = "admin"
    EMPLOYEE = "employee"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(PlainString(60), unique=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    email_hash = Column(PlainString(64), unique=True, index=True, nullable=True)
    rfid_tag = Column(String, nullable=False)
    rfid_hash = Column(PlainString(64), unique=True, index=True, nullable=True)
    
    # Role: 'admin' or 'employee' - stored as string in database
    role = Column(PlainString, nullable=False, default="employee")
    
    department = Column(String, nullable=True)
    password_hash = Column(PlainString, nullable=False)
    is_active = Column(Boolean, default=True)

    hourly_rate = Column(Float, default=200.0)
    allowances = Column(Float, default=0.0)
    deductions = Column(Float, default=0.0)

    # TEAM & LEADERSHIP
    can_manage = Column(Boolean, default=False)
    current_team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    active_leader = Column(Boolean, default=False)

    # ✅ EXPLICIT foreign_keys
    team = relationship(
        "Team",
        back_populates="members",
        foreign_keys=[current_team_id]
    )

    employee_id = Column(PlainString(60), unique=True, index=True)


class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(PlainString(60), ForeignKey("users.employee_id"), nullable=False, index=True)
    
    date = Column(Date, nullable=False)
    entry_time = Column(DateTime, nullable=True)
    exit_time = Column(DateTime, nullable=True)
    duration = Column(Float, default=0.0)
    status = Column(PlainString(20), default="PRESENT")
    location_name = Column(PlainString, nullable=True)
    room_no = Column(PlainString, nullable=True)

    user = relationship(
        "User", 
        primaryjoin="Attendance.employee_id == User.employee_id", 
        foreign_keys=[employee_id],
        backref="attendance_logs"
    )
class RemovedEmployee(Base):
    __tablename__ = "removed_employees"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(PlainString(60), nullable=False)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    rfid_tag = Column(String, nullable=False)
    role = Column(PlainString, nullable=False)
    department = Column(String, nullable=True)
    removed_at = Column(DateTime, default=datetime.datetime.utcnow)


class UnknownRFID(Base):
    __tablename__ = "unknown_rfids"

    id = Column(Integer, primary_key=True, index=True)
    rfid_tag = Column(String, nullable=False)
    location = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)


class Room(Base):
    __tablename__ = "rooms"

    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(PlainString, unique=True, nullable=False)
    room_no = Column(PlainString, nullable=False)
    location_name = Column(PlainString, nullable=False)
    description = Column(String, nullable=True)


class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(PlainString, unique=True, nullable=False)   # e.g., "IT", "HR"
    description = Column(String, nullable=True)          # Optional description


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(PlainString(60), nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(Text)
    status = Column(PlainString(20), default="pending")
    priority = Column(PlainString(20), default="medium")  # low / medium / high
    due_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class LeaveRequest(Base):
    __tablename__ = "leave_requests"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(PlainString(20), ForeignKey("users.employee_id"))
    start_date = Column(Date)
    end_date = Column(Date)
    reason = Column(String)
    status = Column(PlainString(20), default="Pending")

    user = relationship("User")

class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    department = Column(String, nullable=False)

    leader_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # ✅ Leader relationship (explicit)
    leader = relationship(
        "User",
        foreign_keys=[leader_id]
    )

    # ✅ Members relationship (explicit)
    members = relationship(
        "User",
        back_populates="team",
        foreign_keys="User.current_team_id"
    )
