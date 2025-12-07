# ===============================
# TeamSync — Final Clean main.py
# ===============================
from fastapi import FastAPI, Depends, HTTPException, Request, Form, Body
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import func
import datetime
import random
import string
from typing import Optional

from database import SessionLocal, get_db, engine, Base
from models import User, Attendance, RemovedEmployee, UnknownRFID, Room, Department, Task
from auth import authenticate_user, hash_password


# ------------------------------------------------------------
# BASE INIT
# ------------------------------------------------------------
Base.metadata.create_all(bind=engine)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# ------------------------------------------------------------
# SESSION + NO-CACHE MIDDLEWARE
# ------------------------------------------------------------
from starlette.middleware.sessions import SessionMiddleware
app.add_middleware(SessionMiddleware, secret_key="team-sync-secret")

from starlette.middleware.base import BaseHTTPMiddleware

class NoCache(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        resp = await call_next(request)
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp

app.add_middleware(NoCache)


# ------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------
def get_current_user(request: Request, db: Session = Depends(get_db)):
    uid = request.session.get("user_id")
    if not uid:
        raise HTTPException(401, "Not authenticated")
    user = db.query(User).filter(User.id == uid).first()
    if not user:
        raise HTTPException(401, "Invalid session")
    return user


# ------------------------------------------------------------
# LOGIN / LOGOUT
# ------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
async def login(request: Request,
                username: str = Form(...),
                password: str = Form(...),
                db: Session = Depends(get_db)):

    user = authenticate_user(db, username, password)
    if not user:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Invalid credentials"
        })

    request.session["user_id"] = user.id

    if user.role == "admin":
        return RedirectResponse("/admin/select_dashboard", 303)
    return RedirectResponse("/employee", 303)


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", 303)


# ------------------------------------------------------------
# ADMIN — Dashboard Selector
# ------------------------------------------------------------
@app.get("/admin/select_dashboard", response_class=HTMLResponse)
async def admin_select_dashboard(request: Request,
                                 user: User = Depends(get_current_user)):
    if user.role != "admin":
        raise HTTPException(403)
    return templates.TemplateResponse("admin_select_dashboard.html", {
        "request": request,
        "user": user,
        "current_year": datetime.datetime.utcnow().year
    })


# ------------------------------------------------------------
# ADMIN — Command Center (main dashboard)
# ------------------------------------------------------------
@app.get("/admin", response_class=HTMLResponse)
async def admin_command_center(request: Request,
                               user: User = Depends(get_current_user),
                               db: Session = Depends(get_db)):
    if user.role != "admin":
        raise HTTPException(403)

    blocks = db.query(
        Attendance.location_name,
        Attendance.room_no,
        func.count(Attendance.id).label("count")
    ).filter(Attendance.exit_time.is_(None)).group_by(
        Attendance.location_name, Attendance.room_no
    ).all()

    employees = db.query(User).filter(User.is_active == True).all()

    unknown = db.query(UnknownRFID).all()

    return templates.TemplateResponse("admin_dashboard.html", {
        "request": request,
        "user": user,
        "blocks": blocks,
        "employees": employees,
        "unknown_rfids": unknown,
        "current_year": datetime.datetime.utcnow().year
    })


# ------------------------------------------------------------
# ADMIN — Attendance Page
# ------------------------------------------------------------
@app.get("/admin/attendance", response_class=HTMLResponse)
async def admin_attendance(request: Request,
                           user: User = Depends(get_current_user),
                           db: Session = Depends(get_db)):
    if user.role != "admin":
        raise HTTPException(403)

    recent = db.query(Attendance).order_by(
        Attendance.entry_time.desc()
    ).limit(50).all()

    return templates.TemplateResponse("admin_attendance.html", {
        "request": request,
        "user": user,
        "recent": recent,
        "current_year": datetime.datetime.utcnow().year
    })


