"""
app.py — PayShield Flask application.
Includes: JWT auth, Razorpay webhooks, GST PDF, live QR scan, expiry.
"""
import os, json, io, base64, hashlib, hmac
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, request, jsonify, render_template, send_file, make_response
import qrcode, qrcode.constants

from config import (
    SECRET_KEY, IS_PROD, RAZORPAY_KEY_ID,
    RAZORPAY_KEY_SECRET, RAZORPAY_WEBHOOK_SECRET, RECEIPT_EXPIRY_MINUTES
)
from crypto_utils import ensure_keys, generate_receipt, verify_receipt
from db import (init_db, save_transaction, get_transaction, mark_used,
               log_fake, get_vendors, get_vendor_by_id, get_dashboard_stats)
from auth import require_auth, create_token, hash_password, DEFAULT_PASSWORDS
from gst_pdf import generate_gst_invoice

app = Flask(__name__)
app.secret_key = SECRET_KEY

# ── Startup ──────────────────────────────────────────────────────────────────
ensure_keys()
init_db()

# ── Rate limiting (simple in-memory — use Redis in production) ────────────────
from collections import defaultdict, deque
import time

_rate_buckets = defaultdict(deque)

def _rate_limit(key: str, max_calls: int = 20, window: int = 60) -> bool:
    """Returns True if allowed, False if rate-limited."""
    now    = time.time()
    bucket = _rate_buckets[key]
    while bucket and bucket[0] < now - window:
        bucket.popleft()
    if len(bucket) >= max_calls:
        return False
    bucket.append(now)
    return True

# ── Security headers ──────────────────────────────────────────────────────────
@app.after_request
def add_security_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"]        = "DENY"
    resp.headers["Referrer-Policy"]        = "strict-origin-when-cross-origin"
    if IS_PROD:
        resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return resp

# ── Page routes ───────────────────────────────────────────────────────────────
@app.route("/")
def page_customer():   return render_template("customer.html",  razorpay_key=RAZORPAY_KEY_ID, expiry=RECEIPT_EXPIRY_MINUTES)

@app.route("/vendor")
def page_vendor():     return render_template("vendor.html")

@app.route("/dashboard")
def page_dashboard():  return render_template("dashboard.html")

@app.route("/login")
def page_login():      return render_template("login.html")

# ── Auth: vendor login ─────────────────────────────────────────────────────────
@app.route("/api/auth/login", methods=["POST"])
def api_login():
    body      = request.get_json(force=True)
    vendor_id = (body.get("vendor_id") or "").strip().upper()
    password  = (body.get("password")  or "").strip()

    if not vendor_id or not password:
        return jsonify({"error": "vendor_id and password required"}), 400

    vendor = get_vendor_by_id(vendor_id)
    if not vendor:
        return jsonify({"error": "Vendor not found"}), 404

    # Check password — use stored hash if set, else fallback to defaults (dev)
    stored_hash = vendor.get("password_hash") or DEFAULT_PASSWORDS.get(vendor_id)
    if stored_hash != hash_password(password):
        return jsonify({"error": "Invalid credentials"}), 401

    token = create_token(vendor_id, vendor["name"])
    return jsonify({"token": token, "vendor_id": vendor_id, "vendor_name": vendor["name"]})

# ── Vendors list ───────────────────────────────────────────────────────────────
@app.route("/api/vendors")
def api_vendors():
    return jsonify(get_vendors())

# ── Generate signed receipt ────────────────────────────────────────────────────
@app.route("/api/generate", methods=["POST"])
def api_generate():
    ip = request.remote_addr
    if not _rate_limit(f"generate:{ip}", max_calls=30, window=60):
        return jsonify({"error": "Rate limit exceeded — too many requests"}), 429

    body      = request.get_json(force=True)
    amount    = body.get("amount")
    upi_id    = (body.get("upi_id") or "").strip()
    vendor_id = (body.get("vendor_id") or "V001").strip()

    # Optional fields
    gst_number  = (body.get("gst_number")  or "").strip() or None
    hsn_code    = (body.get("hsn_code")    or "").strip() or None
    payment_ref = (body.get("payment_ref") or "").strip() or None

    if not amount or float(amount) <= 0:
        return jsonify({"error": "Please enter a valid amount greater than ₹0"}), 400
    if not upi_id:
        return jsonify({"error": "UPI ID is required"}), 400

    vendors     = {v["vendor_id"]: v["name"] for v in get_vendors()}
    vendor_name = vendors.get(vendor_id, vendor_id)

    receipt = generate_receipt(amount, upi_id, vendor_id, vendor_name,
                                gst_number=gst_number, hsn_code=hsn_code,
                                payment_ref=payment_ref)
    save_transaction(receipt)

    # Build QR
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=7, border=3)
    qr.add_data(json.dumps(receipt))
    qr.make(fit=True)
    img    = qr.make_image(fill_color="#0F172A", back_color="#FFFFFF")
    buf    = io.BytesIO()
    img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode()

    return jsonify({"receipt": receipt, "qr_image": qr_b64,
                    "expires_in_minutes": RECEIPT_EXPIRY_MINUTES})

