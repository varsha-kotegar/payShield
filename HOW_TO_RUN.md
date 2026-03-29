# 🛡️ How to Run PayShield v2

Complete step-by-step guide — from a fresh unzip to a running app.

---

## What You Need

| Requirement | Minimum Version | How to Check |
|-------------|----------------|--------------|
| Python | 3.10+ | `python3 --version` |
| pip | Any recent | `pip3 --version` |
| A terminal | — | Windows: CMD / PowerShell / Git Bash |
| A browser | Any modern | Chrome recommended for camera scan |

---

## Step 1 — Unzip and Enter the Folder

```bash
# After downloading payshield_v2.zip
unzip payshield_v2.zip
cd payshield
```

Your folder should look like this:
```
payshield/
├── app.py
├── config.py
├── crypto_utils.py
├── db.py
├── auth.py
├── gst_pdf.py
├── seed_demo.py
├── requirements.txt
├── .env.example
├── keys/
├── templates/
├── static/
└── ...
```

---

## Step 2 — Create the .env File

The app reads all its settings from a file called `.env`.

```bash
# On Mac / Linux
cp .env.example .env

# On Windows (Command Prompt)
copy .env.example .env

# On Windows (PowerShell)
Copy-Item .env.example .env
```

Open `.env` in any text editor. For development **you don't need to change anything** — the defaults work. The file looks like this:

```env
FLASK_ENV=development
SECRET_KEY=change-me-to-a-long-random-string-in-production
JWT_SECRET=change-me-jwt-secret-also-long-and-random
KEY_BACKEND=file
DB_BACKEND=sqlite
RECEIPT_EXPIRY_MINUTES=15
RAZORPAY_KEY_ID=rzp_test_your_key_here
...
```

> **For a college demo / exhibition** the default values are fine as-is.  
> Only change them if you're deploying to a public server (see [Production section](#production-deployment)).

---

## Step 3 — Install Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- `flask` — web framework
- `cryptography` — RSA-2048, SHA-256, PSS padding
- `qrcode[pil]` — QR code generation
- `PyJWT` — vendor login tokens
- `reportlab` — GST invoice PDF generation
- `gunicorn` — production server
- `python-dotenv` — reads the `.env` file

If you get a permission error on Linux/Mac, add `--user`:
```bash
pip install -r requirements.txt --user
```

If you're using a virtual environment (recommended):
```bash
# Create venv
python3 -m venv venv

# Activate — Mac/Linux
source venv/bin/activate

# Activate — Windows CMD
venv\Scripts\activate.bat

# Activate — Windows PowerShell
venv\Scripts\Activate.ps1

# Now install
pip install -r requirements.txt
```

---

## Step 4 — Seed Demo Data (Recommended)

This populates the database with sample transactions and fake attempts so the dashboard looks interesting.

```bash
python seed_demo.py
```

You should see:
```
✅ RSA-2048 key pair generated.
🌱 Seeding PayShield demo data...

  ✅ ₹   149.00  rahul.sharma@upi   →  Ravi Provision Stores
  ✅ ₹  2499.00  sunita.reddy@upi   →  Meena Textiles
  ...
  🚨 Logged fake: Invalid RSA-2048 signature...
  ...
✨ Done!
```

> This also auto-generates your RSA key pair on first run (stored in `keys/`).

---

## Step 5 — Run the App

```bash
python app.py
```

You should see:
```
✅ RSA-2048 key pair generated.   ← only on first run
🛡️  PayShield running at http://localhost:5000  [development]
 * Running on http://127.0.0.1:5000
 * Debug mode: on
```

Now open your browser and go to **http://localhost:5000**

---

## The Three Pages

| URL | Who Uses It | What It Does |
|-----|------------|--------------|
| **http://localhost:5000** | Customer | Enter amount + UPI ID → get signed QR receipt |
| **http://localhost:5000/vendor** | Vendor/Shopkeeper | Scan or paste QR → verify if payment is real |
| **http://localhost:5000/dashboard** | Admin/Presenter | Live stats, charts, fake attempt log |
| **http://localhost:5000/login** | Vendor | Log in with vendor ID + password to get JWT token |

---

## Default Vendor Login Passwords

Go to **http://localhost:5000/login** and use any of these:

| Vendor ID | Shop Name | Password |
|-----------|-----------|----------|
| V001 | Ravi Provision Stores | `ravi123` |
| V002 | Meena Textiles | `meena123` |
| V003 | Krishna Dhabha | `krishna123` |
| V004 | Suresh Electronics | `suresh123` |
| V005 | Priya Medical | `priya123` |

---

## Demo Walkthrough (for Exhibition)

### Step 1 — Generate a receipt
1. Open **http://localhost:5000**
2. Enter: Amount = `500`, UPI ID = `yourname@upi`, Vendor = `Krishna Dhabha`
3. Click **Generate Signed Receipt**
4. The receipt card appears on the right with:
   - A scannable QR code
   - SHA-256 hash (64-character fingerprint)
   - RSA-PSS signature (Base64)
5. Click **⬇ Download QR** to save the image

### Step 2 — Verify it (should pass ✅)
1. Open **http://localhost:5000/vendor** in another tab
2. **Option A — Camera:** Click `Start Camera`, point your phone's screen at the webcam  
   **Option B — Upload:** Click `Upload Image`, select the downloaded QR PNG  
   **Option C — Paste:** Copy the receipt JSON from the generate page and paste it
3. Click **Verify Receipt**
4. You should see the **green PAYMENT VERIFIED** card with ₹500.00

