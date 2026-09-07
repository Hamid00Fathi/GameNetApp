import sqlite3
from datetime import datetime

def get_connection():
    return sqlite3.connect("gamenet.db")


def create_tables():
    conn = get_connection()
    cur = conn.cursor()

    # جدول مشتری‌ها
    cur.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            family TEXT NOT NULL,
            code TEXT NOT NULL UNIQUE,
            balance INTEGER DEFAULT 0
        )
    """)

    # جدول سیستم‌ها
    cur.execute("""
        CREATE TABLE IF NOT EXISTS systems (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price_per_hour INTEGER NOT NULL,
            active INTEGER DEFAULT 0,
            customer_id INTEGER,
            cost INTEGER DEFAULT 0,
            note TEXT DEFAULT '',
            last_update_time TEXT,
            FOREIGN KEY(customer_id) REFERENCES customers(id)
        )
    """)

    # جدول خوراکی‌ها
    cur.execute("""
        CREATE TABLE IF NOT EXISTS snacks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price INTEGER NOT NULL
        )
    """)

    # جدول سشن‌ها
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            system_id INTEGER NOT NULL,
            customer_id INTEGER,
            start_time TEXT,
            end_time TEXT,
            paused_seconds INTEGER DEFAULT 0,
            cost INTEGER DEFAULT 0,          -- هزینهٔ زمان بازی
            snack_cost INTEGER DEFAULT 0,    -- هزینهٔ خوراکی‌ها
            FOREIGN KEY(system_id) REFERENCES systems(id),
            FOREIGN KEY(customer_id) REFERENCES customers(id)
        )
    """)

    # جدول خوراکی‌های مصرف‌شده در هر سشن
    cur.execute("""
        CREATE TABLE IF NOT EXISTS session_snacks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            snack_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            FOREIGN KEY(session_id) REFERENCES sessions(id),
            FOREIGN KEY(snack_id) REFERENCES snacks(id)
        )
    """)

    conn.commit()
    conn.close()


def get_systems():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT id, name, price_per_hour, active, customer_id, cost, note FROM systems")
    systems_raw = cur.fetchall()

    systems = []

    for sys_id, name, price_per_hour, active, customer_id, sys_cost, note in systems_raw:

        # گرفتن سشن فعال
        cur.execute("""
            SELECT start_time, paused_seconds, snack_cost
            FROM sessions
            WHERE system_id=? AND end_time IS NULL
        """, (sys_id,))
        session = cur.fetchone()

        if session:
            start_time, paused_seconds, snack_cost = session

            if active == 1 and start_time:
                start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
                elapsed_seconds = (datetime.now() - start_dt).seconds
                total_seconds = paused_seconds + elapsed_seconds
            else:
                total_seconds = paused_seconds

            minutes = total_seconds // 60
            seconds = total_seconds % 60
            elapsed = f"{minutes:02d}:{seconds:02d}"

            cost_time = int((total_seconds / 60) * (price_per_hour / 60))
            cost = cost_time + (snack_cost or 0) + sys_cost

        else:
            start_time = None
            elapsed = "00:00"
            cost = sys_cost

        systems.append((sys_id, name, active, start_time, elapsed, cost, customer_id, note))

    conn.close()
    return systems