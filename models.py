from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, Text, Date, ForeignKey, Time, Enum
from sqlalchemy.orm import relationship
from database import Base
import datetime

# --- CORE USER & AUTH ---

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String(60), unique=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    rfid_tag = Column(String(100), unique=True, nullable=False)
    
    # Roles: 'admin', 'manager', 'team_lead', 'employee'
    role = Column(String(50), nullable=False) 
    department = Column(String(100), nullable=True)
    password_hash = Column(String(200), nullable=False)
    is_active = Column(Boolean, default=True)

    # Payroll
    hourly_rate = Column(Float, default=200.0)
    allowances = Column(Float, default=0.0)
    deductions = Column(Float, default=0.0)

    # Leadership Flags
    can_manage = Column(Boolean, default=False)
    current_team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    active_leader = Column(Boolean, default=False)

    # Relationships
    team = relationship("Team", back_populates="members", foreign_keys=[current_team_id])
    attendance_logs = relationship("Attendance", back_populates="user", cascade="all, delete-orphan")
    # Personal Tasks relationship
    personal_tasks = relationship("Task", back_populates="user")


# --- ORGANIZATION & TEAMS ---

class Department(Base):
    __tablename__ = "departments"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(String(255), nullable=True)

class Room(Base):
    __tablename__ = "rooms"
    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(String(50), unique=True, nullable=False)
    room_no = Column(String(50), nullable=False)
    location_name = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)

class TeamMember(Base):
    __tablename__ = "team_members"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    joined_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    user = relationship("User", backref="team_memberships")
    team = relationship("Team", back_populates="memberships")

class Team(Base):
    __tablename__ = "teams"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    department = Column(String(100), nullable=False)
    
    # Who is acting as leader RIGHT NOW (swaps daily)
    leader_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Who is the ACTUAL leader (to swap back to)
    permanent_leader_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    leader = relationship("User", foreign_keys=[leader_id])
    permanent_leader = relationship("User", foreign_keys=[permanent_leader_id])
    members = relationship("User", back_populates="team", foreign_keys="User.current_team_id")
    memberships = relationship("TeamMember", back_populates="team", cascade="all, delete-orphan")


# --- ATTENDANCE ---

class Attendance(Base):
    # This is the simplified view used in the dashboard
    __tablename__ = "attendance"
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String(60), ForeignKey("users.employee_id"), nullable=False, index=True)
    date = Column(Date, nullable=False)
    entry_time = Column(DateTime, nullable=True)
    exit_time = Column(DateTime, nullable=True)
    duration = Column(Float, default=0.0)
    status = Column(String(20), default="PRESENT")
    location_name = Column(String(100), nullable=True)
    room_no = Column(String(50), nullable=True)

    user = relationship("User", back_populates="attendance_logs")

class AttendanceDaily(Base):
    # Detailed daily summary
    __tablename__ = "attendance_daily"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(Date, nullable=False)
    status = Column(String(20)) # PRESENT, ABSENT, LEAVE, LATE
    check_in_time = Column(Time, nullable=True)

class AttendanceLog(Base):
    # Raw logs for every movement
    __tablename__ = "attendance_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    entry_time = Column(DateTime, nullable=False)
    exit_time = Column(DateTime, nullable=True)
    location_name = Column(String(255))
    room_no = Column(String(50))

class UnknownRFID(Base):
    __tablename__ = "unknown_rfids"
    id = Column(Integer, primary_key=True, index=True)
    rfid_tag = Column(String(100), nullable=False)
    location = Column(String(100), nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

class LeaveRequest(Base):
    __tablename__ = "leave_requests"
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String(60), ForeignKey("users.employee_id"))
    start_date = Column(Date)
    end_date = Column(Date)
    reason = Column(String(255))
    status = Column(String(20), default="Pending")
    
    # Relationship to access user department for Managers
    user = relationship("User", foreign_keys=[employee_id], primaryjoin="User.employee_id == LeaveRequest.employee_id")

class RemovedEmployee(Base):
    __tablename__ = "removed_employees"
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String(60), nullable=False)
    name = Column(String(100), nullable=False)
    email = Column(String(100), nullable=False)
    rfid_tag = Column(String(100), nullable=False)
    role = Column(String(50), nullable=False)
    department = Column(String(100), nullable=True)
    removed_at = Column(DateTime, default=datetime.datetime.utcnow)


# --- PROJECT MANAGEMENT ---

class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    department = Column(String(100)) # To filter for Managers
    start_date = Column(DateTime)
    deadline = Column(DateTime)
    status = Column(String(20), default="active")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    tasks = relationship("ProjectTask", back_populates="project")
    assignments = relationship("ProjectAssignment", back_populates="project")

class ProjectTask(Base):
    __tablename__ = "project_tasks"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    status = Column(String(20), default="pending")
    deadline = Column(DateTime, nullable=True) # New: Deadline for Team Lead
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    project = relationship("Project", back_populates="tasks")
    assignees = relationship("ProjectTaskAssignee", back_populates="task")

class ProjectAssignment(Base):
    # Links a User to a Project
    __tablename__ = "project_assignments"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    employee_id = Column(String(60), ForeignKey("users.employee_id"), nullable=False)

    project = relationship("Project", back_populates="assignments")
    employee = relationship("User", primaryjoin="User.employee_id == ProjectAssignment.employee_id")

class ProjectTaskAssignee(Base):
    # Links a User to a specific Task
    __tablename__ = "project_task_assignees"
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("project_tasks.id"), nullable=False)
    employee_id = Column(String(60), ForeignKey("users.employee_id"), nullable=False)

    task = relationship("ProjectTask", back_populates="assignees")
    employee = relationship("User", primaryjoin="User.employee_id == ProjectTaskAssignee.employee_id")


# --- GENERAL TASKS (Personal To-Do) ---

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    # Maps to the employee_id string in the User table
    user_id = Column(String(60), ForeignKey("users.employee_id"), nullable=False, index=True)
    
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(20), default="pending")  # pending / in-progress / done
    priority = Column(String(20), default="medium") # low / medium / high
    
    due_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationship to access the user object
    user = relationship("User", back_populates="personal_tasks")