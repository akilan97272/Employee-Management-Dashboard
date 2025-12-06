from fastapi import FastAPI, Depends, HTTPException, Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
import datetime
import random
import string

from database import SessionLocal, get_db, engine, Base
from models import User, Attendance, RemovedEmployee, UnknownRFID, Room, Department, Task
from auth import authenticate_user, hash_password

# Create all tables (including Task)
Base.metadata.create_all(bind=engine)

# FastAPI app
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# SESSION MIDDLEWARE
from starlette.middleware.sessions import SessionMiddleware
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


# ----------------------------------------
# LOGIN ROUTES
# ----------------------------------------

@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = authenticate_user(db, username, password)
    if not user:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"})

    request.session["user_id"] = user.id

    if user.role == "admin":
        return RedirectResponse("/admin/select_dashboard", status_code=303)
    else:
        return RedirectResponse("/employee", status_code=303)


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)


# ----------------------------------------
# ADMIN SELECT DASHBOARD
# ----------------------------------------

@app.get("/admin/select_dashboard", response_class=HTMLResponse)
async def admin_choice(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse("admin_select_dashboard.html", {"request": request, "user": user})


# ----------------------------------------
# EMPLOYEE DASHBOARD + PAGES
# ----------------------------------------

@app.get("/employee", response_class=HTMLResponse)
async def employee_dashboard(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    total_hours = db.query(func.sum(Attendance.duration)).filter(
        Attendance.employee_id == user.employee_id
    ).scalar() or 0

    return templates.TemplateResponse(
        "employee_dashboard.html",
        {
            "request": request,
            "user": user,
            "total_hours": round(total_hours, 2),
            "current_year": datetime.datetime.utcnow().year
        }
    )


@app.get("/employee/attendance", response_class=HTMLResponse)
async def employee_attendance_page(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    logs = db.query(Attendance).filter(
        Attendance.employee_id == user.employee_id
    ).order_by(Attendance.entry_time.desc()).all()

    return templates.TemplateResponse("employee_attendance.html",
                                      {"request": request, "user": user, "logs": logs,
                                       "current_year": datetime.datetime.utcnow().year})


@app.get("/employee/tasks", response_class=HTMLResponse)
async def employee_tasks_page(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tasks = db.query(Task).filter(Task.user_id == user.employee_id).all()
    return templates.TemplateResponse("employee_tasks.html",
                                      {"request": request, "user": user, "tasks": tasks,
                                       "current_year": datetime.datetime.utcnow().year})


@app.post("/employee/tasks/add")
async def employee_add_task(request: Request, title: str = Form(...), description: str = Form(""),
                            user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    new_task = Task(user_id=user.employee_id, title=title, description=description)
    db.add(new_task)
    db.commit()
    return RedirectResponse("/employee/tasks", status_code=303)


@app.post("/employee/tasks/update")
async def update_task(task_id: int = Form(...), status: str = Form(...),
                      user: User = Depends(get_current_user), db: Session = Depends(get_db)):

    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user.employee_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.status = status
    db.commit()

    return RedirectResponse("/employee/tasks", status_code=303)


@app.get("/employee/profile", response_class=HTMLResponse)
async def employee_profile(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse("employee_profile.html",
                                      {"request": request, "user": user,
                                       "current_year": datetime.datetime.utcnow().year})


@app.get("/employee/payslips", response_class=HTMLResponse)
async def employee_payslips_page(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    total_hours = db.query(func.sum(Attendance.duration)).filter(
        Attendance.employee_id == user.employee_id
    ).scalar() or 0

    salary = total_hours * 200  # ₹200/hr

    return templates.TemplateResponse("employee_payslips.html",
                                      {"request": request, "user": user,
                                       "salary": salary, "total_hours": round(total_hours, 2),
                                       "current_year": datetime.datetime.utcnow().year})


# ----------------------------------------
# ADMIN DASHBOARD + FEATURES
# ----------------------------------------

@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):

    blocks = db.query(
        Attendance.location_name,
        Attendance.room_no,
        func.count(Attendance.id).label("count")
    ).filter(Attendance.exit_time.is_(None)).group_by(
        Attendance.location_name, Attendance.room_no
    ).all()

    employees = db.query(User).filter(User.is_active == True).all()
    unknown = db.query(UnknownRFID).all()

    return templates.TemplateResponse("admin_dashboard.html",
                                      {"request": request, "user": user, "blocks": blocks,
                                       "employees": employees, "unknown_rfids": unknown,
                                       "current_year": datetime.datetime.utcnow().year})


@app.get("/admin/payroll", response_class=HTMLResponse)
async def admin_payroll(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    payroll_data = []

    employees = db.query(User).filter(User.is_active == True).all()
    for emp in employees:
        total_hours = db.query(func.sum(Attendance.duration)).filter(
            Attendance.employee_id == emp.employee_id
        ).scalar() or 0

        salary = total_hours * 200  # ₹200/hr
        payroll_data.append({"name": emp.name, "total_hours": round(total_hours, 2), "salary": salary})

    return templates.TemplateResponse("admin_payroll.html",
                                      {"request": request, "user": user,
                                       "payroll": payroll_data,
                                       "current_year": datetime.datetime.utcnow().year})


# ----------------------------------------
# CREATE INITIAL ADMIN
# ----------------------------------------

@app.on_event("startup")
def create_initial_admin():
    db = SessionLocal()
    if not db.query(User).filter(User.role == "admin").first():
        admin = User(
            employee_id="ADMIN001",
            name="System Admin",
            email="admin@example.com",
            rfid_tag="admin-tag",
            role="admin",
            password_hash=hash_password("admin123"),
            department="IT"
        )
        db.add(admin)
        db.commit()
    db.close()
