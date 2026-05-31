import sqlite3
import os

DB_PATH = 'data/applications.db'

def init_db():
    os.makedirs('data', exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Create table for license applications
    c.execute('''
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hwid TEXT NOT NULL,
            contact TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            license_key TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Create table for automated order verifications (No-Signature Pay Gate)
    c.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id TEXT NOT NULL UNIQUE,
            hwid TEXT NOT NULL,
            license_key TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Create table for pending pay orders
    c.execute('''
        CREATE TABLE IF NOT EXISTS pending_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_no TEXT NOT NULL UNIQUE,
            hwid TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def add_pending_payment(trade_no, hwid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO pending_payments (trade_no, hwid) VALUES (?, ?)', (trade_no, hwid))
    conn.commit()
    conn.close()

def get_pending_payment(trade_no):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT hwid, status FROM pending_payments WHERE trade_no = ?', (trade_no,))
    row = c.fetchone()
    conn.close()
    if row:
        return {"hwid": row[0], "status": row[1]}
    return None

def update_pending_payment_status(trade_no, status):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE pending_payments SET status = ? WHERE trade_no = ?', (status, trade_no))
    conn.commit()
    conn.close()

def add_application(hwid, contact):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO applications (hwid, contact) VALUES (?, ?)', (hwid, contact))
    conn.commit()
    conn.close()

def get_applications(status=None):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    if status:
        c.execute('SELECT * FROM applications WHERE status = ? ORDER BY created_at DESC', (status,))
    else:
        c.execute('SELECT * FROM applications ORDER BY created_at DESC')
    rows = c.fetchall()
    conn.close()
    return [dict(ix) for ix in rows]

def update_application_status(app_id, status, license_key=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if license_key:
        c.execute('UPDATE applications SET status = ?, license_key = ? WHERE id = ?', (status, license_key, app_id))
    else:
        c.execute('UPDATE applications SET status = ? WHERE id = ?', (status, app_id))
    conn.commit()
    conn.close()

def add_order(transaction_id, hwid, license_key):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO orders (transaction_id, hwid, license_key) VALUES (?, ?, ?)', (transaction_id, hwid, license_key))
    conn.commit()
    conn.close()

def get_orders():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM orders ORDER BY created_at DESC')
    rows = c.fetchall()
    conn.close()
    return [dict(ix) for ix in rows]

def is_transaction_used(transaction_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT 1 FROM orders WHERE transaction_id = ?', (transaction_id,))
    row = c.fetchone()
    conn.close()
    return row is not None

if __name__ == "__main__":
    init_db()
    print("Database initialized.")
