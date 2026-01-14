from fastapi import FastAPI, Depends, HTTPException, Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import SessionLocal, get_db, engine, Base
from models import User, Attendance, RemovedEmployee, UnknownRFID, Room, Department, Task, LeaveRequest
from auth import authenticate_user, hash_password
from sqlalchemy import func
import random
import string
import datetime
from typing import Optional
from calendar import monthrange
from team_scheduler import auto_assign_leaders
from threading import Thread
import time
from database import get_team_info


Base.metadata.create_all(bind=engine)

# FastAPI app
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# Session middleware (simple in-memory for demo; use proper sessions in prod)
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
        return RedirectResponse("/admin", status_code=303)
    else:
        return RedirectResponse("/employee", status_code=303)

    request.session["user_id"] = user.id

    if user.role == "admin":
        return RedirectResponse("/admin/select_dashboard", status_code=303)
    else:
        return RedirectResponse("/employee", status_code=303)


 
@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)

  
@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
    # Fetch data for dashboard (dynamic blocks)
    blocks_data = db.query(
        Attendance.location_name,
        Attendance.room_no,
        func.count(Attendance.id).label("count")
    ).filter(
        Attendance.status == "PRESENT",
        Attendance.date == datetime.date.today()
    ).group_by(
        Attendance.location_name,
        Attendance.room_no
    ).all()
    employees = db.query(User).filter(User.is_active == True).all()
    unknown_rfids = db.query(UnknownRFID).all()
    admins = db.query(User).filter(User.role == "admin").all()  # For listing admins
    removed_employees = db.query(RemovedEmployee).all()  # For verification
    return templates.TemplateResponse("admin_dashboard.html", {
        "request": request, "user": user, "blocks": blocks_data, "employees": employees, "unknown_rfids": unknown_rfids,
        "admins": admins, "removed_employees": removed_employees
    })

