import bcrypt
from sqlalchemy.orm import Session
from app.models import User

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def authenticate_user(db: Session, username: str, password: str):
    user = db.query(User).filter(User.employee_id == username).first()
    if user and verify_password(password, user.password_hash):
        return user
    return None