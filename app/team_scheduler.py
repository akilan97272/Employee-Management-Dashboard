from datetime import datetime, time, date
from sqlalchemy.orm import Session
<<<<<<< HEAD:team_scheduler.py
from database import SessionLocal
from models import Team, User, LeaveRequest, Attendance
from sqlalchemy import func
=======
from app.database import SessionLocal
from app.models import Team, User, LeaveRequest, Attendance
>>>>>>> sethu's-touch:app/team_scheduler.py

# Set the time by which the leader must be present
GRACE_TIME = time(9, 30)

def auto_assign_leaders():
    now_time = datetime.now().time()
    
    # Only run this logic after the grace time
    if now_time < GRACE_TIME:
        return

    db: Session = SessionLocal()

    try:
        teams = db.query(Team).all()

        for team in teams:
            current_leader = team.leader
            
            # If team has no leader, skip (or assign one immediately)
            if not current_leader:
                continue

            leader_absent = False

            # 1️⃣ Check if Leader is on approved leave
            on_leave = db.query(LeaveRequest).filter(
                LeaveRequest.employee_id == current_leader.employee_id,
                LeaveRequest.status == "Approved",
                LeaveRequest.start_date <= date.today(),
                LeaveRequest.end_date >= date.today()
            ).first()

            if on_leave:
                leader_absent = True
            else:
                # 2️⃣ Check if Leader has swiped in today
                attendance = db.query(Attendance).filter(
                    Attendance.employee_id == current_leader.employee_id,
                    Attendance.entry_time >= datetime.combine(date.today(), time(0, 0))
                ).first()

                if not attendance:
                    leader_absent = True

            # If leader is present, move to next team
            if not leader_absent:
                continue

            print(f"Leader {current_leader.name} is absent. Reassigning Team {team.name}...")

            # 3️⃣ Find eligible replacements (Same Dept, Can Manage, Is Active)
            # We exclude the current absent leader
            candidates = db.query(User).filter(
                User.department == team.department,
                User.can_manage == True,
                User.is_active == True,
                User.id != current_leader.id
            ).all()

            # Filter candidates: Only pick those who are PRESENT today
            present_candidates = []
            for candidate in candidates:
                is_present = db.query(Attendance).filter(
                    Attendance.employee_id == candidate.employee_id,
                    Attendance.entry_time >= datetime.combine(date.today(), time(0, 0))
                ).first()
                if is_present:
                    present_candidates.append(candidate)

            if not present_candidates:
                print("No present candidates found to take over.")
                continue

            # 4️⃣ Load Balancing: Find candidate with lowest number of current team members
            # We need to count how many people belong to the team this candidate CURRENTLY leads
            
            candidate_counts = []
            for cand in present_candidates:
                # Find the team this candidate leads (if any)
                cand_team = db.query(Team).filter(Team.leader_id == cand.id).first()
                count = 0
                if cand_team:
                    count = len(cand_team.members)
                candidate_counts.append((cand, count))

            # Sort by count (ascending)
            candidate_counts.sort(key=lambda x: x[1])

            # The best candidate is the first one
            new_leader = candidate_counts[0][0]

            # 5️⃣ Assign new leader
            # IMPORTANT: This temporarily updates the Team table. 
            # In a real app, you might want a 'temporary_leader_id' column instead.
            team.leader_id = new_leader.id
            
            print(f"Team {team.name} reassigned to {new_leader.name}")
            db.commit()

    except Exception as e:
        print(f"Scheduler Error: {e}")
        db.rollback()
    finally:
        db.close()