# ── Verify receipt ─────────────────────────────────────────────────────────────
@app.route("/api/verify", methods=["POST"])
def api_verify():
    ip = request.remote_addr
    if not _rate_limit(f"verify:{ip}", max_calls=60, window=60):
        return jsonify({"valid": False, "reason": "Rate limit exceeded"}), 429

    body    = request.get_json(force=True)
    qr_data = (body.get("qr_data") or "").strip()

    if not qr_data:
        return jsonify({"valid": False, "reason": "No receipt data provided"}), 400

    valid, result = verify_receipt(qr_data)

    if not valid:
        log_fake(str(result), ip)
        return jsonify({"valid": False, "reason": result})

    txn = get_transaction(result["id"])
    if not txn:
        reason = "Transaction ID not found in database — receipt may be forged"
        log_fake(reason, ip)
        return jsonify({"valid": False, "reason": reason})

    used_val = txn["used"]
    if isinstance(used_val, bool):
        already_used = used_val
    else:
        already_used = int(used_val) == 1

    if already_used:
        reason = "Receipt already verified — possible replay attack"
        log_fake(reason, ip)
        return jsonify({"valid": False, "reason": reason})

    mark_used(result["id"])
    return jsonify({"valid": True, "details": result})

# ── GST Invoice PDF ────────────────────────────────────────────────────────────
@app.route("/api/invoice/<txn_id>")
def api_invoice(txn_id):
    txn = get_transaction(txn_id)
    if not txn:
        return jsonify({"error": "Transaction not found"}), 404

    txn_dict = dict(txn)

    # Rebuild QR for embedding in the PDF
    receipt_for_qr = {k: v for k, v in txn_dict.items()
                      if k not in ("used","verified_at","razorpay_id")}
    qr   = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=5, border=2)
    qr.add_data(json.dumps(txn_dict.get("id","")))
    qr.make(fit=True)
    qbuf = io.BytesIO()
    qr.make_image(fill_color="#0F172A", back_color="#FFFFFF").save(qbuf, format="PNG")
    qr_b64 = base64.b64encode(qbuf.getvalue()).decode()

    pdf_bytes = generate_gst_invoice(txn_dict, qr_b64)
    resp = make_response(pdf_bytes)
    resp.headers["Content-Type"]        = "application/pdf"
    resp.headers["Content-Disposition"] = f'attachment; filename="payshield_invoice_{txn_id[:8]}.pdf"'
    return resp

# ── Razorpay webhook ───────────────────────────────────────────────────────────
@app.route("/api/webhooks/razorpay", methods=["POST"])
def razorpay_webhook():
    """
    Razorpay calls this URL after a successful payment.
    We verify the HMAC signature, then auto-generate a signed receipt.
    """
    raw_body = request.get_data()
    rp_sig   = request.headers.get("X-Razorpay-Signature", "")

    # Verify Razorpay HMAC-SHA256 signature
    expected = hmac.new(
        RAZORPAY_WEBHOOK_SECRET.encode(),
        raw_body,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected, rp_sig):
        return jsonify({"error": "Invalid webhook signature"}), 400

    event = json.loads(raw_body)
    if event.get("event") != "payment.captured":
        return jsonify({"status": "ignored"}), 200

    payload = event["payload"]["payment"]["entity"]
    amount  = payload["amount"] / 100        # Razorpay amounts are in paise
    upi_vpa = payload.get("vpa") or payload.get("email") or "unknown@upi"
    notes   = payload.get("notes", {})
    vendor_id   = notes.get("vendor_id", "V001")
    gst_number  = notes.get("gst_number")
    payment_ref = payload["id"]

    vendors     = {v["vendor_id"]: v["name"] for v in get_vendors()}
    vendor_name = vendors.get(vendor_id, vendor_id)

    receipt = generate_receipt(
        amount, upi_vpa, vendor_id, vendor_name,
        gst_number=gst_number, payment_ref=payment_ref
    )
    receipt["razorpay_id"] = payment_ref
    save_transaction(receipt)

    return jsonify({"status": "receipt_created", "receipt_id": receipt["id"]}), 200

# ── Dashboard ─────────────────────────────────────────────────────────────────
@app.route("/api/dashboard")
def api_dashboard():
    return jsonify(get_dashboard_stats())

# ── PWA manifest & service worker ────────────────────────────────────────────
@app.route("/manifest.json")
def pwa_manifest():
    return jsonify({
        "name":             "PayShield",
        "short_name":       "PayShield",
        "description":      "Secure Digital Payment Receipt Verification",
        "start_url":        "/",
        "display":          "standalone",
        "orientation":      "portrait",
        "background_color": "#FDFAF5",
        "theme_color":      "#D97706",
        "icons": [
            {"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
            {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
        ],
        "shortcuts": [
            {"name": "Generate Receipt", "url": "/",        "description": "Create a new payment receipt"},
            {"name": "Verify Receipt",   "url": "/vendor",  "description": "Scan and verify a receipt"},
        ]
    })

@app.route("/sw.js")
def service_worker():
    resp = make_response(open("static/js/sw.js").read())
    resp.headers["Content-Type"] = "application/javascript"
    resp.headers["Service-Worker-Allowed"] = "/"
    return resp

# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    debug = not IS_PROD
    print(f"\n🛡️  PayShield running at http://localhost:5000  [{'production' if IS_PROD else 'development'}]\n")
    app.run(debug=debug, port=5000)
