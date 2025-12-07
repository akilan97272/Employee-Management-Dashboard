from fastapi import FastAPI, Depends, HTTPException, Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import SessionLocal, get_db, engine, Base
from models import User, Attendance, RemovedEmployee, UnknownRFID, Room, Department
from auth import authenticate_user, hash_password
from sqlalchemy import func
import random
import string
import datetime
from typing import Optional

Base.metadata.create_all(bind=engine)

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


# Session middleware (simple in-memory for demo; use proper sessions in prod)
from starlette.middleware.sessions import SessionMiddleware
app.add_middleware(SessionMiddleware, secret_key="your-secret-key")


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

  
@app.get("/employee", response_class=HTMLResponse)
async def employee_dashboard(request: Request, user: User = Depends(get_current_user)):
    if user.role not in ["employee", "admin"]:
        raise HTTPException(status_code=403, detail="Access denied")
    return templates.TemplateResponse("employee_dashboard.html", {"request": request, "user": user})

@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
    # Fetch data for dashboard (dynamic blocks)
    blocks_data = db.query(Attendance.location_name, Attendance.room_no,
                           func.count(Attendance.id).label('count')).filter(Attendance.exit_time.is_(None)).group_by(
        Attendance.location_name, Attendance.room_no).all()
    employees = db.query(User).filter(User.is_active == True).all()
    unknown_rfids = db.query(UnknownRFID).all()
    admins = db.query(User).filter(User.role == "admin").all()  # For listing admins
    removed_employees = db.query(RemovedEmployee).all()  # For verification
    return templates.TemplateResponse("admin_dashboard.html", {
        "request": request, "user": user, "blocks": blocks_data, "employees": employees, "unknown_rfids": unknown_rfids,
        "admins": admins, "removed_employees": removed_employees
    })

@app.post("/api/attendance")
async def record_attendance(rfid_tag: str, room_no: str, location_name: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.rfid_tag == rfid_tag, User.is_active == True).first()
    if not user:
        # Unknown RFID
        unknown = UnknownRFID(rfid_tag=rfid_tag, location=location_name)
        db.add(unknown)
        db.commit()
        return {"status": "unknown_rfid_logged"}

    # Find or create room
    room = db.query(Room).filter(Room.room_no == room_no, Room.location_name == location_name).first()
    if not room:
        room_id = f"R{room_no}"
        room = Room(room_id=room_id, room_no=room_no, location_name=location_name)
        db.add(room)
        db.commit()

    # Traverse from bottom (latest) to find open entry
    latest_attendance = db.query(Attendance).filter(Attendance.rfid_tag == rfid_tag,
                                                    Attendance.exit_time.is_(None)).order_by(
        Attendance.id.desc()).first()
    if latest_attendance:
        # Exit
        latest_attendance.exit_time = datetime.datetime.utcnow()
        duration = (latest_attendance.exit_time - latest_attendance.entry_time).total_seconds() / 3600
        latest_attendance.duration = duration
    else:
        # Entry
        attendance = Attendance(employee_id=user.employee_id, rfid_tag=rfid_tag, entry_time=datetime.datetime.utcnow(),
                                room_no=room_no, location_name=location_name, room_id=room.room_id)
        db.add(attendance)
    db.commit()
    return {"status": "recorded"}

@app.get("/admin/payroll")
async def payroll(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
    payroll_data = []
    employees = db.query(User).filter(User.is_active == True).all()
    for emp in employees:
        total_hours = db.query(func.sum(Attendance.duration)).filter(Attendance.employee_id == emp.employee_id).scalar() or 0
        salary = total_hours * 20  # $20/hour
        payroll_data.append({"name": emp.name, "total_hours": total_hours, "salary": salary})
    return templates.TemplateResponse("payroll.html", {"request": request, "payroll": payroll_data})

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
    blocks = db.query(Attendance.location_name, Attendance.room_no, func.count(Attendance.id).label('count')).filter(Attendance.exit_time.is_(None)).group_by(Attendance.location_name, Attendance.room_no).all()
    return {"blocks": [{"location": b.location_name, "room": b.room_no, "count": b.count} for b in blocks]}

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
  
        initial_admin = User(employee_id="admin001", name="Initial Admin", email="admin@example.com", rfid_tag="admin-rfid",
                             role="admin", department="IT", password_hash=hash_password("admin123"))
        db.add(initial_admin)
        db.commit()
    db.close()
   
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
 
