<div align="center">

# 🛡️ PayShield

### Secure UPI Receipt Verification with RSA-based Digital Signing

*Protects businesses from fake payment screenshots by cryptographically validating UPI receipts.*

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-2.3+-000000?style=flat&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![RSA-2048](https://img.shields.io/badge/Encryption-RSA--2048-brightgreen?style=flat)](https://en.wikipedia.org/wiki/RSA_(cryptosystem))
[![License](https://img.shields.io/badge/License-MIT-yellow?style=flat)](LICENSE)

</div>

---

## Overview

PayShield is a Flask-based payment verification platform designed to stop fake UPI payment receipts. It signs every receipt with RSA-2048 and verifies the signature against a public key. If a receipt is tampered with, expired, or reused, verification fails instantly.

This project is interview-ready because it combines:

- backend API design
- cryptography and digital signatures
- secure authentication
- PWA and QR-based workflows
- deployment automation

---

## Key Features

- RSA-2048 digital signatures with PSS for secure receipt authenticity
- SHA-256 hashing for payload integrity
- Receipt expiry and anti-replay protection
- JWT-based vendor authentication
- GST invoice PDF generation
- Razorpay payment webhook integration
- SQLite and PostgreSQL support
- Configurable key management backends: file, env, AWS KMS
- Progressive Web App with QR scanning and offline support
- Production-ready deployment with Nginx + Gunicorn

---

## Why It Matters

Fake payment screenshots are a real fraud vector for small businesses. PayShield solves this by making receipts cryptographically verifiable, so vendors can distinguish real payments from edited images without relying on trust.

---

## Project Layout

```
payshield/
│
├── app.py                  Flask application entrypoint
├── crypto_utils.py         RSA signing, verification, and key backends
├── db.py                   Database backend abstraction and models
├── auth.py                 JWT vendor authentication
├── gst_pdf.py              GST invoice PDF generation
├── config.py               Environment-based configuration loader
├── seed_demo.py            Demo data seeder
│
├── .env.example            Environment variables template
├── requirements.txt        Python dependencies
│
├── keys/                   RSA key storage for development
├── database/               SQLite database file storage
├── templates/              HTML templates for web views
├── static/                 JS, CSS, service worker, icons
├── nginx/                  Nginx reverse proxy config
├── scripts/                Deployment and startup scripts
└── migrations/             Database schema migration files
```

---

## Quick Start

```bash
git clone https://github.com/varsha-kotegar/payShield.git
cd payshield
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python seed_demo.py
python app.py
```

Open `http://localhost:5000`

---

## Example Vendor Login

| Vendor ID | Name | Password |
|-----------|------|----------|
| V001 | Ravi Provision Stores | `ravi123` |
| V002 | Meena Textiles | `meena123` |
| V003 | Krishna Dhabha | `krishna123` |
| V004 | Suresh Electronics | `suresh123` |
| V005 | Priya Medical | `priya123` |

---

## Configuration

Copy the sample environment file into `.env` and update the values:

```bash
copy .env.example .env
```

Important variables:

- `SECRET_KEY` — Flask session secret
- `JWT_SECRET` — JWT signing secret
- `KEY_BACKEND` — `file`, `env`, or `aws_kms`
- `DB_BACKEND` — `sqlite` or `postgresql`
- `RECEIPT_EXPIRY_MINUTES` — receipt validity in minutes
- `RAZORPAY_KEY_ID` — Razorpay API key ID
- `BUSINESS_GSTIN` — GSTIN for invoice generation

Generate strong secrets:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## API Reference

### POST /api/auth/login

Request body:

```json
{
  "vendor_id": "V001",
  "password": "ravi123"
}
```

Response:

```json
{
  "token": "<JWT>",
  "vendor_id": "V001",
  "vendor_name": "Ravi Stores"
}
```

### POST /api/generate

Request body:

```json
{
  "amount": 500.00,
  "upi_id": "customer@upi",
  "vendor_id": "V001",
  "gst_number": "29AABCR1234A1ZK",
  "hsn_code": "9971",
  "payment_ref": "pay_xyz123"
}
```

Response:

```json
{
  "receipt": { ... },
  "qr_image": "<base64 PNG>",
  "expires_in_minutes": 15
}
```

### POST /api/verify

Request body:

```json
{ "qr_data": "<full receipt JSON string>" }
```

Success response:

```json
{ "valid": true, "details": { ... } }
```

Fail response:

```json
{ "valid": false, "reason": "tampered payload" }
```

### GET /api/invoice/<transaction_id>

Returns PDF invoice for the verified transaction.

### POST /api/webhooks/razorpay

Receives Razorpay `payment.captured` events and creates verified receipts automatically.

---

## Deployment

### Quick production deploy

```bash
sudo bash scripts/deploy_ubuntu.sh yourdomain.com
```

### Manual production run

Update `.env`, then restart service:

```bash
sudo systemctl restart payshield
sudo journalctl -u payshield -f
sudo nginx -t && sudo systemctl reload nginx
```

### Gunicorn command

```bash
gunicorn app:app \
  --workers 4 \
  --threads 2 \
  --worker-class gthread \
  --bind 127.0.0.1:5000 \
  --timeout 120
```

---

## Key Management Options

### File backend (development)

```env
KEY_BACKEND=file
```

### Environment variable backend (cloud)

```env
KEY_BACKEND=env
PRIVATE_KEY_PEM=-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----
PUBLIC_KEY_PEM=-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----
```

### AWS KMS backend (production)

```env
KEY_BACKEND=aws_kms
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=ap-south-1
KMS_KEY_ID=arn:aws:kms:ap-south-1:123456789:key/your-key-id
```

---

## Database Options

### SQLite

```env
DB_BACKEND=sqlite
SQLITE_PATH=database/payments.db
```

### PostgreSQL

```env
DB_BACKEND=postgresql
DATABASE_URL=postgresql://payshield_user:password@localhost:5432/payshield
```

Run migration:

```bash
psql $DATABASE_URL < migrations/001_add_expiry_and_gst.sql
```

---

## Interview Highlights

Talk about:

- secure receipt signing and verification using RSA-PSS
- how JWT protects vendor sessions
- PWA + QR workflow for mobile-first verification
- production deployment with Nginx, Gunicorn, and optional PostgreSQL
- secure key management using environment variables or AWS KMS

---

## License

MIT License. See `LICENSE`.
