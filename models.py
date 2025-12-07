# models.py
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, Text
from database import Base
import datetime

class User(Base):
    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String, unique=True, index=True)
    name = Column(String)
    email = Column(String, unique=True)
    rfid_tag = Column(String, unique=True)
    role = Column(String)  # employee, admin, super_admin
    department = Column(String)
    password_hash = Column(String)
    is_active = Column(Boolean, default=True)

class Attendance(Base):
    __tablename__ = "attendance"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String)
    rfid_tag = Column(String)
    entry_time = Column(DateTime)
    exit_time = Column(DateTime, nullable=True)
    duration = Column(Float, nullable=True)  # in hours
    block = Column(String)  # Keep for backward compatibility (old data)
    room_no = Column(String)  # New: Room number
    location_name = Column(String)  # New: Location/block name
    room_id = Column(String)  # New: Reference to Room.room_id

class RemovedEmployee(Base):
    __tablename__ = "removed_employees"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String)
    name = Column(String)
    email = Column(String)
    rfid_tag = Column(String)
    role = Column(String)
    department = Column(String)
    removed_at = Column(DateTime, default=datetime.datetime.utcnow)

class UnknownRFID(Base):
    __tablename__ = "unknown_rfids"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    rfid_tag = Column(String)
    location = Column(String)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

class Room(Base):
    __tablename__ = "rooms"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(String, unique=True)
    room_no = Column(String)
    location_name = Column(String)
    description = Column(String)

class Department(Base):
    __tablename__ = "departments"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)  # e.g., "IT", "HR"
    description = Column(String, nullable=True)  # Optional description

class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(60), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    status = Column(String(20), default="pending")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
