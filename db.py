"""
db.py — Database abstraction layer.
Supports SQLite (dev) and PostgreSQL (production) via DB_BACKEND env var.
"""
import os
from config import DB_BACKEND, SQLITE_PATH, DATABASE_URL

# ── Connection factory ───────────────────────────────────────────────────────

def get_conn():
    if DB_BACKEND == "postgresql":
        try:
            import psycopg2
            import psycopg2.extras
            conn = psycopg2.connect(DATABASE_URL)
            conn.autocommit = False
            return conn
        except ImportError:
            raise RuntimeError("psycopg2 not installed. Run: pip install psycopg2-binary")
    else:
        import sqlite3
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), SQLITE_PATH)
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

def _ph():
    """Return placeholder character for the active DB backend."""
    return "%s" if DB_BACKEND == "postgresql" else "?"

# ── Schema ───────────────────────────────────────────────────────────────────

SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS transactions (
    id            TEXT    PRIMARY KEY,
    amount        REAL    NOT NULL,
    upi_id        TEXT    NOT NULL,
    vendor_id     TEXT    NOT NULL,
    vendor_name   TEXT    NOT NULL DEFAULT '',
    timestamp     TEXT    NOT NULL,
    expires_at    TEXT,
    signature     TEXT    NOT NULL,
    hash          TEXT    NOT NULL,
    used          INTEGER NOT NULL DEFAULT 0,
    verified_at   TEXT,
    payment_ref   TEXT,
    gst_number    TEXT,
    hsn_code      TEXT,
    razorpay_id   TEXT
);
CREATE TABLE IF NOT EXISTS fake_attempts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    attempted_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    ip_address    TEXT,
    reason        TEXT
);
CREATE TABLE IF NOT EXISTS vendors (
    vendor_id     TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    upi_id        TEXT NOT NULL,
    category      TEXT NOT NULL DEFAULT 'General',
    gstin         TEXT,
    password_hash TEXT,
    jwt_secret    TEXT
);
INSERT OR IGNORE INTO vendors VALUES
    ('V001','Ravi Provision Stores','ravistore@upi','Grocery','29AABCR1234A1ZK',NULL,NULL),
    ('V002','Meena Textiles','meena.tex@upi','Clothing','29AABCM5678B1ZK',NULL,NULL),
    ('V003','Krishna Dhabha','krishna.dhaba@upi','Food & Dining',NULL,NULL,NULL),
    ('V004','Suresh Electronics','suresh.elec@upi','Electronics','29AABCS9012C1ZK',NULL,NULL),
    ('V005','Priya Medical','priya.med@upi','Pharmacy','29AABCP3456D1ZK',NULL,NULL);
"""

SCHEMA_POSTGRESQL = """
CREATE TABLE IF NOT EXISTS transactions (
    id            TEXT    PRIMARY KEY,
    amount        NUMERIC(12,2) NOT NULL,
    upi_id        TEXT    NOT NULL,
    vendor_id     TEXT    NOT NULL,
    vendor_name   TEXT    NOT NULL DEFAULT '',
    timestamp     TIMESTAMPTZ NOT NULL,
    expires_at    TIMESTAMPTZ,
    signature     TEXT    NOT NULL,
    hash          TEXT    NOT NULL,
    used          BOOLEAN NOT NULL DEFAULT FALSE,
    verified_at   TIMESTAMPTZ,
    payment_ref   TEXT,
    gst_number    TEXT,
    hsn_code      TEXT,
    razorpay_id   TEXT
);
CREATE TABLE IF NOT EXISTS fake_attempts (
    id            SERIAL PRIMARY KEY,
    attempted_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ip_address    TEXT,
    reason        TEXT
);
CREATE TABLE IF NOT EXISTS vendors (
    vendor_id     TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    upi_id        TEXT NOT NULL,
    category      TEXT NOT NULL DEFAULT 'General',
    gstin         TEXT,
    password_hash TEXT,
    jwt_secret    TEXT
);
INSERT INTO vendors (vendor_id,name,upi_id,category,gstin) VALUES
    ('V001','Ravi Provision Stores','ravistore@upi','Grocery','29AABCR1234A1ZK'),
    ('V002','Meena Textiles','meena.tex@upi','Clothing','29AABCM5678B1ZK'),
    ('V003','Krishna Dhabha','krishna.dhaba@upi','Food & Dining',NULL),
    ('V004','Suresh Electronics','suresh.elec@upi','Electronics','29AABCS9012C1ZK'),
    ('V005','Priya Medical','priya.med@upi','Pharmacy','29AABCP3456D1ZK')
