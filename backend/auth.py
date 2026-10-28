"""User Authentication & Profile Management.
Local, secure credential hashing and persistent user profiles.
"""
import json
import hashlib
import os
import uuid
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
USERS_FILE = DATA / "users.json"
SESSIONS_FILE = DATA / "sessions.json"

def _hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    if not salt:
        salt = uuid.uuid4().hex[:16]
    hashed = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return hashed, salt

def _load_users() -> dict:
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not USERS_FILE.exists():
        # Seed initial demo account
        demo_salt = "blu_demo_salt_99"
        demo_hash, _ = _hash_password("password123", demo_salt)
        seed = {
            "demo_learner": {
                "id": "usr_demo12345",
                "username": "demo_learner",
                "email": "demo@blu.ai",
                "name": "Alex Learner",
                "password_hash": demo_hash,
                "salt": demo_salt,
                "language": "en",
                "level": "beginner",
                "created_at": int(time.time()),
                "xp": 350,
                "level_num": 3,
                "streak_days": 4,
                "quizzes_taken": 3,
                "badges": ["First Lesson", "Honest Scholar (Anti-Cheat Master)", "Polyglot Explorer"],
                "history": [
                    {
                        "timestamp": int(time.time()) - 86400,
                        "lesson_id": "course-python-loops",
                        "lesson_title": "Python Loops & Iteration",
                        "score": 2,
                        "total": 2,
                        "percent": 100,
                        "strikes": 0,
                        "time_taken_sec": 32,
                        "earned_xp": 180,
                        "integrity_status": "Clean (Zero Tab Switches)"
                    }
                ]
            }
        }
        USERS_FILE.write_text(json.dumps(seed, indent=2, ensure_ascii=False), encoding="utf-8")
        return seed
    try:
        return json.loads(USERS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _save_users(users: dict):
    USERS_FILE.write_text(json.dumps(users, indent=2, ensure_ascii=False), encoding="utf-8")

def _load_sessions() -> dict:
    if not SESSIONS_FILE.exists():
        return {}
    try:
        return json.loads(SESSIONS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _save_sessions(sessions: dict):
    SESSIONS_FILE.write_text(json.dumps(sessions, indent=2), encoding="utf-8")

def register_user(username: str, email: str, password: str, name: str = "", language: str = "en", level: str = "beginner") -> dict:
    username = username.strip().lower()
    email = email.strip().lower()
    
    if len(username) < 3:
        raise ValueError("Username must be at least 3 characters.")
    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters.")
    if not email or "@" not in email:
        raise ValueError("Please provide a valid email address.")

    users = _load_users()
    if username in users:
        raise ValueError(f"Username '{username}' is already taken.")
    
    for u in users.values():
        if u.get("email") == email:
            raise ValueError(f"Email '{email}' is already registered. Please sign in.")

    pw_hash, salt = _hash_password(password)
    user_id = f"usr_{uuid.uuid4().hex[:10]}"
    
    user_record = {
        "id": user_id,
        "username": username,
        "email": email,
        "name": name.strip() or username.capitalize(),
        "password_hash": pw_hash,
        "salt": salt,
        "language": language,
        "level": level,
        "created_at": int(time.time()),
        "xp": 100,
        "level_num": 1,
        "streak_days": 1,
        "quizzes_taken": 0,
        "badges": ["New Explorer"],
        "history": []
    }
    users[username] = user_record
    _save_users(users)

    # Generate Session
    token = f"blu_tok_{uuid.uuid4().hex}"
    sessions = _load_sessions()
    sessions[token] = username
    _save_sessions(sessions)

    # Sanitize user record
    safe_user = {k: v for k, v in user_record.items() if k not in ("password_hash", "salt")}
    return {"token": token, "user": safe_user}

def login_user(username_or_email: str, password: str) -> dict:
    ident = username_or_email.strip().lower()
    users = _load_users()

    found_user = None
    for u in users.values():
        if u["username"].lower() == ident or u["email"].lower() == ident:
            found_user = u
            break

    if not found_user:
        raise ValueError("Invalid username or password.")

    check_hash, _ = _hash_password(password, found_user["salt"])
    if check_hash != found_user["password_hash"]:
        raise ValueError("Invalid username or password.")

    token = f"blu_tok_{uuid.uuid4().hex}"
    sessions = _load_sessions()
    sessions[token] = found_user["username"]
    _save_sessions(sessions)

    safe_user = {k: v for k, v in found_user.items() if k not in ("password_hash", "salt")}
    return {"token": token, "user": safe_user}

def get_current_user(token: str | None) -> dict | None:
    if not token:
        return None
    sessions = _load_sessions()
    username = sessions.get(token)
    if not username:
        return None
    users = _load_users()
    user = users.get(username)
    if not user:
        return None
    return {k: v for k, v in user.items() if k not in ("password_hash", "salt")}

def update_user_progress(token: str | None, progress_data: dict) -> dict:
    user = get_current_user(token)
    if not user:
        return progress_data

    users = _load_users()
    username = user["username"]
    rec = users[username]

    for k, v in progress_data.items():
        if k == "xp":
            rec["xp"] = rec.get("xp", 0) + int(v)
            rec["level_num"] = max(1, rec["xp"] // 100 + 1)
        elif k == "history" and isinstance(v, list):
            rec["history"] = (rec.get("history", []) + v)[-30:]
        elif k == "badges" and isinstance(v, list):
            rec["badges"] = list(set(rec.get("badges", []) + v))
        elif k in ("quizzes_taken", "streak_days", "language", "level"):
            rec[k] = v

    users[username] = rec
    _save_users(users)
    return {k: v for k, v in rec.items() if k not in ("password_hash", "salt")}

