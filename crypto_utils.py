"""
crypto_utils.py
Handles RSA-2048 signing/verification with three key backends:
  file    — PEM files on disk (dev)
  env     — PEM content in environment variables (cloud deploy)
  aws_kms — AWS KMS for hardware-backed signing (production)
"""
import json, hashlib, base64, uuid
from datetime import datetime, timezone, timedelta
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.exceptions import InvalidSignature
import os

from config import (
    KEY_BACKEND, PRIVATE_KEY_PATH, PUBLIC_KEY_PATH,
    PRIVATE_KEY_PEM, PUBLIC_KEY_PEM, KMS_KEY_ID, AWS_REGION,
    RECEIPT_EXPIRY_MINUTES
)

KEYS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "keys")

# ── Key loading ──────────────────────────────────────────────────────────────

def ensure_keys():
    """Auto-generate file-based keys in dev if they don't exist."""
    if KEY_BACKEND != "file":
        return
    priv = os.path.join(KEYS_DIR, "private_key.pem")
    pub  = os.path.join(KEYS_DIR, "public_key.pem")
    os.makedirs(KEYS_DIR, exist_ok=True)
    if not os.path.exists(priv):
        k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        with open(priv, "wb") as f:
            f.write(k.private_bytes(serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        with open(pub, "wb") as f:
            f.write(k.public_key().public_bytes(
                serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
        print("✅ RSA-2048 key pair generated (file backend).")

def load_private_key():
    """Load private key from configured backend."""
    if KEY_BACKEND == "env":
        # PEM content stored as environment variable
        pem = (PRIVATE_KEY_PEM or "").replace("\\n", "\n").encode()
        return serialization.load_pem_private_key(pem, password=None)

    if KEY_BACKEND == "aws_kms":
        # AWS KMS — we don't load the private key at all.
        # Signing is done remotely via KMS API (key never leaves HSM).
        raise RuntimeError("For KMS backend, use kms_sign() instead of load_private_key()")

    # Default: file backend
    with open(os.path.join(KEYS_DIR, "private_key.pem"), "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)

def load_public_key():
    """Load public key from configured backend."""
    if KEY_BACKEND == "env":
        pem = (PUBLIC_KEY_PEM or "").replace("\\n", "\n").encode()
        return serialization.load_pem_public_key(pem)

    if KEY_BACKEND == "aws_kms":
        # Fetch public key from KMS
        try:
            import boto3
            kms = boto3.client("kms", region_name=AWS_REGION)
            resp = kms.get_public_key(KeyId=KMS_KEY_ID)
            der  = resp["PublicKey"]
            return serialization.load_der_public_key(der)
        except ImportError:
            raise RuntimeError("boto3 not installed. Run: pip install boto3")

    with open(os.path.join(KEYS_DIR, "public_key.pem"), "rb") as f:
        return serialization.load_pem_public_key(f.read())

def _sign_bytes(data: bytes) -> bytes:
    """Sign bytes using configured backend. Returns raw signature bytes."""
    if KEY_BACKEND == "aws_kms":
        try:
            import boto3
            kms = boto3.client("kms", region_name=AWS_REGION)
            resp = kms.sign(
                KeyId=KMS_KEY_ID,
                Message=data,
                MessageType="RAW",
                SigningAlgorithm="RSASSA_PSS_SHA_256"
            )
            return resp["Signature"]
        except ImportError:
            raise RuntimeError("boto3 not installed. Run: pip install boto3")

    # file or env backend — local RSA signing
    private_key = load_private_key()
    return private_key.sign(
        data,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256()
    )

# ── Receipt generation ───────────────────────────────────────────────────────

def generate_receipt(amount, upi_id, vendor_id, vendor_name,
                     gst_number=None, hsn_code=None, payment_ref=None):
    """
    Build payload → SHA-256 hash → RSA-PSS sign → Base64 encode.
    Includes expiry timestamp (RECEIPT_EXPIRY_MINUTES from config).
    """
    now      = datetime.now(timezone.utc)
    expires  = now + timedelta(minutes=RECEIPT_EXPIRY_MINUTES)

    payload = {
        "id":          str(uuid.uuid4()),
        "amount":      round(float(amount), 2),
        "upi_id":      upi_id.strip().lower(),
        "vendor_id":   vendor_id,
        "vendor_name": vendor_name,
        "timestamp":   now.isoformat(),
        "expires_at":  expires.isoformat(),
        "key_version": "v1",                     # key rotation support
    }
    # Optional GST fields (added only when present)
    if gst_number:    payload["gst_number"]   = gst_number
    if hsn_code:      payload["hsn_code"]     = hsn_code
    if payment_ref:   payload["payment_ref"]  = payment_ref   # Razorpay order/payment ID

    # SHA-256 hash of canonical JSON
    payload_str  = json.dumps(payload, sort_keys=True, separators=(',', ':'))
    payload_hash = hashlib.sha256(payload_str.encode()).hexdigest()

    # RSA-PSS sign
    sig_bytes     = _sign_bytes(payload_str.encode())
    signature_b64 = base64.b64encode(sig_bytes).decode()

    return {**payload, "hash": payload_hash, "signature": signature_b64}

# ── Receipt verification ─────────────────────────────────────────────────────

def verify_receipt(qr_data: str):
    """
    Full verification pipeline:
      1. Parse JSON
      2. Check required fields exist
      3. Check expiry (15-min TTL)
      4. Verify SHA-256 hash
      5. Verify RSA-PSS signature
    Returns (True, data_dict) or (False, reason_string).
    """
    try:
        data          = json.loads(qr_data)
        signature_b64 = data.pop("signature", None)
        stored_hash   = data.pop("hash", None)

        if not signature_b64 or not stored_hash:
            return False, "Missing cryptographic fields — this is a fake screenshot or invalid QR"

        # ── Expiry check ──────────────────────────────────────────────────
        expires_at_str = data.get("expires_at")
        if expires_at_str:
            try:
                expires_at = datetime.fromisoformat(expires_at_str)
                # Make offset-aware if naive
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) > expires_at:
                    return False, (
                        f"Receipt expired at {expires_at_str} UTC — "
                        f"receipt TTL is {RECEIPT_EXPIRY_MINUTES} minutes. "
                        "Ask the customer to generate a new receipt."
                    )
            except ValueError:
                pass  # malformed expiry — continue, signature will catch tampering

        # ── Hash integrity ────────────────────────────────────────────────
        payload_str   = json.dumps(data, sort_keys=True, separators=(',', ':'))
        computed_hash = hashlib.sha256(payload_str.encode()).hexdigest()
        if computed_hash != stored_hash:
            return False, "Hash mismatch — amount, UPI ID, or other fields have been tampered with"

        # ── RSA-PSS signature ─────────────────────────────────────────────
        sig_bytes  = base64.b64decode(signature_b64)
        public_key = load_public_key()

        if KEY_BACKEND == "aws_kms":
            # KMS verify via API
            try:
                import boto3
                kms = boto3.client("kms", region_name=AWS_REGION)
                kms.verify(
                    KeyId=KMS_KEY_ID,
                    Message=payload_str.encode(),
                    MessageType="RAW",
                    Signature=sig_bytes,
                    SigningAlgorithm="RSASSA_PSS_SHA_256"
                )
            except Exception as e:
                return False, f"KMS verification failed: {e}"
        else:
            public_key.verify(
                sig_bytes, payload_str.encode(),
                padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
                hashes.SHA256()
            )

        return True, {**data, "hash": stored_hash, "signature": signature_b64}

    except InvalidSignature:
        return False, "Invalid RSA-2048 signature — receipt was NOT issued by this server"
    except json.JSONDecodeError:
        return False, "Cannot parse QR data — not a valid PayShield receipt"
    except Exception as e:
        return False, f"Verification error: {str(e)}"
