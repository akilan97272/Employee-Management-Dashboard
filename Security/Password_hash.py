"""
PASSWORD HASHING & VERIFICATION MODULE
=====================================

This module handles secure password hashing and verification using Argon2 via passlib.
Passwords are NEVER stored in plain text in the database.

SECURITY FEATURES:
- Uses Argon2 algorithm with automatic salt generation
- Passwords are hashed when created (signup/initialization)
- Original passwords are discarded after hashing
- Hashed passwords cannot be reversed to get original password
- Each password hash is unique even for the same password
- Verification compares plain password with stored hash

FLOW:
- hash_password() creates Argon2 hash before storage.
- verify_password() checks login against stored hash.

WHY:
- Prevents storing raw passwords and reduces breach impact.

HOW:
- Argon2 hashing with per-password salt.

USAGE:
1. When creating user account:
   from Security.Password_hash import hash_password
   hashed = hash_password(user_input_password)
   user.password_hash = hashed  # Store this in database

2. When logging in:
   from Security.Password_hash import verify_password
   if verify_password(user_input_password, stored_hash):
       # Password is correct, authenticate user
"""

from passlib.context import CryptContext
from passlib.exc import UnknownHashError

# Create password context with Argon2 + bcrypt (verify legacy hashes)
pwd_context = CryptContext(
    schemes=["argon2", "bcrypt"],
    deprecated="auto"
)

def hash_password(password: str) -> str:
    """
    Hash a plain text password using Argon2.
    
    Args:
        password (str): Plain text password from user input
        
    Returns:
        str: Hashed password (safe to store in database)
        
    Example:
        hashed = hash_password("MySecurePassword123!")
        # Result: $argon2id$v=19$m=65536,t=3,p=4$...
    """
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain text password against a stored hash.
    Used during login to authenticate users.
    
    Args:
        plain_password (str): Plain text password from login form
        hashed_password (str): Hashed password from database
        
    Returns:
        bool: True if password is correct, False otherwise
        
    Example:
        if verify_password(form_password, user.password_hash):
            print("Login successful!")
        else:
            print("Invalid password!")
    """
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except UnknownHashError:
        return False