ON CONFLICT (vendor_id) DO NOTHING;
"""

def init_db():
    with get_conn() as conn:
        c = conn.cursor()
        schema = SCHEMA_POSTGRESQL if DB_BACKEND == "postgresql" else SCHEMA_SQLITE
        if DB_BACKEND == "sqlite":
            conn.executescript(schema)
        else:
            for stmt in [s.strip() for s in schema.split(";") if s.strip()]:
                c.execute(stmt)
            conn.commit()

# ── CRUD helpers ─────────────────────────────────────────────────────────────

def _row_to_dict(row):
    if row is None: return None
    if DB_BACKEND == "postgresql": return dict(row)
    import sqlite3
    if isinstance(row, sqlite3.Row): return dict(row)
    return dict(row)

def save_transaction(txn: dict):
    p = _ph()
    sql = f"""
        INSERT INTO transactions
          (id,amount,upi_id,vendor_id,vendor_name,timestamp,expires_at,
           signature,hash,payment_ref,gst_number,hsn_code,razorpay_id)
        VALUES ({p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p})
    """
    vals = (
        txn["id"], txn["amount"], txn["upi_id"], txn["vendor_id"], txn["vendor_name"],
        txn["timestamp"], txn.get("expires_at"),
        txn["signature"], txn["hash"],
        txn.get("payment_ref"), txn.get("gst_number"),
        txn.get("hsn_code"), txn.get("razorpay_id")
    )
    with get_conn() as conn:
        conn.cursor().execute(sql, vals)
        if DB_BACKEND == "postgresql": conn.commit()

def get_transaction(txn_id: str):
    p = _ph()
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM transactions WHERE id={p}", (txn_id,))
        if DB_BACKEND == "postgresql":
            import psycopg2.extras
            cols = [d[0] for d in cur.description]
            row  = cur.fetchone()
            return dict(zip(cols, row)) if row else None
        return _row_to_dict(cur.fetchone())

def mark_used(txn_id: str):
    p = _ph()
    ts = "NOW()" if DB_BACKEND == "postgresql" else "datetime('now')"
    with get_conn() as conn:
        conn.cursor().execute(
            f"UPDATE transactions SET used=1, verified_at={ts} WHERE id={p}", (txn_id,))
        if DB_BACKEND == "postgresql": conn.commit()

def log_fake(reason: str, ip: str):
    p = _ph()
    with get_conn() as conn:
        conn.cursor().execute(
            f"INSERT INTO fake_attempts (ip_address,reason) VALUES ({p},{p})", (ip, reason))
        if DB_BACKEND == "postgresql": conn.commit()

def get_vendors():
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT vendor_id,name,upi_id,category,gstin FROM vendors ORDER BY name")
        if DB_BACKEND == "postgresql":
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]
        return [dict(r) for r in cur.fetchall()]

def get_vendor_by_id(vendor_id: str):
    p = _ph()
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM vendors WHERE vendor_id={p}", (vendor_id,))
        if DB_BACKEND == "postgresql":
            cols = [d[0] for d in cur.description]
            row  = cur.fetchone()
            return dict(zip(cols, row)) if row else None
        return _row_to_dict(cur.fetchone())

def get_dashboard_stats():
    with get_conn() as conn:
        cur = conn.cursor()
        def q(sql): cur.execute(sql); return cur.fetchone()
        def qa(sql): cur.execute(sql); 
        if DB_BACKEND == "postgresql":
            def fetch_one(sql):
                cur.execute(sql); cols=[d[0] for d in cur.description]; row=cur.fetchone()
                return dict(zip(cols,row)) if row else {}
            def fetch_all(sql):
                cur.execute(sql); cols=[d[0] for d in cur.description]
                return [dict(zip(cols,r)) for r in cur.fetchall()]
            totals   = fetch_one("SELECT COUNT(*) cnt, COALESCE(SUM(amount),0) total FROM transactions")
            fakes    = fetch_one("SELECT COUNT(*) cnt FROM fake_attempts")
            used_cnt = fetch_one("SELECT COUNT(*) cnt FROM transactions WHERE used=TRUE")
            recent   = fetch_all("SELECT id,amount,upi_id,vendor_name,timestamp,used FROM transactions ORDER BY timestamp DESC LIMIT 8")
            daily    = fetch_all("SELECT DATE(timestamp) day, COUNT(*) cnt, SUM(amount) total FROM transactions GROUP BY day ORDER BY day DESC LIMIT 7")
            by_vendor= fetch_all("SELECT vendor_name,COUNT(*) cnt,COALESCE(SUM(amount),0) total FROM transactions GROUP BY vendor_id,vendor_name ORDER BY total DESC")
            fake_log = fetch_all("SELECT attempted_at,ip_address,reason FROM fake_attempts ORDER BY attempted_at DESC LIMIT 6")
        else:
            import sqlite3
            def sr(r): return dict(r) if r else {}
            totals   = sr(conn.execute("SELECT COUNT(*) cnt,COALESCE(SUM(amount),0) total FROM transactions").fetchone())
            fakes    = sr(conn.execute("SELECT COUNT(*) cnt FROM fake_attempts").fetchone())
            used_cnt = sr(conn.execute("SELECT COUNT(*) cnt FROM transactions WHERE used=1").fetchone())
            recent   = [dict(r) for r in conn.execute("SELECT id,amount,upi_id,vendor_name,timestamp,used FROM transactions ORDER BY timestamp DESC LIMIT 8").fetchall()]
            daily    = [dict(r) for r in conn.execute("SELECT substr(timestamp,1,10) day,COUNT(*) cnt,SUM(amount) total FROM transactions GROUP BY day ORDER BY day DESC LIMIT 7").fetchall()]
            by_vendor= [dict(r) for r in conn.execute("SELECT vendor_name,COUNT(*) cnt,COALESCE(SUM(amount),0) total FROM transactions GROUP BY vendor_id ORDER BY total DESC").fetchall()]
            fake_log = [dict(r) for r in conn.execute("SELECT attempted_at,ip_address,reason FROM fake_attempts ORDER BY attempted_at DESC LIMIT 6").fetchall()]
    return {
        "total_transactions": totals.get("cnt",0),
        "total_amount":       round(float(totals.get("total",0)), 2),
        "fake_attempts":      fakes.get("cnt",0),
        "used_receipts":      used_cnt.get("cnt",0),
        "recent":             recent,
        "daily":              daily,
        "by_vendor":          by_vendor,
        "fake_log":           fake_log,
    }
