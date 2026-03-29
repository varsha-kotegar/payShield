"""
config.py — Central configuration loaded from environment variables.
All modules import from here instead of reading os.environ directly.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Flask
FLASK_ENV        = os.getenv("FLASK_ENV", "development")
SECRET_KEY       = os.getenv("SECRET_KEY", "dev-secret-change-in-prod")
PORT             = int(os.getenv("PORT", 5000))
IS_PROD          = FLASK_ENV == "production"

# JWT
JWT_SECRET       = os.getenv("JWT_SECRET", "dev-jwt-secret-change-in-prod")
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", 24))

# Key management
KEY_BACKEND      = os.getenv("KEY_BACKEND", "file")   # file | env | aws_kms
PRIVATE_KEY_PATH = os.getenv("PRIVATE_KEY_PATH", "keys/private_key.pem")
PUBLIC_KEY_PATH  = os.getenv("PUBLIC_KEY_PATH",  "keys/public_key.pem")
PRIVATE_KEY_PEM  = os.getenv("PRIVATE_KEY_PEM")       # used when KEY_BACKEND=env
PUBLIC_KEY_PEM   = os.getenv("PUBLIC_KEY_PEM")
KMS_KEY_ID       = os.getenv("KMS_KEY_ID")
AWS_REGION       = os.getenv("AWS_REGION", "ap-south-1")

# Database
DB_BACKEND       = os.getenv("DB_BACKEND", "sqlite")  # sqlite | postgresql
SQLITE_PATH      = os.getenv("SQLITE_PATH", "database/payments.db")
DATABASE_URL     = os.getenv("DATABASE_URL")

# Receipt
RECEIPT_EXPIRY_MINUTES = int(os.getenv("RECEIPT_EXPIRY_MINUTES", 15))

# Razorpay
RAZORPAY_KEY_ID      = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET  = os.getenv("RAZORPAY_KEY_SECRET", "")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")

# GST / Business
BUSINESS_NAME    = os.getenv("BUSINESS_NAME",    "PayShield Payments")
BUSINESS_GSTIN   = os.getenv("BUSINESS_GSTIN",   "29AABCP1234A1ZK")
BUSINESS_ADDRESS = os.getenv("BUSINESS_ADDRESS", "Belagavi, Karnataka")
BUSINESS_PAN     = os.getenv("BUSINESS_PAN",     "AABCP1234A")
BUSINESS_EMAIL   = os.getenv("BUSINESS_EMAIL",   "billing@payshield.in")
BUSINESS_PHONE   = os.getenv("BUSINESS_PHONE",   "+91-9876543210")
