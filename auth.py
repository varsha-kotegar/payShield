"""
auth.py — JWT vendor authentication.
Vendors log in with vendor_id + password and receive a signed JWT.
All /api/generate calls require a valid JWT in the Authorization header.
"""
import jwt, hashlib, os, secrets
from datetime import datetime, timezone, timedelta
from functools import wraps
from flask import request, jsonify
from config import JWT_SECRET, JWT_EXPIRY_HOURS

ALGORITHM = "HS256"

# ── Helpers ──────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """SHA-256 hash of password (in production use bcrypt)."""
    return hashlib.sha256(password.encode()).hexdigest()

def create_token(vendor_id: str, vendor_name: str) -> str:
    payload = {
        "vendor_id":   vendor_id,
        "vendor_name": vendor_name,
        "iat":         datetime.now(timezone.utc),
        "exp":         datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)

def decode_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])

# ── Decorator ────────────────────────────────────────────────────────────────

def require_auth(f):
    """
    Decorator: validates JWT from Authorization: Bearer <token> header.
    Injects vendor_id and vendor_name into the wrapped function as kwargs.
    Public routes (customer payment page, verify) skip this decorator.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or malformed Authorization header"}), 401
        token = auth_header[7:]
        try:
            payload = decode_token(token)
            kwargs["vendor_id"]   = payload["vendor_id"]
            kwargs["vendor_name"] = payload["vendor_name"]
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Session expired — please log in again"}), 401
        except jwt.InvalidTokenError as e:
            return jsonify({"error": f"Invalid token: {str(e)}"}), 401
        return f(*args, **kwargs)
    return decorated

# ── Default vendor passwords (dev only) ─────────────────────────────────────
# In production these are stored as hashed values in the vendors table.
DEFAULT_PASSWORDS = {
    "V001": hash_password("ravi123"),
    "V002": hash_password("meena123"),
    "V003": hash_password("krishna123"),
    "V004": hash_password("suresh123"),
    "V005": hash_password("priya123"),
}
