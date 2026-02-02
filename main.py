from fastapi import FastAPI, Depends, HTTPException, Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import SessionLocal, get_db, engine, Base
from models import User, Attendance, RemovedEmployee, UnknownRFID, Room, Department, Task, LeaveRequest, TeamMember
from auth import authenticate_user, hash_password
from sqlalchemy import func, extract
import random
import string
import datetime
from typing import Optional
from calendar import monthrange
from team_scheduler import auto_assign_leaders
from threading import Thread
import time
from database import get_team_info
from apscheduler.schedulers.background import BackgroundScheduler
# Ensure these are imported from your models
from models import Team, User
from fastapi.exception_handlers import http_exception_handler
from starlette.middleware.sessions import SessionMiddleware

scheduler = BackgroundScheduler()

# Importing all models 
from models import (
    User, Attendance, RemovedEmployee, UnknownRFID, Room, Department, 
    Task, LeaveRequest, Team, Project, ProjectTask, ProjectAssignment, 
    ProjectTaskAssignee, AttendanceLog, AttendanceDaily, Payroll
)
from team_scheduler import auto_assign_leaders

# Setup
Base.metadata.create_all(bind=engine)
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
app.add_middleware(SessionMiddleware, secret_key="super-secret-key")
scheduler = BackgroundScheduler()

# FastAPI app
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# Session middleware (simple in-memory for demo; use proper sessions in prod)

app.add_middleware(SessionMiddleware, secret_key="your-secret-key")

# ----------------------------------------
# SESSION HANDLERS
# ----------------------------------------