# ------------------------------------------------------------
# ADMIN — Manage Employees Page
# ------------------------------------------------------------
@app.get("/admin/manage_employees", response_class=HTMLResponse)
async def admin_manage(request: Request,
                       user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    if user.role != "admin":
        raise HTTPException(403)

    emps = db.query(User).filter(User.is_active == True).all()

    return templates.TemplateResponse("admin_manage.html", {
        "request": request,
        "user": user,
        "employees": emps,
        "current_year": datetime.datetime.utcnow().year
    })


# ------------------------------------------------------------
# ADMIN — Unknown RFID
# ------------------------------------------------------------
@app.get("/admin/unknown_rfid", response_class=HTMLResponse)
async def admin_unknown(request: Request,
                        user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):

    if user.role != "admin":
        raise HTTPException(403)

    records = db.query(UnknownRFID).all()

    return templates.TemplateResponse("admin_unknown.html", {
        "request": request,
        "user": user,
        "unknown_rfids": records,
        "current_year": datetime.datetime.utcnow().year
    })


# ------------------------------------------------------------
# ADMIN — Payroll
# ------------------------------------------------------------
@app.get("/admin/payroll", response_class=HTMLResponse)
async def admin_payroll(request: Request,
                        user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    if user.role != "admin":
        raise HTTPException(403)

    data = []
    for emp in db.query(User).filter(User.is_active == True).all():
        total_hours = db.query(
            func.sum(Attendance.duration)
        ).filter(Attendance.employee_id == emp.employee_id).scalar() or 0

        data.append({
            "name": emp.name,
            "total_hours": round(total_hours, 2),
            "salary": round(total_hours * 200)
        })

    return templates.TemplateResponse("payroll.html", {
        "request": request,
        "payroll": data,
        "user": user,
        "current_year": datetime.datetime.utcnow().year
    })


# ------------------------------------------------------------
# ADMIN — Add Employee
# ------------------------------------------------------------
@app.post("/admin/add_employee")
async def add_employee(name: str = Form(...),
                       email: str = Form(...),
                       rfid_tag: str = Form(...),
                       role: str = Form(...),
                       department: str = Form(...),
                       user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):

    if user.role != "admin":
        raise HTTPException(403)

    prefix = {"IT": "2261", "HR": "2262", "Finance": "2263"}.get(department, "2260")
    existing = db.query(User).filter(User.employee_id.like(f"{prefix}%")).all()
    used = []

    for u in existing:
        try:
            used.append(int(u.employee_id[len(prefix):]))
        except:
            pass

    next_id = max(used) + 1 if used else 1
    employee_id = f"{prefix}{next_id:03d}"

    pw = ''.join(random.choices(string.ascii_letters + string.digits, k=8))

    u = User(
        employee_id=employee_id,
        name=name,
        email=email,
        rfid_tag=rfid_tag,
        role=role,
        department=department,
        password_hash=hash_password(pw),
        is_active=True
    )
    db.add(u)
    db.commit()

    return RedirectResponse("/admin/manage_employees", 303)


# ------------------------------------------------------------
# ADMIN — Remove Employee
# ------------------------------------------------------------
@app.post("/admin/remove_employee")
async def remove_employee(employee_id: str = Form(...),
                          user: User = Depends(get_current_user),
                          db: Session = Depends(get_db)):

    if user.role != "admin":
        raise HTTPException(403)

    emp = db.query(User).filter(User.employee_id == employee_id).first()
    if not emp:
        raise HTTPException(404)

    removed = RemovedEmployee(
        employee_id=emp.employee_id,
        name=emp.name,
        email=emp.email,
        rfid_tag=emp.rfid_tag,
        role=emp.role,
        department=emp.department,
        removed_at=datetime.datetime.utcnow()
    )
    db.add(removed)
    db.delete(emp)
    db.commit()

    return RedirectResponse("/admin/manage_employees", 303)


# ------------------------------------------------------------
# EMPLOYEE — Dashboard
# ------------------------------------------------------------
@app.get("/employee", response_class=HTMLResponse)
async def emp_dash(request: Request,
                   user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):

    total_hours = db.query(func.sum(Attendance.duration)).filter(
        Attendance.employee_id == user.employee_id
    ).scalar() or 0

    tasks = db.query(Task).filter(Task.user_id == user.employee_id).all()

    return templates.TemplateResponse("employee_dashboard.html", {
        "request": request,
        "user": user,
        "total_hours": round(total_hours, 2),
        "tasks": tasks,
        "current_year": datetime.datetime.utcnow().year
    })


# ------------------------------------------------------------
# EMPLOYEE — Attendance
# ------------------------------------------------------------
@app.get("/employee/attendance", response_class=HTMLResponse)
async def emp_attendance(request: Request,
                         user: User = Depends(get_current_user),
                         db: Session = Depends(get_db)):

    logs = db.query(Attendance).filter(
        Attendance.employee_id == user.employee_id
    ).order_by(Attendance.entry_time.desc()).all()

    return templates.TemplateResponse("employee_attendance.html", {
        "request": request,
        "user": user,
        "entries": logs,
        "current_year": datetime.datetime.utcnow().year
    })


# ------------------------------------------------------------
# EMPLOYEE — Tasks
# ------------------------------------------------------------
@app.get("/employee/tasks", response_class=HTMLResponse)
async def tasks_page(request: Request,
                     user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):

    tasks = db.query(Task).filter(Task.user_id == user.employee_id).all()
    return templates.TemplateResponse("employee_task.html", {
        "request": request,
        "user": user,
        "tasks": tasks,
        "current_year": datetime.datetime.utcnow().year
    })


@app.post("/employee/tasks/add")
async def add_task(title: str = Form(...),
                   description: str = Form(""),
                   user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):

    t = Task(user_id=user.employee_id, title=title, description=description)
    db.add(t)
    db.commit()
    return RedirectResponse("/employee/tasks", 303)


@app.post("/employee/tasks/delete")
async def delete_task(id: int = Form(...),
                      user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):

    t = db.query(Task).filter(Task.id == id, Task.user_id == user.employee_id).first()
    if t:
        db.delete(t)
        db.commit()

    return RedirectResponse("/employee/tasks", 303)


# ------------------------------------------------------------
# EMPLOYEE — Profile
# ------------------------------------------------------------
@app.get("/employee/profile", response_class=HTMLResponse)
async def emp_profile(request: Request,
                      user: User = Depends(get_current_user)):

    return templates.TemplateResponse("employee_profile.html", {
        "request": request,
        "user": user,
        "current_year": datetime.datetime.utcnow().year
    })


@app.post("/employee/profile/update")
async def update_profile(name: str = Form(...),
                         email: str = Form(...),
                         user: User = Depends(get_current_user),
                         db: Session = Depends(get_db)):

    user.name = name
    user.email = email
    db.commit()

    return RedirectResponse("/employee/profile", 303)


# ------------------------------------------------------------
# EMPLOYEE — Payslips
# ------------------------------------------------------------
@app.get("/employee/payslips", response_class=HTMLResponse)
async def payslips(request: Request,
                   user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):

    total_hours = db.query(func.sum(Attendance.duration)).filter(
        Attendance.employee_id == user.employee_id
    ).scalar() or 0

    salary = round(total_hours * 200)

    return templates.TemplateResponse("employee_payslips.html", {
        "request": request,
        "user": user,
        "salary": salary,
        "total_hours": round(total_hours, 2),
        "current_year": datetime.datetime.utcnow().year
    })


# ------------------------------------------------------------
# RFID — API Endpoint
# ------------------------------------------------------------
from pydantic import BaseModel

class AttendancePayload(BaseModel):
    rfid_tag: str
    room_no: str
    location_name: str


@app.post("/api/attendance")
async def rfid_event(payload: AttendancePayload,
                     db: Session = Depends(get_db)):

    user = db.query(User).filter(
        User.rfid_tag == payload.rfid_tag,
        User.is_active == True
    ).first()

    if not user:
        db.add(UnknownRFID(rfid_tag=payload.rfid_tag, location=payload.location_name))
        db.commit()
        return {"status": "unknown_rfid_logged"}

    # Create room if new
    room = db.query(Room).filter(
        Room.room_no == payload.room_no,
        Room.location_name == payload.location_name
    ).first()

    if not room:
        room = Room(room_id=f"R{payload.room_no}",
                    room_no=payload.room_no,
                    location_name=payload.location_name)
        db.add(room)
        db.commit()

    # Check if entry exists
    open_entry = db.query(Attendance).filter(
        Attendance.rfid_tag == payload.rfid_tag,
        Attendance.exit_time.is_(None)
    ).order_by(Attendance.id.desc()).first()

    if open_entry:
        open_entry.exit_time = datetime.datetime.utcnow()
        open_entry.duration = (open_entry.exit_time - open_entry.entry_time).total_seconds() / 3600
        db.commit()
        return {"status": "exit_recorded"}

    new = Attendance(
        employee_id=user.employee_id,
        rfid_tag=user.rfid_tag,
        entry_time=datetime.datetime.utcnow(),
        room_no=payload.room_no,
        location_name=payload.location_name,
        room_id=room.room_id
    )
    db.add(new)
    db.commit()
    return {"status": "entry_recorded"}


# ------------------------------------------------------------
# INITIAL ADMIN CREATION
# ------------------------------------------------------------
@app.on_event("startup")
def create_admin():
    db = SessionLocal()
    if not db.query(User).filter(User.role == "admin").first():
        admin = User(
            employee_id="ADMIN001",
            name="System Admin",
            email="admin@example.com",
            rfid_tag="adminrfid",
            department="IT",
            role="admin",
            password_hash=hash_password("admin123"),
            is_active=True
        )
        db.add(admin)
        db.commit()
    db.close()
