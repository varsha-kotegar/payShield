<div align="center">

# 🛡️ PayShield

### Secure Digital Payment Receipt Verification System

*Cryptographically signed UPI receipts that make fake payment screenshots mathematically impossible.*

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-2.3+-000000?style=flat&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![RSA-2048](https://img.shields.io/badge/Encryption-RSA--2048-brightgreen?style=flat)](https://en.wikipedia.org/wiki/RSA_(cryptosystem))
[![License](https://img.shields.io/badge/License-MIT-yellow?style=flat)](LICENSE)

</div>

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Cryptographic Design](#cryptographic-design)
- [Project Structure](#project-structure)
- [Quick Start (Development)](#quick-start-development)
- [Configuration (.env)](#configuration-env)
- [API Reference](#api-reference)
- [Production Deployment](#production-deployment)
- [Key Management Backends](#key-management-backends)
- [Database Backends](#database-backends)
- [Razorpay Integration](#razorpay-integration)
- [PWA — Install on Mobile](#pwa--install-on-mobile)
- [AWS KMS Setup](#aws-kms-setup)
- [PostgreSQL Migration](#postgresql-migration)
- [Exhibition Demo Script](#exhibition-demo-script)
- [Team](#team)

---

## Overview

Small businesses in India lose significant revenue to fake UPI payment screenshots. Customers edit payment receipts in photo apps — the result looks identical to a real confirmation but no money ever transferred.

**PayShield** solves this at the cryptographic level. Every receipt is signed with RSA-2048 (the same algorithm used by banks and governments). A vendor can verify any receipt in under a second — even offline — and the system makes it mathematically impossible to forge a valid receipt without access to the server's private key.

---

## Features

| Feature | Description |
|---------|-------------|
| 🔐 **RSA-2048 + PSS Signing** | Every receipt carries a digital signature verifiable with the public key |
| #️⃣ **SHA-256 Hash Integrity** | Any field change — even one character — is instantly detected |
| ⏱️ **15-Minute Receipt Expiry** | Receipts expire automatically, preventing stale-receipt abuse |
| 📷 **Live Camera QR Scanning** | Vendors scan receipts with phone camera — no manual input needed |
| 🔒 **JWT Vendor Authentication** | Each vendor has a signed session token; generate requires login |
| 📄 **GST Invoice PDF** | One-click download of a GST-compliant tax invoice with crypto proof section |
| 💳 **Razorpay Webhook** | Receipts auto-generated from confirmed Razorpay payments |
| 🌐 **PostgreSQL Support** | Drop-in replacement for SQLite for multi-server deployments |
| 🔑 **3 Key Management Backends** | File (dev) → Environment variable (cloud) → AWS KMS (production HSM) |
| 📱 **Progressive Web App** | Installable on Android/iOS, works offline with cached public key |
| 🚫 **Anti-Replay Protection** | Each receipt marked used after first verification; duplicates blocked |
| 🛡️ **Rate Limiting** | Per-IP limits on all API endpoints via Nginx + in-process fallback |
| 📊 **Live Dashboard** | Real-time analytics: volume, vendor breakdown, fake attempt log |
| 🔄 **Nginx + Gunicorn** | Production-grade WSGI server behind Nginx reverse proxy with SSL |

---

## Cryptographic Design

```
GENERATION                              VERIFICATION
──────────                              ────────────
1. Build JSON payload                   1. Parse QR → extract JSON
   {id, amount, upi_id,                 2. Check expiry timestamp
    vendor_id, timestamp,               3. Re-compute SHA-256 hash
    expires_at, key_version}               compare with stored hash
                                           → FAIL if mismatch (tampered)
2. SHA-256 hash payload                 4. Verify RSA-PSS signature
   → 64-char hex fingerprint               using public key
                                           → FAIL if invalid (forged)
3. RSA-PSS sign hash                    5. DB lookup: does txn ID exist?
   with private key + random salt          → FAIL if not found (fake)
   → 256-byte signature                 6. DB check: is receipt unused?
                                           → FAIL if used (replay attack)
4. Base64 encode signature              7. Mark receipt as used
   → ASCII-safe for QR/JSON             8. Return ✅ VERIFIED
```

**Why RSA-PSS over plain RSA?**
Plain RSA is deterministic — the same data always produces the same signature, enabling certain mathematical attacks. PSS (Probabilistic Signature Scheme) adds a random salt before signing, so two identical ₹100 payments produce completely different signatures. This is the PKCS#1 v2.1 standard, used by TLS 1.3 and modern bank APIs.

**Why SHA-256 before signing?**
RSA can only sign data ≤ key size (2048 bits = 256 bytes). Payment JSON is larger. Hashing first gives a fixed 32-byte input regardless of payload size — standard practice called "hash-then-sign".

---

## Project Structure

```
payshield/
│
├── app.py                  Flask application — all routes
├── crypto_utils.py         RSA-2048 sign/verify, 3 key backends, expiry
├── db.py                   Database layer — SQLite + PostgreSQL
├── auth.py                 JWT vendor authentication
├── gst_pdf.py              GST-compliant invoice PDF (ReportLab)
├── config.py               Central config loaded from .env
├── seed_demo.py            Populate demo data for exhibition
│
├── .env.example            ← Copy to .env and fill in values
├── .env                    ← Your local config (git-ignored)
├── .gitignore
├── requirements.txt
│
├── keys/                   RSA key files (git-ignored in production)
│   ├── private_key.pem     ← NEVER commit, NEVER share
│   └── public_key.pem      ← Safe to distribute to vendors
│
├── database/
│   └── payments.db         SQLite database (git-ignored)
│
├── templates/
│   ├── customer.html       Generate receipt page (PWA)
│   ├── vendor.html         Verify receipt — live camera scan (PWA)
│   ├── dashboard.html      Analytics dashboard
│   └── login.html          Vendor JWT login
│
├── static/
│   ├── js/sw.js            Service worker (PWA offline support)
│   └── icons/              PWA app icons (192×192, 512×512)
│
├── nginx/
│   └── payshield.conf      Nginx reverse proxy + SSL + rate limiting
│
├── scripts/
│   ├── start.sh            Production startup (Gunicorn)
│   ├── start_dev.sh        Development startup
│   └── deploy_ubuntu.sh    One-shot Ubuntu 22.04 deployment
│
└── migrations/
    └── 001_add_expiry_and_gst.sql   Schema migration for existing DBs
```

---

## Quick Start (Development)

```bash
# 1. Clone
git clone https://github.com/YOUR_USERNAME/payshield.git
cd payshield

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy and configure environment
cp .env.example .env
# Edit .env — at minimum set SECRET_KEY and JWT_SECRET

# 4. Seed demo data (optional but recommended)
python seed_demo.py

# 5. Run
python app.py
```

Open **http://localhost:5000**

**Default vendor passwords** (development only):

| Vendor ID | Store | Password |
|-----------|-------|----------|
| V001 | Ravi Provision Stores | `ravi123` |
| V002 | Meena Textiles | `meena123` |
| V003 | Krishna Dhabha | `krishna123` |
| V004 | Suresh Electronics | `suresh123` |
| V005 | Priya Medical | `priya123` |

---

## Configuration (.env)

```bash
# Copy the template first
cp .env.example .env
```

Key settings to change:

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | dev value | Flask session secret — use 64+ random chars in prod |
| `JWT_SECRET` | dev value | JWT signing secret — use 64+ random chars in prod |
| `KEY_BACKEND` | `file` | `file` / `env` / `aws_kms` |
| `DB_BACKEND` | `sqlite` | `sqlite` / `postgresql` |
| `RECEIPT_EXPIRY_MINUTES` | `15` | How long a receipt is valid |
| `RAZORPAY_KEY_ID` | placeholder | From Razorpay dashboard |
| `BUSINESS_GSTIN` | sample | Your actual GSTIN |

**Generate secure secrets:**
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

---

## API Reference

### Authentication
```
POST /api/auth/login
Body: { "vendor_id": "V001", "password": "ravi123" }
Returns: { "token": "<JWT>", "vendor_id": "V001", "vendor_name": "Ravi Stores" }
```

### Generate Receipt
```
POST /api/generate
Body: {
  "amount": 500.00,
  "upi_id": "customer@upi",
  "vendor_id": "V001",
  "gst_number": "29AABCR1234A1ZK",  // optional
  "hsn_code": "9971",                // optional
  "payment_ref": "pay_xyz123"        // optional, from Razorpay
}
Returns: { "receipt": {...}, "qr_image": "<base64 PNG>", "expires_in_minutes": 15 }
```

### Verify Receipt
```
POST /api/verify
Body: { "qr_data": "<full receipt JSON string>" }
Returns (valid):   { "valid": true, "details": {...} }
Returns (invalid): { "valid": false, "reason": "..." }
```

### Download GST Invoice PDF
```
GET /api/invoice/<transaction_id>
Returns: application/pdf
```

### Razorpay Webhook
```
POST /api/webhooks/razorpay
Headers: X-Razorpay-Signature: <hmac>
Body: Razorpay payment.captured event JSON
```

### Dashboard Stats
```
GET /api/dashboard
Returns: { total_transactions, total_amount, fake_attempts, recent[], daily[], by_vendor[], fake_log[] }
```

---

## Production Deployment

### Requirements
- Ubuntu 22.04 LTS (recommended)
- Python 3.10+
- Nginx
- A domain name with DNS pointed to your server

### One-command deploy
```bash
sudo bash scripts/deploy_ubuntu.sh yourdomain.com
```

This script:
1. Installs Nginx, Python, Certbot
2. Creates a `payshield` system user
3. Sets up a Python virtualenv
4. Creates a systemd service (auto-restarts on crash)
5. Configures Nginx as reverse proxy
6. Obtains a free Let's Encrypt SSL certificate

### Manual steps after deploy
```bash
# Edit environment
sudo nano /opt/payshield/.env

# Restart service
sudo systemctl restart payshield

# Check logs
sudo journalctl -u payshield -f

# Check Nginx
sudo nginx -t && sudo systemctl reload nginx
```

### Run with Gunicorn directly
```bash
# 4 workers, 2 threads each — tune to your server
gunicorn app:app \
  --workers 4 \
  --threads 2 \
  --worker-class gthread \
  --bind 127.0.0.1:5000 \
  --timeout 120
```

**Gunicorn worker formula:** `(2 × CPU cores) + 1`
- 1 CPU → 3 workers
- 2 CPU → 5 workers
- 4 CPU → 9 workers

---

## Key Management Backends

### 1. File Backend (development)
```env
KEY_BACKEND=file
```
Keys stored in `keys/private_key.pem` and `keys/public_key.pem`.
Auto-generated on first run. **Never use in production.**

### 2. Environment Variable Backend (cloud deployment)
```env
KEY_BACKEND=env
PRIVATE_KEY_PEM=-----BEGIN PRIVATE KEY-----\nMIIE...\n-----END PRIVATE KEY-----
PUBLIC_KEY_PEM=-----BEGIN PUBLIC KEY-----\nMIIB...\n-----END PUBLIC KEY-----
```

Convert your keys to env-var format:
```bash
# Export existing keys as single-line env vars
python3 -c "
import base64
priv = open('keys/private_key.pem').read().replace('\n','\\\\n')
pub  = open('keys/public_key.pem').read().replace('\n','\\\\n')
print('PRIVATE_KEY_PEM=' + priv)
print('PUBLIC_KEY_PEM='  + pub)
"
```
Paste the output into your cloud provider's secrets/environment variables panel (Railway, Render, Heroku, etc.).

### 3. AWS KMS Backend (production — most secure)
```env
KEY_BACKEND=aws_kms
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=ap-south-1
KMS_KEY_ID=arn:aws:kms:ap-south-1:123456789:key/your-key-id
```

The private key **never leaves AWS hardware**. All signing happens inside the KMS HSM.

**AWS KMS setup:**
```bash
# Install boto3
pip install boto3

# Create KMS key (asymmetric, RSA_2048, SIGN_VERIFY)
aws kms create-key \
  --key-usage SIGN_VERIFY \
  --key-spec  RSA_2048 \
  --description "PayShield receipt signing key" \
  --region ap-south-1

# Note the KeyId from the output and set KMS_KEY_ID in .env
```

---

## Database Backends

### SQLite (default, development)
```env
DB_BACKEND=sqlite
SQLITE_PATH=database/payments.db
```
Zero setup, single file. Use for development and single-server deployments with low traffic.

### PostgreSQL (production)
```bash
# Install psycopg2
pip install psycopg2-binary

# Create database
createdb payshield
```

```env
DB_BACKEND=postgresql
DATABASE_URL=postgresql://payshield_user:password@localhost:5432/payshield
```

Tables are auto-created on first run. For existing SQLite deployments:
```bash
# Run migration
psql $DATABASE_URL < migrations/001_add_expiry_and_gst.sql
```

---

## Razorpay Integration

PayShield auto-generates receipts when Razorpay confirms a payment.

### Setup
1. Create account at [razorpay.com](https://razorpay.com)
2. Get API keys from Dashboard → Settings → API Keys
3. Set in `.env`:
```env
RAZORPAY_KEY_ID=rzp_live_...
RAZORPAY_KEY_SECRET=...
RAZORPAY_WEBHOOK_SECRET=...
```

### Configure webhook
In Razorpay Dashboard → Settings → Webhooks:
- **URL:** `https://yourdomain.com/api/webhooks/razorpay`
- **Events:** `payment.captured`
- **Secret:** same as `RAZORPAY_WEBHOOK_SECRET`

### Payment flow with Razorpay
1. Customer initiates payment on your checkout page
2. Razorpay processes the UPI payment
3. Razorpay fires `payment.captured` webhook to `/api/webhooks/razorpay`
4. PayShield verifies HMAC signature on the webhook
5. Receipt auto-generated and signed with RSA-2048
6. Vendor scans the receipt QR on their device

**Pass vendor_id in Razorpay notes:**
```javascript
// In your Razorpay checkout config
notes: {
  vendor_id: "V001",
  gst_number: "29AABCR1234A1ZK"  // optional
}
```

---

## PWA — Install on Mobile

PayShield is a full Progressive Web App. Vendors can install it on their Android or iOS phone for native-like access.

### Android (Chrome)
1. Open `https://yourdomain.com/vendor` in Chrome
2. Tap the "Install" banner at the bottom of the screen, OR
3. Tap Menu (⋮) → "Add to Home Screen"

### iOS (Safari)
1. Open `https://yourdomain.com/vendor` in Safari
2. Tap Share button → "Add to Home Screen"

### What works offline
- The vendor scan page loads from cache
- Previously cached public key allows **offline signature verification**
- Failed verify requests are queued and retried when connectivity returns (Background Sync API)

---

## Exhibition Demo Script

The 5-step demo that wins the prize:

**Step 1 — Generate a valid receipt**
```
Open http://localhost:5000
Enter: ₹500, yourname@upi, Ravi Stores
Click: Generate Signed Receipt
Show: QR code, SHA-256 hash, RSA signature in the receipt card
Download the QR image
```

**Step 2 — Verify it (should pass)**
```
Open http://localhost:5000/vendor
Click: Live Camera → Start Camera → point at the QR on your phone
Result: ✅ PAYMENT VERIFIED — ₹500.00
Show: 5 green check pills, crypto proof section
Click: Download GST Invoice PDF — show the professional PDF
```

**Step 3 — Replay attack (should fail)**
```
Verify the same QR image again
Result: ❌ Receipt already verified — possible replay attack
```

**Step 4 — Fake receipt (should fail)**
```
Click "Paste JSON" tab
Paste: {"amount":9999,"upi_id":"hacker@upi","vendor_id":"V001"}
Result: ❌ Missing cryptographic fields — fake screenshot
```

**Step 5 — Show dashboard**
```
Open http://localhost:5000/dashboard
Show: transaction chart, vendor breakdown, fake attempts log
```

---

## Team

| Name | Roll Number |
|------|------------|
| Adithi Shetty | 4SF23IS008 |
| Shruthi | 4SF23IS097 |
| Varsha | 4SF23IS116 |
| Varsha K | 4SF23IS117 |
| Priya Shet | 4SF23IS072 |

**Subject:** Cryptography and Network Security (IS62214IC)
**Institution:** Siddaganga Institute of Technology, Tumkur

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">
Built with 🔐 RSA-2048 · SHA-256 · Flask · ReportLab · html5-qrcode
</div>
