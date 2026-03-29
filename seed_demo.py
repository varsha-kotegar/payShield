"""
Run this to seed realistic demo transactions for the exhibition.
Usage: python seed_demo.py
"""
import os, sys
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, '.')

from crypto_utils import ensure_keys, generate_receipt
from db import init_db, save_transaction, log_fake

ensure_keys()
init_db()

TRANSACTIONS = [
    (149.00,  "rahul.sharma@upi",   "V001", "Ravi Provision Stores"),
    (2499.00, "sunita.reddy@upi",   "V002", "Meena Textiles"),
    (85.00,   "mohan.kumar@upi",    "V003", "Krishna Dhabha"),
    (599.00,  "adithi.shetty@upi",  "V001", "Ravi Provision Stores"),
    (12500.0, "vikram.iyer@upi",    "V004", "Suresh Electronics"),
    (42.00,   "priya.naidu@upi",    "V003", "Krishna Dhabha"),
    (320.00,  "varsha.kamath@upi",  "V005", "Priya Medical"),
    (799.00,  "shruthi.pai@upi",    "V002", "Meena Textiles"),
    (65.00,   "raju.hegde@upi",     "V003", "Krishna Dhabha"),
    (4299.00, "deepa.shetty@upi",   "V004", "Suresh Electronics"),
]

FAKE_REASONS = [
    "Invalid RSA-2048 signature — this receipt was NOT issued by this system",
    "Hash mismatch — payment amount or UPI ID has been tampered with",
    "This receipt has already been verified — possible replay attack",
    "Transaction ID not found in database — receipt may be forged",
    "Missing cryptographic signature — this is likely a screenshot or manually created fake",
]

print("🌱 Seeding PayShield demo data...\n")
for amount, upi, vid, vname in TRANSACTIONS:
    r = generate_receipt(amount, upi, vid, vname)
    save_transaction(r)
    print(f"  ✅ ₹{amount:>9.2f}  {upi:<28}  →  {vname}")

print()
for reason in FAKE_REASONS:
    log_fake(reason, "192.168.1." + str(int(hash(reason) % 254 + 1)))
    print(f"  🚨 Logged fake: {reason[:60]}…")

print("\n✨ Done! Open http://localhost:5000 to explore the app.")
print("   Pages:  / (Generate)  |  /vendor (Verify)  |  /dashboard")
