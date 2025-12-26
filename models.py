from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, Text, Date, ForeignKey
from sqlalchemy.orm import relationship
from database import Base
import datetime


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String(60), unique=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    rfid_tag = Column(String, unique=True, nullable=False)
    role = Column(String, nullable=False)  # "employee" or "admin"
    department = Column(String, nullable=True)
    password_hash = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    hourly_rate = Column(Float, default=200.0)
    allowances = Column(Float, default=0.0)
    deductions = Column(Float, default=0.0)



class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String(60), nullable=False)
    rfid_tag = Column(String, nullable=False)
    entry_time = Column(DateTime, default=datetime.datetime.utcnow)
    exit_time = Column(DateTime, nullable=True)
    duration = Column(Float, nullable=True)  # in hours

    # Location details
    block = Column(String, nullable=True)         # backward compatibility / older data
    room_no = Column(String, nullable=True)       # room number
    location_name = Column(String, nullable=True) # location / block name
    room_id = Column(String, nullable=True)       # reference to Room.room_id


class RemovedEmployee(Base):
    __tablename__ = "removed_employees"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String(60), nullable=False)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    rfid_tag = Column(String, nullable=False)
    role = Column(String, nullable=False)
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
    room_id = Column(String, unique=True, nullable=False)
    room_no = Column(String, nullable=False)
    location_name = Column(String, nullable=False)
    description = Column(String, nullable=True)


class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)   # e.g., "IT", "HR"
    description = Column(String, nullable=True)          # Optional description


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(60), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    status = Column(String(20), default="pending")
    priority = Column(String(20), default="medium")  # low / medium / high
    due_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class LeaveRequest(Base):
    __tablename__ = "leave_requests"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String(20), ForeignKey("users.employee_id"))
    start_date = Column(Date)
    end_date = Column(Date)
    reason = Column(String(255))
    status = Column(String(20), default="Pending")

    user = relationship("User")

