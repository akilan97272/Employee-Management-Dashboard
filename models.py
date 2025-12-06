from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, Text
from database import Base
import datetime

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String(60), unique=True, index=True)
    name = Column(String)
    email = Column(String, unique=True)
    rfid_tag = Column(String, unique=True)
    role = Column(String)  # employee, admin
    department = Column(String)
    password_hash = Column(String)
    is_active = Column(Boolean, default=True)


class Attendance(Base):
    __tablename__ = "attendance"
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String(60))
    rfid_tag = Column(String)
    entry_time = Column(DateTime)
    exit_time = Column(DateTime, nullable=True)
    duration = Column(Float, nullable=True)  # in hours

    # Updated fields
    block = Column(String)
    room_no = Column(String)
    location_name = Column(String)
    room_id = Column(String)


class RemovedEmployee(Base):
    __tablename__ = "removed_employees"
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String(60))
    name = Column(String)
    email = Column(String)
    rfid_tag = Column(String)
    role = Column(String)
    department = Column(String)
    removed_at = Column(DateTime, default=datetime.datetime.utcnow)


class UnknownRFID(Base):
    __tablename__ = "unknown_rfids"
    id = Column(Integer, primary_key=True, index=True)
    rfid_tag = Column(String)
    location = Column(String)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)


class Room(Base):
    __tablename__ = "rooms"
    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(String, unique=True)
    room_no = Column(String)
    location_name = Column(String)
    description = Column(String)


class Department(Base):
    __tablename__ = "departments"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)
    description = Column(String, nullable=True)


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(60), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    status = Column(String(20), default="pending")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
