-- Migration 001: Add expiry, GST, and Razorpay columns to existing tables
-- Run manually: sqlite3 database/payments.db < migrations/001_add_expiry_and_gst.sql
-- Or for PostgreSQL: psql $DATABASE_URL < migrations/001_add_expiry_and_gst.sql

ALTER TABLE transactions ADD COLUMN IF NOT EXISTS expires_at   TEXT;
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS payment_ref  TEXT;
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS gst_number   TEXT;
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS hsn_code     TEXT;
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS razorpay_id  TEXT;

ALTER TABLE vendors      ADD COLUMN IF NOT EXISTS gstin         TEXT;
ALTER TABLE vendors      ADD COLUMN IF NOT EXISTS password_hash TEXT;
ALTER TABLE vendors      ADD COLUMN IF NOT EXISTS jwt_secret    TEXT;