@app.post("/api/attendance")
async def record_attendance(
    rfid_tag: str,
    room_no: str,
    location_name: str,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(
        User.rfid_tag == rfid_tag,
        User.is_active == True
    ).first()

    if not user:
        db.add(UnknownRFID(rfid_tag=rfid_tag, location=location_name))
        db.commit()
        return {"status": "unknown_rfid"}

    today = datetime.date.today()
    now = datetime.datetime.utcnow()

    attendance = db.query(Attendance).filter(
        Attendance.employee_id == user.employee_id,
        Attendance.date == today
    ).first()

    # FIRST SCAN → ENTRY
    if not attendance:
        attendance = Attendance(
            employee_id=user.employee_id,
            date=today,
            entry_time=now,
            status="PRESENT",
            location_name=location_name,
            room_no=room_no
        )
        db.add(attendance)
        db.commit()
        return {"status": "checked_in"}

    # SECOND SCAN → EXIT
    if attendance.entry_time and not attendance.exit_time:
        attendance.exit_time = now
        attendance.duration = round(
            (attendance.exit_time - attendance.entry_time).total_seconds() / 3600,
            2
        )
        db.commit()
        return {"status": "checked_out", "hours": attendance.duration}

    return {"status": "already_checked_out"}


@app.post("/admin/add_employee")
async def add_employee(request: Request, name: str = Form(...), email: str = Form(...), rfid_tag: str = Form(...),
                       role: str = Form(...), department: str = Form(...), user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    # Generate employee_id
    prefix = {"IT": "2261", "HR": "2262", "Finance": "2263"}.get(department, "2260")
    existing_ids = [int(u.employee_id[4:]) for u in db.query(User).filter(User.employee_id.like(f"{prefix}%")).all()]
    next_id = max(existing_ids) + 1 if existing_ids else 1
    employee_id = f"{prefix}{next_id:03d}"

    # Generate password
    password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    password_hash = hash_password(password)

    new_user = User(employee_id=employee_id, name=name, email=email, rfid_tag=rfid_tag, role=role,
                    department=department, password_hash=password_hash)
    db.add(new_user)
    db.commit()
    return {"employee_id": employee_id, "password": password}

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

@app.post("/admin/update_employee")
async def update_employee(
    request: Request,
    employee_id: str = Form(...),
    name: str = Form(...),
    email: str = Form(...),
    department: str = Form(...),
    role: str = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    emp = db.query(User).filter(User.employee_id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    emp.name = name
    emp.email = email
    emp.department = department
    emp.role = role

    db.commit()
    return RedirectResponse("/admin/manage_employees", status_code=303)

@app.post("/admin/update_salary")
async def update_salary(
    employee_id: str = Form(...),
    basic_salary: float = Form(...),
    allowances: float = Form(...),
    deductions: float = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
    
    emp = db.query(User).filter(User.employee_id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    emp.basic_salary = basic_salary
    emp.allowances = allowances
    emp.deductions = deductions
    db.commit()
    
    return RedirectResponse("/admin/payroll", status_code=303)

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
        return templates.TemplateResponse("employee_details.html", {"request": request, "error": "Employee not found"})
    # Calculate total time (sum durations)
    total_time = db.query(Attendance).filter(Attendance.employee_id == emp.employee_id).with_entities(
        Attendance.duration).all()
    total_hours = sum(d[0] for d in total_time if d[0])
    return templates.TemplateResponse("employee_details.html",
                                      {"request": request, "employee": emp, "total_hours": total_hours})

@app.get("/api/block_persons")
async def get_block_persons(location: str, room: str, db: Session = Depends(get_db)):
    attendances = db.query(Attendance).join(User, Attendance.employee_id == User.employee_id).filter(Attendance.location_name == location, Attendance.room_no == room, Attendance.exit_time.is_(None)).all()
    persons = [{"name": a.user.name} for a in attendances]
    return {"persons": persons}

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


# Admin-only features (merged from super_admin)
@app.post("/admin/add_admin")
async def add_admin(request: Request, name: str = Form(...), email: str = Form(...), rfid_tag: str = Form(...),
                    department: str = Form(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    # Validate department exists
    dept = db.query(Department).filter(Department.name == department).first()
    if not dept:
        raise HTTPException(status_code=400, detail="Department does not exist")

    # Generate employee_id
    prefix = {"IT": "2261", "HR": "2262", "Finance": "2263"}.get(department, "2260")
    existing_ids = [int(u.employee_id[4:]) for u in db.query(User).filter(User.employee_id.like(f"{prefix}%")).all()]
    next_id = max(existing_ids) + 1 if existing_ids else 1
    employee_id = f"{prefix}{next_id:03d}"

    # Generate password
    password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    password_hash = hash_password(password)

    new_admin = User(employee_id=employee_id, name=name, email=email, rfid_tag=rfid_tag, role="admin",
                     department=department, password_hash=password_hash)
    db.add(new_admin)
    db.commit()
    return {"employee_id": employee_id, "password": password, "message": "Admin added successfully"}

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

@app.get("/api/leave_count")
async def leave_count(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    pending = db.query(LeaveRequest).filter(LeaveRequest.status == "Pending").count()
    return {"count": pending}

@app.get("/api/month-hours")
async def month_hours(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    now = datetime.datetime.utcnow()
    first_day = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    total = db.query(func.sum(Attendance.duration)).filter(
        Attendance.employee_id == user.employee_id,
        Attendance.entry_time >= first_day
    ).scalar() or 0

    return {"total_hours": round(total, 2)}

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

# Create initial admin on startup
   

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


    tasks = db.query(Task).filter(Task.user_id == user.employee_id).all()

    return templates.TemplateResponse(
        "employee_dashboard.html",
        {
            "request": request,
            "user": user,
            "total_hours": round(total_hours, 2),
            "tasks": tasks,
            "leave_balance": 0,
            "current_year": datetime.datetime.utcnow().year
        }
    )


@app.get("/employee/attendance", response_class=HTMLResponse)
async def employee_attendance_page(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    logs = db.query(Attendance).filter(
        Attendance.employee_id == user.employee_id
            ).order_by(Attendance.date.desc()).all()


    return templates.TemplateResponse("employee_attendance.html",
                                      {"request": request, "user": user, "logs": logs,
                                       "current_year": datetime.datetime.utcnow().year})


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

    return templates.TemplateResponse("employee_tasks.html",
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


@app.get("/employee/leave", response_class=HTMLResponse)
async def employee_leave_page(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    leaves = db.query(LeaveRequest).filter(LeaveRequest.employee_id == user.employee_id).order_by(LeaveRequest.id.desc()).all()
    return templates.TemplateResponse("employee_leave.html",
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


@app.get("/employee/profile", response_class=HTMLResponse)
async def employee_profile(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse("employee_profile.html",
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


@app.get("/employee/payslips", response_class=HTMLResponse)
async def employee_payslips_page(request: Request,
                                 month: int = None, year: int = None,
                                 user: User = Depends(get_current_user),
                                 db: Session = Depends(get_db)):

    current_year = datetime.datetime.utcnow().year

    if not month or not year:
        return templates.TemplateResponse("employee_payslips.html",
                                          {"request": request, "user": user,
                                           "computed": False,
                                           "current_year": current_year,
                                           "month": current_year,
                                           "year": current_year})

    start_date = datetime.datetime(year, month, 1)
    end_date = datetime.datetime(year, month, monthrange(year, month)[1], 23, 59, 59)

    total_hours = db.query(func.sum(Attendance.duration)).filter(
        Attendance.employee_id == user.employee_id,
        Attendance.entry_time >= start_date,
        Attendance.entry_time <= end_date
    ).scalar() or 0

    gross_salary = round(total_hours * 200, 2)

    # Leave count
    leave_count = db.query(func.count(LeaveRequest.id)).filter(
        LeaveRequest.employee_id == user.employee_id,
        LeaveRequest.status == "approved",
        LeaveRequest.start_date >= start_date,
        LeaveRequest.end_date <= end_date
    ).scalar() or 0

    leave_deduction = round(leave_count * 500, 2)   # ₹500 fine per leave

    tax_deduction = round(gross_salary * 0.10, 2)

    net_salary = round(gross_salary - leave_deduction - tax_deduction, 2)

    return templates.TemplateResponse("employee_payslips.html",
                                      {"request": request, "user": user,
                                       "computed": True,
                                       "total_hours": total_hours,
                                       "gross_salary": gross_salary,
                                       "tax_deduction": tax_deduction,
                                       "leave_deduction": leave_deduction,
                                       "net_salary": net_salary,
                                       "current_year": current_year,
                                       "month": month,
                                       "year": year})


# ----------------------------------------
# ADMIN DASHBOARD + FEATURES
# ----------------------------------------
@app.get("/admin/payroll", response_class=HTMLResponse)
async def admin_payroll(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    employees = db.query(User).filter(User.is_active == True).all()
    payroll_data = []

    for emp in employees:
        total_hours = db.query(func.sum(Attendance.duration)).filter(
            Attendance.employee_id == emp.employee_id
        ).scalar() or 0

        salary = total_hours * 200  # ₹200/hour

        payroll_data.append({
            "name": emp.name,
            "employee_id": emp.employee_id,
            "total_hours": round(total_hours, 2),
            "salary": round(salary, 2)
        })

    total_salary = sum(p["salary"] for p in payroll_data)
    avg_salary = round(total_salary / len(payroll_data), 2) if payroll_data else 0
    max_salary = max((p["salary"] for p in payroll_data), default=0)

    return templates.TemplateResponse(
        "payroll.html",
        {
            "request": request,
            "user": user,
            "payroll": payroll_data,
            "total_salary": total_salary,
            "avg_salary": avg_salary,
            "max_salary": max_salary,
            "current_year": datetime.datetime.utcnow().year
        }
    )


@app.get("/admin/attendance", response_class=HTMLResponse)
async def admin_attendance(
    request: Request,
    search: Optional[str] = None,
    date: Optional[str] = None,
    department: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    query = db.query(Attendance).join(
        User,
        Attendance.employee_id == User.employee_id
    )

    if search:
        query = query.filter(
            (User.employee_id.like(f"%{search}%")) |
            (User.name.ilike(f"%{search}%"))
        )

    if department:
        query = query.filter(User.department == department)

    if date:
        try:
            filter_date = datetime.datetime.strptime(date, "%Y-%m-%d").date()
            query = query.filter(Attendance.date == filter_date)
        except ValueError:
            pass

    records = query.order_by(
        Attendance.date.desc(),
        Attendance.entry_time.desc()
    ).limit(100).all()

    return templates.TemplateResponse(
        "admin_attendance.html",
        {
            "request": request,
            "user": user,
            "records": records,
            "search": search,
            "date": date,
            "department": department,
        }
    )


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

    return templates.TemplateResponse("admin_manage.html",
                                      {"request": request,
                                       "user": user,
                                       "employees": employees,
                                       "search": search,
                                       "current_year": datetime.datetime.utcnow().year})


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
        "admin_unknown.html",
        {
            "request": request,
            "user": user,
            "search": search,
            "unknown_rfids": unknown_rfids,
            "current_year": datetime.datetime.utcnow().year
        }
    )

@app.post("/admin/resolve_rfid")
async def resolve_rfid(request: Request, rfid_tag: str = Form(...), db: Session = Depends(get_db)):
    db.query(UnknownRFID).filter(UnknownRFID.rfid_tag == rfid_tag).delete()
    db.commit()
    return RedirectResponse("/admin/unknown_rfid", status_code=303)


@app.get("/admin/leave_requests", response_class=HTMLResponse)
async def admin_leave_page(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
    pending = db.query(LeaveRequest).order_by(LeaveRequest.id.desc()).all()
    return templates.TemplateResponse("admin_leave_requests.html",
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



def scheduler_loop():
    while True:
        auto_assign_leaders()
        time.sleep(300)  # every 5 mins

@app.on_event("startup")
def start_scheduler():
    Thread(target=scheduler_loop, daemon=True).start()

templates = Jinja2Templates(directory="templates")

@app.get("/teamsync")
def team_sync(request: Request, db=Depends(get_db), user=Depends(get_current_user)):
    team_data = get_team_info(db, user.id)
    return templates.TemplateResponse(
        "teamsync.html",
        {
            "request": request,
            "team": team_data,
            "user": user
        }
    )