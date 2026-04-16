# """
# Authentication routes — TOKEN-BASED (no cookies, no sessions).
# Login returns a token → frontend stores in localStorage → sends in every request header.
# """
# from flask_mail import Mail, Message

# mail = Mail()
# import random
# import string
# import secrets
# from datetime import datetime, timedelta
# from flask import Blueprint, request, jsonify
# import bcrypt
# from database.db import get_db
"""
Authentication routes — TOKEN-BASED (no cookies, no sessions).
Login returns a token → frontend stores in localStorage → sends in every request header.
"""

import random
import string
import secrets
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
from flask_mail import Message
import bcrypt
from database.db import get_db

auth_bp = Blueprint("auth", __name__)

# mail instance will be injected by app.py
mail = None

# In-memory token store: { token: username }
active_tokens = {}

# auth_bp = Blueprint("auth", __name__)

# # In-memory token store: { token: username }
# active_tokens = {}


def _generate_otp(length=6):
    return "".join(random.choices(string.digits, k=length))

def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()

def _check_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())

def _get_token_from_request():
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None

def get_current_user():
    token = _get_token_from_request()
    if not token:
        return None
    return active_tokens.get(token)


@auth_bp.route("/register", methods=["POST"])
def register():
    data     = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    email    = data.get("email", "").strip()
    password = data.get("password", "").strip()

    if not username or not email or not password:
        return jsonify({"success": False, "message": "username, email and password are required."}), 400
    if len(password) < 6:
        return jsonify({"success": False, "message": "Password must be at least 6 characters."}), 400

    hashed = _hash_password(password)
    db = get_db()
    try:
        db.execute("INSERT INTO users(username, email, password) VALUES(?,?,?)", (username, email, hashed))
        db.commit()
        return jsonify({"success": True, "message": "Registered successfully! Please login."})
    except Exception:
        return jsonify({"success": False, "message": "Username or email already exists."}), 409
    finally:
        db.close()


@auth_bp.route("/login", methods=["POST"])
def login():
    data     = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        return jsonify({"success": False, "message": "Username and password are required."}), 400

    db   = get_db()
    user = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    db.close()

    if not user or not _check_password(password, user["password"]):
        return jsonify({"success": False, "message": "Invalid username or password."}), 401

    token = secrets.token_hex(32)
    active_tokens[token] = username

    return jsonify({"success": True, "message": "Login successful.", "username": username, "token": token})


@auth_bp.route("/logout", methods=["POST"])
def logout():
    token = _get_token_from_request()
    if token and token in active_tokens:
        del active_tokens[token]
    return jsonify({"success": True, "message": "Logged out."})


@auth_bp.route("/me", methods=["GET"])
def me():
    username = get_current_user()
    if not username:
        return jsonify({"success": False, "message": "Not logged in."}), 401
    return jsonify({"success": True, "username": username})


# @auth_bp.route("/forgot-password", methods=["POST"])
# def forgot_password():
#     data     = request.get_json(silent=True) or {}
#     username = data.get("username", "").strip()

#     if not username:
#         return jsonify({"success": False, "message": "Username is required."}), 400

#     db   = get_db()
#     user = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()

#     if not user:
#         db.close()
#         return jsonify({"success": True, "message": "If this account exists, an OTP has been generated.", "otp": None})

#     otp        = _generate_otp()
#     expires_at = datetime.now() + timedelta(minutes=10)

#     db.execute("DELETE FROM otp_store WHERE username=?", (username,))
#     db.execute("INSERT INTO otp_store(username, otp, expires_at) VALUES(?,?,?)", (username, otp, expires_at.isoformat()))
#     db.commit()
#     db.close()

#     print(f"[OTP] User '{username}' OTP: {otp}  (expires {expires_at})")

#     return jsonify({"success": True, "message": "OTP generated. (Demo mode: OTP returned in response.)", "otp": otp})
@auth_bp.route("/forgot-password", methods=["POST"])
def forgot_password():
    data     = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()

    if not username:
        return jsonify({"success": False, "message": "Username is required."}), 400

    db   = get_db()
    user = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()

    if not user:
        db.close()
        return jsonify({"success": True, "message": "If this account exists, an OTP has been sent to your email."})

    otp        = _generate_otp()
    expires_at = datetime.now() + timedelta(minutes=10)
    email      = user["email"]   # fetch registered email from DB

    db.execute("DELETE FROM otp_store WHERE username=?", (username,))
    db.execute("INSERT INTO otp_store(username, otp, expires_at) VALUES(?,?,?)",
               (username, otp, expires_at.isoformat()))
    db.commit()
    db.close()

    try:
        msg = Message(
            subject="Your Password Reset OTP",
            recipients=[email],
            body=(
                f"Hello {username},\n\n"
                f"Your OTP for password reset is: {otp}\n\n"
                f"This OTP expires in 10 minutes.\n\n"
                f"If you didn't request this, ignore this email."
            )
        )
        mail.send(msg)
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")
        return jsonify({"success": False, "message": "Failed to send OTP email. Try again later."}), 500

    # Do NOT return the OTP in the response
    return jsonify({"success": True, "message": "OTP sent to your registered email."})


@auth_bp.route("/verify-otp", methods=["POST"])
def verify_otp():
    data         = request.get_json(silent=True) or {}
    username     = data.get("username", "").strip()
    otp          = data.get("otp", "").strip()
    new_password = data.get("new_password", "").strip()

    if not username or not otp or not new_password:
        return jsonify({"success": False, "message": "username, otp and new_password are required."}), 400
    if len(new_password) < 6:
        return jsonify({"success": False, "message": "New password must be at least 6 characters."}), 400

    db  = get_db()
    row = db.execute("SELECT * FROM otp_store WHERE username=? ORDER BY id DESC LIMIT 1", (username,)).fetchone()

    if not row:
        db.close()
        return jsonify({"success": False, "message": "No OTP found. Request a new one."}), 400
    if row["otp"] != otp:
        db.close()
        return jsonify({"success": False, "message": "Invalid OTP."}), 400
    if datetime.now() > datetime.fromisoformat(row["expires_at"]):
        db.execute("DELETE FROM otp_store WHERE username=?", (username,))
        db.commit()
        db.close()
        return jsonify({"success": False, "message": "OTP has expired. Request a new one."}), 400

    hashed = _hash_password(new_password)
    db.execute("UPDATE users SET password=? WHERE username=?", (hashed, username))
    db.execute("DELETE FROM otp_store WHERE username=?", (username,))
    db.commit()
    db.close()

    return jsonify({"success": True, "message": "Password reset successfully! Please login."})