### Step 3 — Try replay attack (should fail ❌)
1. Verify the **same QR** a second time
2. You should see **❌ Receipt already verified — possible replay attack**

### Step 4 — Try a fake receipt (should fail ❌)
1. Click the **Paste JSON** tab
2. Paste this fake data:
   ```json
   {"amount": 9999, "upi_id": "hacker@upi", "vendor_id": "V001"}
   ```
3. Click Verify
4. You should see **❌ Missing cryptographic fields — this is a fake**

### Step 5 — Download GST Invoice
1. After a successful verification, click **📄 Download GST Invoice PDF**
2. A professional PDF opens with:
   - Business details and GSTIN
   - CGST + SGST breakdown
   - Cryptographic proof section (hash + signature)
   - Embedded QR code

### Step 6 — Show the Dashboard
1. Open **http://localhost:5000/dashboard**
2. Shows: total transactions, total amount, fake attempts caught, vendor breakdown chart

---

## Stopping the App

Press `Ctrl + C` in the terminal where it's running.

---

## Common Errors and Fixes

### ❌ `ModuleNotFoundError: No module named 'flask'`
```bash
pip install -r requirements.txt
```

### ❌ `ModuleNotFoundError: No module named 'dotenv'`
```bash
pip install python-dotenv
```

### ❌ `FileNotFoundError: keys/private_key.pem`
Run seed_demo.py or app.py once — keys auto-generate:
```bash
python seed_demo.py
```

### ❌ `Address already in use` (port 5000 busy)
Another app is using port 5000. Either stop that app, or change the port:
```bash
# Mac — AirPlay uses 5000, disable it in System Preferences > Sharing
# Or run on a different port:
FLASK_RUN_PORT=5001 python app.py
```

### ❌ Camera not working on vendor page
- Camera only works over **HTTPS** or **localhost** — it won't work on `http://192.168.x.x`
- Allow camera permission when the browser asks
- On iPhone/iPad, use Safari (not Chrome) for camera access
- If camera still won't start, use the **Upload Image** or **Paste JSON** tab instead

### ❌ `python` command not found (Windows)
Try `python3` instead of `python`, or use the Python Launcher:
```powershell
py app.py
py seed_demo.py
```

### ❌ `pip` not found
```bash
python3 -m pip install -r requirements.txt
```

---

## File Structure Quick Reference

```
payshield/
│
├── app.py              ← START HERE — Flask server, all routes
├── config.py           ← Reads .env, exposes settings to all modules
├── crypto_utils.py     ← RSA-2048 sign/verify + receipt expiry
├── db.py               ← SQLite/PostgreSQL database operations
├── auth.py             ← JWT login tokens for vendors
├── gst_pdf.py          ← GST invoice PDF generation
├── seed_demo.py        ← Populate demo transactions (run once)
│
├── .env                ← YOUR CONFIG (copy from .env.example)
├── .env.example        ← Template with all options documented
├── requirements.txt    ← Python packages list
│
├── keys/
│   ├── private_key.pem ← Auto-generated, signs receipts (KEEP SECRET)
│   └── public_key.pem  ← Auto-generated, verifies receipts (safe to share)
│
├── database/
│   └── payments.db     ← SQLite database (auto-created)
│
├── templates/          ← HTML pages
│   ├── customer.html   ← Generate receipt
│   ├── vendor.html     ← Verify receipt (live camera)
│   ├── dashboard.html  ← Analytics
│   └── login.html      ← Vendor login
│
├── static/
│   ├── js/sw.js        ← Service worker (PWA offline support)
│   └── icons/          ← App icons for mobile install
│
├── nginx/
│   └── payshield.conf  ← Nginx config (production only)
│
└── scripts/
    ├── start.sh            ← Production startup (Gunicorn)
    ├── start_dev.sh        ← Dev startup shortcut
    └── deploy_ubuntu.sh    ← Full Ubuntu deployment script
```

---

## Production Deployment

> Skip this section for a college demo. Only needed for real public deployment.

### One-command deploy to Ubuntu 22.04
```bash
# On your server (as root or with sudo)
sudo bash scripts/deploy_ubuntu.sh yourdomain.com
```

This automatically:
- Installs Nginx, Python, Gunicorn, Certbot
- Creates a `payshield` system user
- Sets up HTTPS with a free Let's Encrypt certificate
- Configures Nginx as a reverse proxy with rate limiting
- Creates a systemd service that auto-restarts on crash

### Manual Gunicorn (without Nginx)
```bash
gunicorn app:app --workers 4 --bind 0.0.0.0:5000
```

### Environment for production
Change these in `.env`:
```env
FLASK_ENV=production
SECRET_KEY=<64 random characters>
JWT_SECRET=<64 different random characters>
```

Generate secure secrets:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

---

## Install on Phone (PWA)

PayShield works as a native app on mobile — no App Store needed.

**Android (Chrome):**
1. Open `http://localhost:5000/vendor` (or your deployed URL)
2. Tap the **Install** banner that appears, or
3. Tap Menu ⋮ → **Add to Home Screen**

**iPhone (Safari):**
1. Open the URL in Safari
2. Tap the Share button → **Add to Home Screen**

Once installed, the vendor can scan customer QR codes using the phone camera directly from the app — no typing, no uploading, instant verification.

---

*PayShield v2 — Cryptography & Network Security (IS62214IC)*  
*Team: Adithi Shetty, Shruthi, Varsha, Varsha K, Priya Shet*
