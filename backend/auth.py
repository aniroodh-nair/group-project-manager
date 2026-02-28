"""Authentication and authorization utilities"""
import json
import os
from functools import wraps
from flask import session, redirect, url_for, request

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
USERS_FILE = os.path.join(DATA_DIR, "users.json")


def load_users():
    """Load all users from JSON"""
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def save_users(users):
    """Save users to JSON"""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(USERS_FILE, "w", encoding="utf-8") as file:
        json.dump(users, file, indent=2)


def register_user(email, password, name, role, department=""):
    """Register a new user"""
    users = load_users()
    if email in users:
        return False, "Email already registered"
    
    users[email] = {
        "email": email,
        "password": password,  # In production, use proper hashing!
        "name": name,
        "role": role,  # "student", "faculty", "hod", "admin"
        "department": department
    }
    save_users(users)
    return True, "User registered successfully"


def login_user(email, password):
    """Authenticate user"""
    users = load_users()
    if email not in users:
        return False, "Email not found"
    
    if users[email]["password"] != password:
        return False, "Invalid password"
    
    return True, users[email]


def require_login(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_email" not in session:
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated_function


def require_role(*roles):
    """Decorator to require specific roles"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if "user_email" not in session:
                return redirect(url_for("login_page"))
            
            user_role = session.get("user_role")
            if user_role not in roles:
                return "Access Denied", 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def get_current_user():
    """Get current logged-in user from session"""
    if "user_email" not in session:
        return None
    return {
        "email": session.get("user_email"),
        "name": session.get("user_name"),
        "role": session.get("user_role")
    }