def get_current_user(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def calculate_monthly_payroll(db, emp, month, year):
    # First, check for an existing persisted payroll for this employee/month/year
    try:
        existing = db.query(Payroll).filter(
            Payroll.employee_id == emp.employee_id,
            Payroll.month == month,
            Payroll.year == year
        ).first()
    except Exception:
        existing = None

    if existing:
        return {
            "present_days": existing.present_days,
            "leave_days": existing.leave_days,
            "unpaid_leaves": existing.unpaid_leaves,
            "base_salary": round(existing.base_salary, 2),
            "leave_deduction": round(existing.leave_deduction, 2),
            "tax": round(existing.tax, 2),
            "net_salary": round(existing.net_salary, 2),
            "explanation": existing.explanation,
            "locked": bool(existing.locked),
            "generated_at": existing.created_at
        }

    # 1️⃣ Present days (from AttendanceDaily)
    present_days = db.query(func.count()).filter(
        AttendanceDaily.user_id == emp.id,
        AttendanceDaily.status.in_("PRESENT", "LATE") if False else AttendanceDaily.status.in_(["PRESENT", "LATE"]),
        extract("month", AttendanceDaily.date) == month,
        extract("year", AttendanceDaily.date) == year
    ).scalar() or 0

    # 2️⃣ Approved leaves
    leave_days = db.query(func.count()).filter(
        LeaveRequest.employee_id == emp.employee_id,
        LeaveRequest.status == "Approved",
        extract("month", LeaveRequest.start_date) == month,
        extract("year", LeaveRequest.start_date) == year
    ).scalar() or 0

    # 3️⃣ Salary rules
    WORKING_DAYS = 22
    per_day_salary = (emp.base_salary or 0.0) / WORKING_DAYS if WORKING_DAYS else 0.0

    unpaid_leaves = max(0, (leave_days or 0) - (emp.paid_leaves_allowed or 0))
    leave_deduction = unpaid_leaves * per_day_salary

    gross_salary = (emp.base_salary or 0.0) - leave_deduction
    tax = gross_salary * ((emp.tax_percentage or 0.0) / 100.0)
    allowances = getattr(emp, 'allowances', 0) or 0
    deductions = getattr(emp, 'deductions', 0) or 0
    net_salary = gross_salary - tax + allowances - deductions

    # Explanation text for UI
    base_salary_val = round(emp.base_salary or 0.0, 2)
    leave_deduction_val = round(leave_deduction, 2)
    tax_val = round(tax, 2)
    tax_percentage = emp.tax_percentage or 0.0

    explanation = f"""
Base Salary: ₹{base_salary_val}
Unpaid Leaves: {unpaid_leaves}
Leave Deduction: ₹{leave_deduction_val}
Tax ({tax_percentage}%): ₹{tax_val}
"""

    # Persist the generated payroll record so it's locked for future reads
    payroll_rec = Payroll(
        employee_id=emp.employee_id,
        month=month,
        year=year,
        present_days=present_days,
        leave_days=leave_days,
        unpaid_leaves=unpaid_leaves,
        base_salary=emp.base_salary or 0.0,
        leave_deduction=leave_deduction,
        tax=tax,
        allowances=allowances,
        deductions=deductions,
        net_salary=round(net_salary, 2),
        explanation=explanation,
        locked=True
    )
    try:
        db.add(payroll_rec)
        db.commit()
        db.refresh(payroll_rec)
    except Exception:
        db.rollback()

    return {
        "present_days": present_days,
        "leave_days": leave_days,
        "unpaid_leaves": unpaid_leaves,
        "base_salary": base_salary_val,
        "leave_deduction": leave_deduction_val,
        "tax": tax_val,
        "net_salary": round(net_salary, 2),
        "explanation": explanation,
        "locked": True,
        "generated_at": payroll_rec.created_at if hasattr(payroll_rec, 'created_at') else None
    }

@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("auth/login.html", {"request": request})

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = authenticate_user(db, username, password)
    if not user:
        return templates.TemplateResponse("auth/login.html", {"request": request, "error": "Invalid credentials"})
    
    request.session["user_id"] = user.id

    # ROLE BASED REDIRECTS
    if user.role == "admin":
        return RedirectResponse("/admin/select_dashboard", status_code=303)
    elif user.role == "manager":
        return RedirectResponse("/manager/dashboard", status_code=303)
    elif user.role == "team_lead":
        return RedirectResponse("/leader/dashboard", status_code=303)
    else:
        return RedirectResponse("/employee", status_code=303)

#----------------------------------------
# LOGOUT ROUTE
#----------------------------------------

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("session") 
    return response

@app.middleware("http")
async def add_no_cache_headers(request: Request, call_next):
    response = await call_next(request)
    # Only apply to protected routes (admin and employee)
    if request.url.path.startswith("/admin") or request.url.path.startswith("/employee"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 401:
        return templates.TemplateResponse("auth/401.html", {"request": request}, status_code=401)
    
    # Use the imported default handler for all other errors
    return await http_exception_handler(request, exc)

# ----------------------------------------
# ADMIN SELECT DASHBOARD
# ----------------------------------------

@app.get("/admin/select_dashboard", response_class=HTMLResponse)
async def admin_choice(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse("admin/admin_select_dashboard.html", {"request": request, "user": user})

@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "admin": raise HTTPException(status_code=403)
    # ... (Your existing admin dashboard logic) ...
    # Placeholder return to prevent error in this snippet
    return templates.TemplateResponse("admin/admin_dashboard.html",
                                       {"request": request, 
                                        "user": user, 
                                        "blocks": [],
                                        "employees": [],
                                        "unknown_rfids": [], 
                                        "admins": [], 
                                        "removed_employees": []
                                        }
                                    )
#----------------------------------------
# ADMIN - ADD EMPLOYEE ROUTE
#----------------------------------------

@app.post("/admin/add_employee")
async def add_employee(request: Request, name: str = Form(...), email: str = Form(...), rfid_tag: str = Form(...),
                       role: str = Form(...), department: str = Form(...), user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    prefix = {"IT": "2261", "HR": "2262", "Finance": "2263"}.get(department, "2260")   # to create a defined id instead of manual entry
    max_emp = db.query(User).filter(User.employee_id.like(f"{prefix}%")).order_by(User.employee_id.desc()).first()
    if max_emp and len(max_emp.employee_id) > 4:
        try:
            suffix = int(max_emp.employee_id[4:])
            next_id = suffix + 1
        except ValueError:
            next_id = 1
    else:
        next_id = 1
    employee_id = f"{prefix}{next_id:03d}"
    # Generate password
    password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    password_hash = hash_password(password)
    new_user = User(employee_id=employee_id, name=name, email=email, rfid_tag=rfid_tag, role=role,
                    department=department, password_hash=password_hash)
    db.add(new_user)
    db.commit()
    return {"employee_id": employee_id, "password": password}

#----------------------------------------
#ADMIN - Settings
#----------------------------------------

@app.get("/admin/settings", response_class=HTMLResponse)
async def admin_settings_page(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
    
    rooms = db.query(Room).all()
    departments = db.query(Department).all()
    
    return templates.TemplateResponse("admin/admin_settings.html", {
        "request": request, 
        "user": user, 
        "rooms": rooms, 
        "departments": departments
    })

#-----------------------------------------
#ADMIN - REMOVE EMPLOYEE ROUTE
#-----------------------------------------

@app.post("/admin/remove_employee")
async def remove_employee(request: Request, employee_id: str = Form(...), user: User = Depends(get_current_user),
                          db: Session = Depends(get_db)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
    emp = db.query(User).filter(User.employee_id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    # Move to removed
    removed = RemovedEmployee(employee_id=emp.employee_id, name=emp.name, email=emp.email, rfid_tag=emp.rfid_tag,
                              role=emp.role, department=emp.department)
    db.add(removed)
    db.delete(emp)
    db.commit()
    return {"status": "removed", "message": "Employee removed"}


@app.post("/admin/set_base_salary")
async def set_base_salary(
    employee_id: str = Form(...),
    base_salary: float = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if user.role != "admin":
        raise HTTPException(status_code=403)

    emp = db.query(User).filter(User.employee_id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    emp.base_salary = base_salary
    db.commit()

    return RedirectResponse("/admin/manage_employees", status_code=303)

#-----------------------------------------
#ADMIN - MANAGE EMPLOYEE ROUTE
#-----------------------------------------

@app.get("/admin/manage_employees", response_class=HTMLResponse)
async def admin_manage_employees(request: Request,
                                 search: Optional[str] = None,
                                 department: Optional[str] = None,
                                 user: User = Depends(get_current_user),
                                 db: Session = Depends(get_db)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
    query = db.query(User).filter(User.is_active == True)
    if search:
        query = query.filter(
            (User.employee_id.like(f"%{search}%")) |
            (User.name.ilike(f"%{search}%"))
        )
    if department:
        query = query.filter(User.department == department)
    employees = query.all()
    return templates.TemplateResponse("admin/admin_manage.html",{
        "request": request,
        "user": user,
        "employees": employees,
        "search": search,
        "current_year": datetime.datetime.utcnow().year
        })

@app.post("/admin/update_employee")
async def admin_update_employee(request: Request,
                                 employee_id: str = Form(...),
                                 name: Optional[str] = Form(None),
                                 email: Optional[str] = Form(None),
                                 department: Optional[str] = Form(None),
                                 role: Optional[str] = Form(None),
                                 base_salary: Optional[float] = Form(None),
                                 paid_leaves_allowed: Optional[int] = Form(None),
                                 tax_percentage: Optional[float] = Form(None),
                                 user: User = Depends(get_current_user),
                                 db: Session = Depends(get_db)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    emp = db.query(User).filter(User.employee_id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Update editable fields if provided
    if name is not None:
        emp.name = name
    if email is not None:
        emp.email = email
    if department is not None:
        emp.department = department
    if role is not None:
        emp.role = role

    # Payroll related fields
    try:
        if base_salary is not None:
            emp.base_salary = float(base_salary)
    except Exception:
        pass

    try:
        if paid_leaves_allowed is not None:
            emp.paid_leaves_allowed = int(paid_leaves_allowed)
    except Exception:
        pass

    try:
        if tax_percentage is not None:
            emp.tax_percentage = float(tax_percentage)
    except Exception:
        pass

    db.commit()
    return RedirectResponse(url="/admin/manage_employees", status_code=303)

# ----------------------------------------
# ADMIN TEAM MANAGEMENT ROUTES
# ----------------------------------------

@app.get("/admin/manage_teams", response_class=HTMLResponse)
async def admin_manage_teams(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
    
    teams = db.query(Team).all()
    employees = db.query(User).filter(User.is_active == True).all()
    
    # --- FIX: FETCH DEPARTMENTS ---
    departments = db.query(Department).all()
    
    # Calculate Project Status for Teams (Optional logic for the progress bar)
    team_data = []
    for t in teams:
        projs = db.query(Project).filter(Project.department == t.department).all()
        completion = 0
        if projs:
            total_tasks = sum([len(p.tasks) for p in projs])
            completed_tasks = sum([len([task for task in p.tasks if task.status == 'completed']) for p in projs])
            if total_tasks > 0:
                completion = int((completed_tasks / total_tasks) * 100)
        
        team_data.append({
            "obj": t,
            "completion": completion,
            "member_count": len(t.memberships)
        })

    return templates.TemplateResponse("admin/admin_manage_teams.html", {
        "request": request, 
        "user": user, 
        "team_data": team_data, 
        "employees": employees,
        "departments": departments  # <--- PASSING THIS IS CRITICAL
    })

@app.post("/admin/create_team")
async def create_team(
    name: str = Form(...),
    department: str = Form(...), # Accepts any string now
    leader_employee_id: str = Form(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if user.role != "admin": raise HTTPException(status_code=403)
    
    leader_id = None
    if leader_employee_id:
        leader = db.query(User).filter(User.employee_id == leader_employee_id).first()
        if leader:
            leader_id = leader.id
            leader.can_manage = True

    # Set both leader_id (active) and permanent_leader_id (original)
    new_team = Team(name=name, department=department, leader_id=leader_id, permanent_leader_id=leader_id)
    db.add(new_team)
    db.commit()
    
    # If leader exists, add them to team_members too
    if leader_id:
        db.add(TeamMember(user_id=leader_id, team_id=new_team.id))
        db.commit()

    return RedirectResponse("/admin/manage_teams", status_code=303)

@app.post("/admin/delete_team")
async def delete_team(
    team_id: int = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if user.role != "admin": raise HTTPException(status_code=403)
    
    team = db.query(Team).filter(Team.id == team_id).first()
    if team:
        db.delete(team) # Cascades to team_members due to model setup
        db.commit()
        
    return RedirectResponse("/admin/manage_teams", status_code=303)

@app.post("/admin/assign_member")
async def assign_team_member(
    employee_id: str = Form(...),
    team_id: int = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if user.role != "admin": raise HTTPException(status_code=403)

    emp = db.query(User).filter(User.employee_id == employee_id).first()
    
    # Check if already in team
    exists = db.query(TeamMember).filter(TeamMember.user_id == emp.id, TeamMember.team_id == team_id).first()
    if not exists:
        new_member = TeamMember(user_id=emp.id, team_id=team_id)
        db.add(new_member)
        db.commit()

    return RedirectResponse("/admin/manage_teams", status_code=303)
# (Payroll update route removed)

#-----------------------------------------
#ADMIN - EMPLOYEE DETAILS ROUTE
#-----------------------------------------

@app.get("/admin/employee_details", response_class=HTMLResponse)
async def employee_details(request: Request, employee_id: Optional[str] = None, name: Optional[str] = None,
                           user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
    query = db.query(User).filter(User.is_active == True)
    if employee_id:
        query = query.filter(User.employee_id == employee_id)
    if name:
        query = query.filter(User.name.ilike(f"%{name}%"))
    emp = query.first()
    if not emp:
        return templates.TemplateResponse("admin/admin_employee_details.html", {"request": request, "error": "Employee not found"})
    # Calculate total time (sum durations)
    total_time = db.query(Attendance).filter(Attendance.employee_id == emp.employee_id).with_entities(
        Attendance.duration).all()
    total_hours = sum(d[0] for d in total_time if d[0])
    return templates.TemplateResponse("admin/admin_employee_details.html",
                                      {"request": request, "employee": emp, "total_hours": total_hours})

#-----------------------------------------
#ADMIN - ADD ROOM & DEPARTMENT ROUTES
#----------------------------------------

@app.post("/admin/add_room")
async def add_room(request: Request, room_no: str = Form(...), location_name: str = Form(...),
                   description: str = Form(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    # Check if room already exists
    existing_room = db.query(Room).filter(Room.room_no == room_no, Room.location_name == location_name).first()
    if existing_room:
        raise HTTPException(status_code=400, detail="Room already exists")

    room_id = f"R{room_no}"
    new_room = Room(room_id=room_id, room_no=room_no, location_name=location_name, description=description)
    db.add(new_room)
    db.commit()
    return {"room_id": room_id, "message": "Room added successfully"}

#-----------------------------------------
#ADMIN - ADD DEPARTMENT ROUTE
#-----------------------------------------

@app.post("/admin/add_department")
async def add_department(request: Request, name: str = Form(...), description: str = Form(...),
                         user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    # Check if department already exists
    existing_dept = db.query(Department).filter(Department.name == name).first()
    if existing_dept:
        raise HTTPException(status_code=400, detail="Department already exists")

    new_dept = Department(name=name, description=description)
    db.add(new_dept)
    db.commit()
    return {"message": "Department added successfully"}

#-----------------------------------------
#ADMIN - REMOVE ROOM ROUTE
#-----------------------------------------

@app.post("/admin/remove_room")
async def remove_room(request: Request, room_id: str = Form(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
    room = db.query(Room).filter(Room.room_id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    # Check if room has active attendance
    active_attendance = db.query(Attendance).filter(Attendance.room_id == room_id, Attendance.exit_time.is_(None)).first()
    if active_attendance:
        raise HTTPException(status_code=400, detail="Cannot remove room with active attendance")
    db.delete(room)
    db.commit()
    return {"message": "Room removed successfully"}

#-----------------------------------------
#ADMIN - PAYROLL PAGE
#----------------------------------------

@app.get("/admin/payroll", response_class=HTMLResponse)
async def admin_payroll(
    request: Request,
    month: int = datetime.date.today().month,
    year: int = datetime.date.today().year,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if user.role != "admin":
        raise HTTPException(status_code=403)

    employees = db.query(User).filter(User.is_active == True).all()
    payroll = []

    for emp in employees:
        data = calculate_monthly_payroll(db, emp, month, year)
        payroll.append({
            "name": emp.name,
            "employee_id": emp.employee_id,
            **data
        })

    total_salary = sum(p["net_salary"] for p in payroll)
    avg_salary = round(total_salary / len(payroll), 2) if payroll else 0
    max_salary = max((p["net_salary"] for p in payroll), default=0)

    return templates.TemplateResponse(
        "admin/admin_payroll.html",
        {
            "request": request,
            "user": user,
            "payroll": payroll,
            "total_salary": round(total_salary, 2),
            "avg_salary": avg_salary,
            "max_salary": max_salary,
            "current_year": year
        }
    )

# ----------------------------------------
# ADMIN ATTENDANCE PAGE
# ----------------------------------------

@app.get("/admin/attendance", response_class=HTMLResponse)
async def admin_attendance(
    request: Request,
    department: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
    present_query = db.query(
        User.employee_id,
        User.name,
        User.department,
        Attendance.room_no,
        Attendance.entry_time
    ).join(
        Attendance,
        Attendance.employee_id == User.employee_id
    ).filter(
        Attendance.exit_time == None
    )
    if department:
        present_query = present_query.filter(User.department == department)
    present = present_query.all()
    present_count = len(present)
    total_employees = db.query(User).filter(
        User.is_active == True
    ).count()
    absent_count = total_employees - present_count
    unknown_rfids = db.query(UnknownRFID).order_by(
        UnknownRFID.id.desc()
    ).limit(20).all()
    return templates.TemplateResponse(
        "admin/admin_attendance.html",
        {
            "request": request,
            "user": user,
            "present": present,
            "present_count": present_count,
            "absent_count": absent_count,
            "unknown_rfids": unknown_rfids,
        }
    )

# ----------------------------------------
# ADMIN UNKNOWN RFID PAGE
# ----------------------------------------

@app.get("/admin/unknown_rfid", response_class=HTMLResponse)
async def admin_unknown_rfid(
    request: Request,
    search: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
    query = db.query(UnknownRFID)
    if search:
        query = query.filter(
            (UnknownRFID.rfid_tag.like(f"%{search}%")) |
            (UnknownRFID.location.ilike(f"%{search}%"))
        )
    unknown_rfids = query.order_by(UnknownRFID.timestamp.desc()).all()
    return templates.TemplateResponse(
        "admin/admin_unknown.html",
        {
            "request": request,
            "user": user,
            "search": search,
            "unknown_rfids": unknown_rfids,
            "current_year": datetime.datetime.utcnow().year
        }
    )

# ----------------------------------------
# ADMIN RESOLVE RFID ROUTE
# ----------------------------------------

@app.post("/admin/resolve_rfid")
async def resolve_rfid(request: Request, rfid_tag: str = Form(...), db: Session = Depends(get_db)):
    db.query(UnknownRFID).filter(UnknownRFID.rfid_tag == rfid_tag).delete()
    db.commit()
    return RedirectResponse("/admin/unknown_rfid", status_code=303)

# ----------------------------------------
# ADMIN LEAVE REQUESTS PAGE
# ----------------------------------------

@app.get("/admin/leave_requests", response_class=HTMLResponse)
async def admin_leave_page(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
    pending = db.query(LeaveRequest).order_by(LeaveRequest.id.desc()).all()
    return templates.TemplateResponse("admin/admin_leave_requests.html",
                                      {"request": request, "user": user, "pending": pending,
                                       "current_year": datetime.datetime.utcnow().year})

@app.post("/admin/leave/update")
async def update_leave_status(request: Request,
                              leave_id: int = Form(...),
                              action: str = Form(...),
                              user: User = Depends(get_current_user),
                              db: Session = Depends(get_db)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave not found")

    leave.status = "Approved" if action == "approve" else "Rejected"
    db.commit()
    return RedirectResponse("/admin/leave_requests", status_code=303)

# ----------------------------------------
# MANAGER DASHBOARD
# ----------------------------------------

@app.get("/manager/dashboard", response_class=HTMLResponse)
async def manager_dashboard(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "manager": raise HTTPException(status_code=403)

    # 1. Projects in Manager's Department
    projects = db.query(Project).filter(Project.department == user.department).all()
    
    # 2. Leave Requests from Department Members
    # Join LeaveRequest with User to filter by User.department
    leave_requests = db.query(LeaveRequest).join(User).filter(
        User.department == user.department,
        User.id != user.id # Don't show own requests here
    ).all()

    # 3. Teams in Department
    teams = db.query(Team).filter(Team.department == user.department).all()

    # 4. Check if Manager is ALSO a Team Leader
    is_also_lead = db.query(Team).filter(Team.leader_id == user.id).first() is not None

    return templates.TemplateResponse("manager_dashboard.html", {
        "request": request,
        "user": user,
        "projects": projects,
        "leave_requests": leave_requests,
        "teams": teams,
        "is_also_lead": is_also_lead
    })

@app.post("/manager/create_team")
async def manager_create_team(
    name: str = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if user.role != "manager": raise HTTPException(status_code=403)
    
    # Manager can only create teams in THEIR department
    new_team = Team(name=name, department=user.department)
    db.add(new_team)
    db.commit()
    return RedirectResponse("/manager/dashboard", status_code=303)

@app.post("/manager/approve_leave")
async def manager_approve_leave(
    leave_id: int = Form(...),
    action: str = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if user.role != "manager": raise HTTPException(status_code=403)
    
    leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
    if leave:
        leave.status = "Approved" if action == "approve" else "Rejected"
        db.commit()
    return RedirectResponse("/manager/dashboard", status_code=303)

@app.post("/manager/create_project")
async def create_project(
    name: str = Form(...),
    description: str = Form(""),
    deadline: str = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if user.role != "manager": raise HTTPException(status_code=403)

    new_proj = Project(
        name=name,
        description=description,
        department=user.department,
        deadline=datetime.datetime.strptime(deadline, "%Y-%m-%d")
    )
    db.add(new_proj)
    db.commit()
    return RedirectResponse("/manager/dashboard", status_code=303)

# ----------------------------------------
# TEAM LEADER ROUTES (New Feature)
# ----------------------------------------

@app.get("/leader/dashboard", response_class=HTMLResponse)
async def leader_dashboard(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Allow Managers to access this if they are also leads, or standard Team Leads
    if user.role != "team_lead" and user.role != "manager": 
        raise HTTPException(status_code=403)
    
    # Get the team this user leads
    my_team = db.query(Team).filter(Team.leader_id == user.id).first()
    
    # Get projects involving this team (logic: find projects where team members are assigned)
    # Simplified: Get all projects in department for now
    projects = db.query(Project).filter(Project.department == user.department).all()

    return templates.TemplateResponse("leader_dashboard.html", {
        "request": request,
        "user": user,
        "team": my_team,
        "projects": projects
    })

@app.post("/leader/assign_task")
async def assign_task(
    project_id: int = Form(...),
    title: str = Form(...),
    deadline: str = Form(...),
    assign_to_employee_id: str = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Check permissions
    if user.role not in ["team_lead", "manager"]: raise HTTPException(status_code=403)

    # Create Task
    new_task = ProjectTask(
        project_id=project_id,
        title=title,
        deadline=datetime.datetime.strptime(deadline, "%Y-%m-%d"),
        status="pending"
    )
    db.add(new_task)
    db.commit() # Commit to get ID

    # Assign to User
    assignment = ProjectTaskAssignee(
        task_id=new_task.id,
        employee_id=assign_to_employee_id
    )
    db.add(assignment)
    db.commit()

    return RedirectResponse("/leader/dashboard", status_code=303)



# ----------------------------------------
# EMPLOYEE DASHBOARD 
# ----------------------------------------

@app.get("/employee", response_class=HTMLResponse)
async def employee_dashboard(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # ... (Your existing logic) ...
    total_hours = 0
    tasks = [] 
    return templates.TemplateResponse("employee/employee_dashboard.html", 
                                      {
                                        "request": request, 
                                        "user": user, 
                                        "total_hours": total_hours, 
                                        "tasks": tasks, 
                                        "current_year": 2026
                                        }
                                    )

#-----------------------------------------
#EMPLOYEE TEAM PAGE
#----------------------------------------

@app.get("/employee/team", response_class=HTMLResponse)
async def employee_team(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    led_teams = db.query(Team).filter(Team.leader_id == user.id).all()
    membership_records = db.query(TeamMember).filter(TeamMember.user_id == user.id).all()
    member_team_ids = [m.team_id for m in membership_records]
    member_teams = db.query(Team).filter(Team.id.in_(member_team_ids)).all()
    if user.current_team_id:
        primary_team = db.query(Team).filter(Team.id == user.current_team_id).first()
        if primary_team:
            member_teams.append(primary_team)
    all_teams_dict = {t.id: t for t in led_teams + member_teams}
    my_teams = list(all_teams_dict.values())

    return templates.TemplateResponse(
        "employee/employee_team.html",
        {
            "request": request,
            "user": user,
            "teams": my_teams  
        }
    )

#-----------------------------------------
#EMPLOYEE ATTENDANCE PAGE
#-----------------------------------------

@app.get("/employee/attendance", response_class=HTMLResponse)
async def employee_attendance_page(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    logs = db.query(Attendance).filter(
        Attendance.employee_id == user.employee_id
            ).order_by(Attendance.date.desc()).all()
    return templates.TemplateResponse("employee/employee_attendance.html",
                                      {"request": request, "user": user, "logs": logs,
                                       "current_year": datetime.datetime.utcnow().year})

#-----------------------------------------
#EMPLOYEE TASKS PAGE
#-----------------------------------------

@app.get("/employee/tasks", response_class=HTMLResponse)
async def employee_tasks_page(request: Request,
                              user: User = Depends(get_current_user),
                              db: Session = Depends(get_db),
                              filter: str = None):
    task_query = db.query(Task).filter(Task.user_id == user.employee_id)
    if filter in ["pending", "in-progress", "done"]:
        task_query = task_query.filter(Task.status == filter)
    tasks = task_query.order_by(Task.id.desc()).all()
    pending = db.query(Task).filter(Task.user_id == user.employee_id, Task.status == "pending").count()
    in_progress = db.query(Task).filter(Task.user_id == user.employee_id, Task.status == "in-progress").count()
    done = db.query(Task).filter(Task.user_id == user.employee_id, Task.status == "done").count()
    return templates.TemplateResponse("employee/employee_tasks.html",
                                      {"request": request, "user": user,
                                       "tasks": tasks,
                                       "pending": pending,
                                       "in_progress": in_progress,
                                       "done": done})

@app.post("/employee/tasks/add")
async def employee_add_task(title: str = Form(...), description: str = Form(""),
                            user: User = Depends(get_current_user),
                            db: Session = Depends(get_db)):
    new_task = Task(user_id=user.employee_id, title=title, description=description)
    db.add(new_task)
    db.commit()
    return RedirectResponse("/employee/tasks", status_code=303)

@app.post("/employee/tasks/update")
async def update_task(task_id: int = Form(...), status: str = Form(...),
                      user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user.employee_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.status = status
    db.commit()
    return RedirectResponse("/employee/tasks", status_code=303)

@app.post("/employee/tasks/delete")
async def delete_task(task_id: int = Form(...),
                      user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user.employee_id).first()
    if task:
        db.delete(task)
        db.commit()
    return RedirectResponse("/employee/tasks", status_code=303)

#----------------------------------------
#EMPLOYEE LEAVE PAGE
# ----------------------------------------

@app.get("/employee/leave", response_class=HTMLResponse)
async def employee_leave_page(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    leaves = db.query(LeaveRequest).filter(LeaveRequest.employee_id == user.employee_id).order_by(LeaveRequest.id.desc()).all()
    return templates.TemplateResponse("employee/employee_leave.html",
                                      {"request": request, "user": user,
                                       "leaves": leaves,
                                       "current_year": datetime.datetime.utcnow().year})

@app.post("/employee/leave/apply")
async def apply_leave(request: Request,
                      start_date: str = Form(...),
                      end_date: str = Form(...),
                      reason: str = Form(...),
                      user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    
    leave = LeaveRequest(employee_id=user.employee_id,
                         start_date=start_date,
                         end_date=end_date,
                         reason=reason)
    db.add(leave)
    db.commit()
    return RedirectResponse("/employee/leave", status_code=303)

#----------------------------------------
#EMPLOYEE PROFILE PAGE
#----------------------------------------

@app.get("/employee/profile", response_class=HTMLResponse)
async def employee_profile(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse("employee/employee_profile.html",
                                      {"request": request, "user": user,
                                       "current_year": datetime.datetime.utcnow().year})

@app.post("/employee/profile/update")
async def update_profile(
    request: Request,
    phone: str = Form(...),
    email: str = Form(...),
    address: str = Form(""),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user.phone = phone
    user.email = email
    user.address = address
    db.commit()
    return RedirectResponse(url="/employee/profile", status_code=303)

@app.get("/employee/team", response_class=HTMLResponse)
async def employee_team(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    team = None
    leader = None
    members = []

    # Case 1: User is a member of a team
    if user.current_team_id:
        team = db.query(Team).filter(Team.id == user.current_team_id).first()
    
    # Case 2: User IS the leader of a team (and might not have current_team_id set)
    if not team:
        team = db.query(Team).filter(Team.leader_id == user.id).first()

    if team:
        leader = team.leader # Uses the relationship defined in models
        members = team.members # Uses the relationship defined in models
        
        # Filter out the leader from the members list if they are in there
        if leader:
            members = [m for m in members if m.id != leader.id]

    return templates.TemplateResponse(
        "employee/employee_team.html",
        {
            "request": request,
            "user": user,
            "team": team,
            "leader": leader,
            "members": members
        }
    )

#-----------------------------------------
#EMPLOYEE PAYSLIPS PAGE
#----------------------------------------

@app.get("/employee/payslips", response_class=HTMLResponse)
async def employee_payslips_page(request: Request,
                                 month: int = None, year: int = None,
                                 user: User = Depends(get_current_user),
                                 db: Session = Depends(get_db)):
    current_year = datetime.datetime.utcnow().year
    if not month or not year:
        return templates.TemplateResponse("employee/employee_payslips.html",
                                          {"request": request, "user": user,
                                           "computed": False,
                                           "current_year": current_year,
                                           "month": current_year,
                                           "year": current_year})
    # Use the shared payroll engine
    payroll = calculate_monthly_payroll(db, user, month, year)

    # Keep total_hours for compatibility/diagnostics
    start_date = datetime.datetime(year, month, 1)
    end_date = datetime.datetime(year, month, monthrange(year, month)[1], 23, 59, 59)
    total_hours = db.query(func.sum(Attendance.duration)).filter(
        Attendance.employee_id == user.employee_id,
        Attendance.entry_time >= start_date,
        Attendance.entry_time <= end_date
    ).scalar() or 0

    # Map payroll values for the template (backwards-compatible keys)
    gross_salary = payroll.get("base_salary")
    leave_deduction = payroll.get("leave_deduction")
    tax_deduction = payroll.get("tax")
    net_salary = payroll.get("net_salary")

    return templates.TemplateResponse("employee/employee_payslips.html",
                                      {"request": request, "user": user,
                                       "computed": True,
                                       "total_hours": total_hours,
                                       "gross_salary": gross_salary,
                                       "tax_deduction": tax_deduction,
                                       "leave_deduction": leave_deduction,
                                       "net_salary": net_salary,
                                       "payroll": payroll,
                                       "current_year": current_year,
                                       "month": month,
                                       "year": year})

#----------------------------------------
# RFID ATTENDANCE API
#----------------------------------------

@app.post("/api/attendance")
async def record_attendance(
    rfid_tag: str,
    room_no: str,
    location_name: str,
    db: Session = Depends(get_db)
):
    GATE_ROOM_NO = "77"
    
    # 1. Find User
    user = db.query(User).filter(User.rfid_tag == rfid_tag, User.is_active == True).first()
    
    if not user:
        db.add(UnknownRFID(rfid_tag=rfid_tag, location=location_name))
        db.commit()
        return {"status": "unknown_rfid"}

    today = datetime.date.today()
    now = datetime.datetime.utcnow()

    # --- NEW: WRITE TO DETAILED LOG ---
    new_log = AttendanceLog(
        user_id=user.id,
        entry_time=now,
        location_name=location_name,
        room_no=room_no
    )
    db.add(new_log)

    # --- NEW: UPDATE DAILY SUMMARY ---
    daily_record = db.query(AttendanceDaily).filter(
        AttendanceDaily.user_id == user.id,
        AttendanceDaily.date == today
    ).first()

    if not daily_record:
        # First swipe of the day
        status = "PRESENT"
        # Late logic (e.g., after 9:30 AM)
        if now.time() > datetime.time(9, 30):
            status = "LATE"
        
        daily_record = AttendanceDaily(
            user_id=user.id,
            date=today,
            status=status,
            check_in_time=now.time()
        )
        db.add(daily_record)
    
    # --- EXISTING LOGIC (For Dashboard Views) ---
    # (Kept for backward compatibility with your existing dashboards)
    
    open_gate = db.query(Attendance).filter(Attendance.employee_id == user.employee_id, Attendance.room_no == GATE_ROOM_NO, Attendance.exit_time == None).first()
    open_block = db.query(Attendance).filter(Attendance.employee_id == user.employee_id, Attendance.room_no != GATE_ROOM_NO, Attendance.exit_time == None).first()
    
    status_msg = "entry"

    if room_no == GATE_ROOM_NO:
        if open_block:
            open_block.exit_time = now
            open_block.duration = round((now - open_block.entry_time).total_seconds() / 3600, 2)
        if open_gate:
            open_gate.exit_time = now
            open_gate.duration = round((now - open_gate.entry_time).total_seconds() / 3600, 2)
            status_msg = "gate_exited"
        else:
            db.add(Attendance(employee_id=user.employee_id, date=today, entry_time=now, status="PRESENT", location_name=location_name, room_no=GATE_ROOM_NO))
            status_msg = "gate_entered"
    else:
        # Block logic
        if not open_gate:
             db.add(Attendance(employee_id=user.employee_id, date=today, entry_time=now, status="PRESENT", location_name="Main Gate", room_no=GATE_ROOM_NO))
        
        if open_block and open_block.room_no == room_no:
             # Re-swiping same room (exit)
             open_block.exit_time = now
             open_block.duration = round((now - open_block.entry_time).total_seconds() / 3600, 2)
             status_msg = "block_exited"
        else:
            if open_block:
                open_block.exit_time = now
                open_block.duration = round((now - open_block.entry_time).total_seconds() / 3600, 2)
            
            db.add(Attendance(employee_id=user.employee_id, date=today, entry_time=now, status="PRESENT", location_name=location_name, room_no=room_no))
            status_msg = "block_entered"

    db.commit()
    return {"status": status_msg}

#----------------------------------------
#API FOR PERSONS IN BLOCK
#----------------------------------------

@app.get("/api/block_persons")
async def get_block_persons(location: str, room: str, db: Session = Depends(get_db)):
    attendances = db.query(Attendance).filter(
        Attendance.location_name == location, 
        Attendance.room_no == room, 
        Attendance.exit_time.is_(None)
    ).all()
    persons = [{"name": a.user.name} for a in attendances]
    return {"persons": persons}

#----------------------------------------
#API FOR BLOCKS STATUS
#----------------------------------------

@app.get("/api/blocks")
async def get_blocks(db: Session = Depends(get_db)):
    blocks = (
        db.query(
            Attendance.location_name,
            Attendance.room_no,
            func.count(Attendance.id).label("count")
        )
        .filter(
            Attendance.status == "PRESENT",
            Attendance.date == datetime.date.today()
        )
        .group_by(
            Attendance.location_name,
            Attendance.room_no
        )
        .all()
    )
    return {
        "blocks": [
            {
                "location": b.location_name,
                "room": b.room_no,
                "count": b.count
            }
            for b in blocks
        ]
    }

#----------------------------------------
#API FOR ABSENTEES
#----------------------------------------

@app.get("/api/absentees")
async def get_absentees(department: str, db: Session = Depends(get_db)):
    # Get all active employees in the department
    all_employees = db.query(User).filter(User.department == department, User.is_active == True).all()
    # Get employees currently checked in (present)
    present_employee_ids = db.query(Attendance.employee_id).filter(Attendance.exit_time.is_(None)).distinct().all()
    present_ids = {p[0] for p in present_employee_ids}
    # Absentees: Employees not in present_ids
    absentees = [emp for emp in all_employees if emp.employee_id not in present_ids]
    return {"absentees": [{"name": emp.name, "employee_id": emp.employee_id} for emp in absentees]}

#----------------------------------------
#API FOR EMPLOYEE LOGS
#----------------------------------------

@app.get("/api/employee_logs")
async def employee_logs(employee_id: str, db: Session = Depends(get_db)):
    logs = db.query(Attendance).filter(
        Attendance.employee_id == employee_id
    ).order_by(Attendance.entry_time.desc()).limit(10).all()
    return {
        "logs": [
            {
                "in": a.entry_time.strftime("%H:%M"),
                "out": a.exit_time.strftime("%H:%M") if a.exit_time else "-",
                "room": a.room_no,
                "location": a.location_name
            }
            for a in logs
        ]
    }

#----------------------------------------
#API FOR LEAVE COUNT
#----------------------------------------

@app.get("/api/leave_count")
async def leave_count(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
    pending = db.query(LeaveRequest).filter(LeaveRequest.status == "Pending").count()
    return {"count": pending}

#----------------------------------------
#API FOR MONTH HOURS
#----------------------------------------

@app.get("/api/month-hours")
async def month_hours(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    now = datetime.datetime.utcnow()
    first_day = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    total = db.query(func.sum(Attendance.duration)).filter(
        Attendance.employee_id == user.employee_id,
        Attendance.entry_time >= first_day
    ).scalar() or 0
    return {"total_hours": round(total, 2)}

#----------------------------------------
# SCHEDULER SETUP
# ----------------------------------------


def mark_absent():
    """Mark users with no AttendanceDaily record today as ABSENT.

    This runs as a scheduled job (23:59 daily).
    """
    db = SessionLocal()
    try:
        today = datetime.date.today()

        all_users = db.query(User).filter(User.is_active == True).all()
        present_rows = db.query(AttendanceDaily.user_id).filter(
            AttendanceDaily.date == today
        ).all()

        present_ids = {p[0] for p in present_rows}

        for u in all_users:
            if u.id not in present_ids:
                # Ensure we don't duplicate if another process added it concurrently
                exists = db.query(AttendanceDaily).filter(
                    AttendanceDaily.user_id == u.id,
                    AttendanceDaily.date == today
                ).first()
                if not exists:
                    db.add(AttendanceDaily(
                        user_id=u.id,
                        date=today,
                        status="ABSENT"
                    ))

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def scheduler_loop():
    while True:
        auto_assign_leaders()
        time.sleep(300)

@app.on_event("startup")
def start_scheduler():
    scheduler.add_job(auto_assign_leaders, 'interval', minutes=5, id="leader_job")
    # Schedule daily absent marking at 23:59
    scheduler.add_job(mark_absent, 'cron', hour=23, minute=59, id="mark_absent_job")
    scheduler.start()

@app.on_event("shutdown")
def shutdown_scheduler():
    scheduler.shutdown()
