from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, Text
from database import Base
import datetime


# ------------------------------------------------------------
# USER TABLE
# ------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String(60), unique=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    rfid_tag = Column(String, unique=True, nullable=False)
    role = Column(String, nullable=False)  # admin / employee
    department = Column(String, nullable=True)
    password_hash = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)


# ------------------------------------------------------------
# ATTENDANCE TABLE
# ------------------------------------------------------------
class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String(60), nullable=False)
    rfid_tag = Column(String, nullable=False)

    entry_time = Column(DateTime, default=datetime.datetime.utcnow)
    exit_time = Column(DateTime, nullable=True)
    duration = Column(Float, nullable=True)  # hours

    # NEW FIELDS
    block = Column(String, nullable=True)                # Optional
    room_no = Column(String, nullable=False)             # Room Number
    location_name = Column(String, nullable=False)       # Block / Location
    room_id = Column(String, nullable=True)              # Reference to rooms.room_id


# ------------------------------------------------------------
# REMOVED EMPLOYEE TABLE
# ------------------------------------------------------------
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


# ------------------------------------------------------------
# UNKNOWN RFID TABLE
# ------------------------------------------------------------
class UnknownRFID(Base):
    __tablename__ = "unknown_rfids"

    id = Column(Integer, primary_key=True, index=True)
    rfid_tag = Column(String, nullable=False)
    location = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)


# ------------------------------------------------------------
# ROOM TABLE
# ------------------------------------------------------------
class Room(Base):
    __tablename__ = "rooms"

    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(String, unique=True, nullable=False)
    room_no = Column(String, nullable=False)
    location_name = Column(String, nullable=False)
    description = Column(String, nullable=True)


# ------------------------------------------------------------
# DEPARTMENT TABLE
# ------------------------------------------------------------
class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(String, nullable=True)


# ------------------------------------------------------------
# TASK TABLE
# ------------------------------------------------------------
class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(60), nullable=False, index=True)  # employee_id
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(20), default="pending")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    deadline = Column(DateTime)
    status = Column(String(20), default="active")  # active, completed, paused
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class ProjectAssignment(Base):
    __tablename__ = "project_assignments"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, nullable=False)
    employee_id = Column(String(60), nullable=False)    # users.employee_id


class ProjectTask(Base):
    __tablename__ = "project_tasks"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    assigned_to = Column(String(60), nullable=False)      # employee_id
    status = Column(String(20), default="pending")         # pending / in_progress / completed
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

