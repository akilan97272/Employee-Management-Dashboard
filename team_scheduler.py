from datetime import datetime, time, date, timedelta
from sqlalchemy.orm import Session
from database import SessionLocal
from models import Team, User, LeaveRequest, Attendance


GRACE_TIME = time(9, 30)

def auto_assign_leaders():
    now = datetime.now().time()
    if now < GRACE_TIME:
        return

    db: Session = SessionLocal()

    try:
        teams = db.query(Team).all()

        for team in teams:
            leader = team.leader
            if not leader:
                continue

            # 1️⃣ Check leave
            on_leave = db.query(LeaveRequest).filter(
                LeaveRequest.employee_id == leader.employee_id,
                LeaveRequest.status == "Approved",
                LeaveRequest.start_date <= date.today(),
                LeaveRequest.end_date >= date.today()
            ).first()

            if on_leave:
                leader_absent = True
            else:
                # 2️⃣ Check attendance
                attendance = db.query(Attendance).filter(
                    Attendance.employee_id == leader.employee_id,
                    Attendance.entry_time >= datetime.combine(date.today(), time(0, 0))
                ).first()

                leader_absent = attendance is None

            if not leader_absent:
                continue

            # 3️⃣ Find eligible replacement
            candidate = (
                db.query(User)
                .filter(
                    User.department == team.department,
                    User.can_manage == True,
                    User.is_active == True
                )
                .all()
            )

            if not candidate:
                continue

            # Load balancing
            candidate.sort(
                key=lambda u: db.query(User)
                .filter(User.current_team_id == u.current_team_id)
                .count()
            )

            new_leader = candidate[0]

            # 4️⃣ Assign new leader
            team.leader_id = new_leader.id
            new_leader.active_leader = True

            db.commit()

    finally:
        db.close()



# def auto_exit_gate(db: Session):
#     now = datetime.utcnow().year

#     expired_gates = db.query(Attendance).filter(
#         Attendance.room_no == "GATE",
#         Attendance.exit_time == None,
#         Attendance.entry_time <= now - timedelta(minutes=30)
#     ).all()

#     for gate in expired_gates:
#         # Check if user entered any room after gate entry
#         room_used = db.query(Attendance).filter(
#             Attendance.employee_id == gate.employee_id,
#             Attendance.room_no != "GATE",
#             Attendance.entry_time >= gate.entry_time
#         ).first()

#         if not room_used:
#             gate.exit_time = now

#     db.commit()
