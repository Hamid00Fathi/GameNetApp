import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "gamenet.db")

def get_connection():
    """Open the single application database with consistent SQLite settings."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA busy_timeout = 10000")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

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
            start_delay_seconds INTEGER DEFAULT 0,
            FOREIGN KEY(customer_id) REFERENCES customers(id)
        )
    """)

    # جدول ps_rates برای چندتعرفه‌ای‌ها
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ps_rates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            system_id INTEGER NOT NULL,
            controllers_count INTEGER NOT NULL DEFAULT 1,
            price_per_hour INTEGER NOT NULL DEFAULT 0,
            name TEXT,
            FOREIGN KEY(system_id) REFERENCES systems(id) ON DELETE CASCADE,
            UNIQUE(system_id, controllers_count)
        )
    """)

    # جدول خوراکی‌ها و دسته‌بندی
    cur.execute("""
        CREATE TABLE IF NOT EXISTS food_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS foods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER,
            name TEXT NOT NULL,
            price INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1,
            FOREIGN KEY(category_id) REFERENCES food_categories(id) ON DELETE SET NULL
        )
    """)

    # جدول سشن‌ها (اضافه کردن controllers_count)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            system_id INTEGER NOT NULL,
            customer_id INTEGER,
            start_time TEXT,
            end_time TEXT,
            paused_seconds INTEGER DEFAULT 0,
            controllers_count INTEGER DEFAULT 1,
            cost INTEGER DEFAULT 0,
            snack_cost INTEGER DEFAULT 0,
            FOREIGN KEY(system_id) REFERENCES systems(id),
            FOREIGN KEY(customer_id) REFERENCES customers(id)
        )
    """)

    # جدول تاریخچه تغییر تعرفه برای هر سشن
    cur.execute("""
        CREATE TABLE IF NOT EXISTS session_rate_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            old_rate_id INTEGER,
            new_rate_id INTEGER,
            changed_at TEXT NOT NULL,
            source_system_id INTEGER DEFAULT NULL,
            source_note TEXT DEFAULT '',
            old_rate_price INTEGER,
            old_rate_name TEXT,
            new_rate_price INTEGER,
            new_rate_name TEXT,
            FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
        )
    """)

    # تفکیک هزینهٔ هر بازهٔ اجرا برای نمایش دقیق فاکتور پس از توقف/ادامه.
    # این جدول افزایشی است و با دیتابیس‌های قدیمی هم سازگار می‌ماند.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS session_cost_segments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            system_id INTEGER,
            system_name TEXT NOT NULL DEFAULT '',
            rate_id INTEGER,
            rate_name TEXT NOT NULL DEFAULT '',
            rate_price INTEGER NOT NULL DEFAULT 0,
            start_time TEXT,
            end_time TEXT,
            elapsed_seconds INTEGER NOT NULL DEFAULT 0,
            cost INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_session_cost_segments_session ON session_cost_segments(session_id, id)")

    # جدول خوراکی‌های مصرف‌شده در هر سشن
    cur.execute("""
        CREATE TABLE IF NOT EXISTS session_snacks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            snack_id INTEGER,
            quantity INTEGER NOT NULL,
            name_snapshot TEXT,
            price_snapshot INTEGER,
            FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE,
            FOREIGN KEY(snack_id) REFERENCES foods(id) ON DELETE SET NULL
        )
    """)

    # جدول درخواست‌های زمان‌بندی استارت
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_start_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            system_id INTEGER NOT NULL,
            user_identifier TEXT,
            requested_start_at TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            status TEXT DEFAULT 'pending',
            FOREIGN KEY(system_id) REFERENCES systems(id) ON DELETE CASCADE
        )
    """)

    # Safe additive migrations for existing installations.
    def ensure_column(table, column, definition):
        cur.execute(f"PRAGMA table_info({table})")
        existing = {row[1] for row in cur.fetchall()}
        if column not in existing:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    for column, definition in (
        ("old_rate_price", "INTEGER"), ("old_rate_name", "TEXT"),
        ("new_rate_price", "INTEGER"), ("new_rate_name", "TEXT"),
    ):
        ensure_column("session_rate_changes", column, definition)
    ensure_column("session_snacks", "name_snapshot", "TEXT")
    ensure_column("session_snacks", "price_snapshot", "INTEGER")
    ensure_column("sessions", "discount", "INTEGER DEFAULT 0")

    # Older databases declared new_rate_id NOT NULL. A transfer to a single-rate
    # system has no ps_rates row, so allow a NULL ID while retaining price/name
    # snapshots as the authoritative history. Rebuild only when needed.
    cur.execute("PRAGMA table_info(session_rate_changes)")
    rate_columns = {row[1]: row for row in cur.fetchall()}
    if rate_columns.get("new_rate_id") and rate_columns["new_rate_id"][3]:
        cur.execute("DROP TRIGGER IF EXISTS trg_snapshot_session_rate_change")
        cur.execute("ALTER TABLE session_rate_changes RENAME TO session_rate_changes_legacy")
        cur.execute("""CREATE TABLE session_rate_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            old_rate_id INTEGER,
            new_rate_id INTEGER,
            changed_at TEXT NOT NULL,
            source_system_id INTEGER DEFAULT NULL,
            source_note TEXT DEFAULT '',
            old_rate_price INTEGER,
            old_rate_name TEXT,
            new_rate_price INTEGER,
            new_rate_name TEXT,
            FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
        )""")
        cur.execute("""INSERT INTO session_rate_changes
            (id, session_id, old_rate_id, new_rate_id, changed_at, source_system_id,
             source_note, old_rate_price, old_rate_name, new_rate_price, new_rate_name)
            SELECT id, session_id, old_rate_id, new_rate_id, changed_at, source_system_id,
                   source_note, old_rate_price, old_rate_name, new_rate_price, new_rate_name
            FROM session_rate_changes_legacy""")
        cur.execute("DROP TABLE session_rate_changes_legacy")

    # Preserve the tariff values at the moment each history row is created.
    cur.executescript("""
    CREATE TRIGGER IF NOT EXISTS trg_snapshot_session_rate_change
    AFTER INSERT ON session_rate_changes
    BEGIN
      UPDATE session_rate_changes SET
        old_rate_price = COALESCE(NEW.old_rate_price,
          (SELECT prior.new_rate_price FROM session_rate_changes prior
           WHERE prior.session_id=NEW.session_id AND prior.new_rate_id=NEW.old_rate_id AND prior.id<NEW.id
           ORDER BY prior.id DESC LIMIT 1),
          (SELECT price_per_hour FROM ps_rates WHERE id=NEW.old_rate_id)),
        old_rate_name = COALESCE(NEW.old_rate_name,
          (SELECT prior.new_rate_name FROM session_rate_changes prior
           WHERE prior.session_id=NEW.session_id AND prior.new_rate_id=NEW.old_rate_id AND prior.id<NEW.id
           ORDER BY prior.id DESC LIMIT 1),
          (SELECT name FROM ps_rates WHERE id=NEW.old_rate_id)),
        new_rate_price = COALESCE(NEW.new_rate_price, (SELECT price_per_hour FROM ps_rates WHERE id=NEW.new_rate_id)),
        new_rate_name = COALESCE(NEW.new_rate_name, (SELECT name FROM ps_rates WHERE id=NEW.new_rate_id))
      WHERE id=NEW.id;
    END;
    CREATE TRIGGER IF NOT EXISTS trg_snapshot_session_snack
    AFTER INSERT ON session_snacks
    BEGIN
      UPDATE session_snacks SET
        name_snapshot = COALESCE(NEW.name_snapshot, (SELECT name FROM foods WHERE id=NEW.snack_id)),
        price_snapshot = COALESCE(NEW.price_snapshot, (SELECT price FROM foods WHERE id=NEW.snack_id))
      WHERE id=NEW.id;
    END;
    """)
    # Backfill old records once; values already captured are never overwritten.
    cur.execute("""UPDATE session_rate_changes SET
        old_rate_price=COALESCE(old_rate_price,(SELECT price_per_hour FROM ps_rates WHERE id=old_rate_id)),
        old_rate_name=COALESCE(old_rate_name,(SELECT name FROM ps_rates WHERE id=old_rate_id)),
        new_rate_price=COALESCE(new_rate_price,(SELECT price_per_hour FROM ps_rates WHERE id=new_rate_id)),
        new_rate_name=COALESCE(new_rate_name,(SELECT name FROM ps_rates WHERE id=new_rate_id))
    WHERE old_rate_price IS NULL OR new_rate_price IS NULL""")
    cur.execute("""UPDATE session_snacks SET
        name_snapshot=COALESCE(name_snapshot,(SELECT name FROM foods WHERE id=snack_id)),
        price_snapshot=COALESCE(price_snapshot,(SELECT price FROM foods WHERE id=snack_id))
    WHERE name_snapshot IS NULL OR price_snapshot IS NULL""")

    conn.commit()
    conn.close()



def get_price_per_hour(conn, system_id: int, controllers_count: int = 1) -> int:
    """Return the applicable hourly rate without falling back to a stale base rate for multi-rate systems."""
    cur = conn.cursor()
    cur.execute(
        "SELECT price_per_hour FROM ps_rates WHERE system_id=? AND controllers_count=? LIMIT 1",
        (system_id, controllers_count),
    )
    row = cur.fetchone()
    if row and row[0] is not None:
        return int(row[0])

    # Multi-rate systems must use an actual configured tariff, never the legacy base price.
    cur.execute(
        "SELECT price_per_hour FROM ps_rates WHERE system_id=? ORDER BY controllers_count ASC, id ASC LIMIT 1",
        (system_id,),
    )
    row = cur.fetchone()
    if row and row[0] is not None:
        return int(row[0])

    cur.execute("SELECT price_per_hour FROM systems WHERE id=? LIMIT 1", (system_id,))
    row = cur.fetchone()
    return int(row[0] or 0) if row else 0


def get_systems():
    systems_out = []
    now = datetime.now()

    conn = get_connection()
    cur = conn.cursor()

    # خواندن همهٔ سیستم‌ها
    cur.execute("""
        SELECT id, name, active, note, customer_id, price_per_hour, cost
        FROM systems
        ORDER BY CAST(substr(name, 3) AS INTEGER) ASC
    """)
    rows = cur.fetchall()

    for row in rows:
        sys_id, name, active, note, customer_id, base_price_per_hour, system_cost = row

        # مقداردهی پیش‌فرض‌ها
        start_time = None
        elapsed_seconds = 0
        elapsed_str = "00:00:00"
        time_cost = 0
        snack_cost = 0
        controllers_count = 1
        price_per_hour = base_price_per_hour or 0.0

        # گرفتن سشن فعال (اگر وجود داشته باشد) و controllers_count
        cur.execute("""
            SELECT id, start_time, paused_seconds, snack_cost, controllers_count
            FROM sessions
            WHERE system_id=? AND end_time IS NULL
            LIMIT 1
        """, (sys_id,))
        session = cur.fetchone()

        if session:
            session_id, s_start_time, paused_seconds, s_snack_cost, s_controllers = session
            paused_seconds = paused_seconds or 0
            snack_cost = s_snack_cost or 0
            controllers_count = s_controllers or 1
            start_time = s_start_time
            # Resolve the selected tariff from the session history; the legacy
            # controllers_count field can be stale in older sessions.
            try:
                cur.execute("""SELECT src.new_rate_id, src.new_rate_price, src.new_rate_name,
                                      pr.controllers_count, pr.price_per_hour
                               FROM session_rate_changes src
                               LEFT JOIN ps_rates pr ON pr.id=src.new_rate_id AND pr.system_id=?
                               WHERE src.session_id=?
                               ORDER BY datetime(src.changed_at) DESC, src.id DESC LIMIT 1""", (sys_id, session_id))
                selected = cur.fetchone()
                if selected:
                    if selected[3] is not None:
                        controllers_count = int(selected[3])
                    if selected[1] is not None:
                        price_per_hour = selected[1]
                    elif selected[4] is not None:
                        price_per_hour = selected[4]
            except Exception:
                pass

            # محاسبه elapsed_seconds
            if start_time:
                try:
                    start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
                    elapsed_seconds = paused_seconds + int((now - start_dt).total_seconds())
                    if elapsed_seconds < 0:
                        elapsed_seconds = 0
                except Exception:
                    elapsed_seconds = paused_seconds
            else:
                elapsed_seconds = paused_seconds

            if not start_time:
                try:
                    time_cost = int(paused_seconds * (price_per_hour / 3600.0))
                except Exception:
                    time_cost = 0
            else:
                # مسیر فعلی که calc_session_cost_and_segments را صدا می‌زند
                time_cost, _segments, _acc, _acc_details = calc_session_cost_and_segments(conn, session_id, sys_id, until_dt=now)

            try:
                from database import get_price_per_hour as _gpph
                price_per_hour = _gpph(conn, sys_id, controllers_count)
                cur.execute("SELECT new_rate_price FROM session_rate_changes WHERE session_id=? ORDER BY datetime(changed_at) DESC, id DESC LIMIT 1", (session_id,))
                _snapshot = cur.fetchone()
                if _snapshot and _snapshot[0] is not None:
                    price_per_hour = _snapshot[0]
            except Exception:
                price_per_hour = base_price_per_hour or 0.0

            # محاسبه هزینه زمان (گرد شده به عدد صحیح)
            try:
                time_cost, _segments, _acc, _acc_details = calc_session_cost_and_segments(conn, session_id, sys_id, until_dt=now)
            except Exception:
                # fallback به روش قدیمی
                time_cost = int(elapsed_seconds * (price_per_hour / 3600))

            # ساخت رشتهٔ زمان سپری‌شده
            h = elapsed_seconds // 3600
            m = (elapsed_seconds % 3600) // 60
            s = elapsed_seconds % 60
            elapsed_str = f"{h:02}:{m:02}:{s:02}"

        else:
            controllers_count = 1
            price_per_hour = base_price_per_hour or 0.0
            elapsed_str = "00:00:00"
            time_cost = 0
            snack_cost = 0

        total_cost = (time_cost or 0) + (snack_cost or 0) + system_cost

        systems_out.append((
            sys_id,
            name,
            active,
            start_time,
            elapsed_str,
            total_cost,
            customer_id,
            note,
            controllers_count,
            price_per_hour
        ))

    conn.close()
    return systems_out


def calc_session_cost_and_segments(conn, session_id: int, sys_id: int, until_dt=None):
    # helperهای ایمن تبدیل
    def to_int_safe(v, default=0):
        try:
            if v is None:
                return default
            if isinstance(v, (int, float)):
                return int(v)
            return int(str(v).replace(",", "").strip() or default)
        except Exception:
            return default

    def to_float_safe(v, default=0.0):
        try:
            if v is None:
                return default
            if isinstance(v, (int, float)):
                return float(v)
            return float(str(v).replace(",", "").strip() or default)
        except Exception:
            return default

    if until_dt is None:
        until_dt = datetime.now()

    cur = conn.cursor()

    # خواندن اطلاعات پایهٔ سشن
    cur.execute("SELECT start_time, paused_seconds, cost FROM sessions WHERE id=?", (session_id,))
    r = cur.fetchone()
    if not r:
        # سشن وجود ندارد → بازگرداندن صفرها
        return 0, [], 0, []

    start_time, paused_seconds, accum_cost = r
    paused_seconds = to_int_safe(paused_seconds, 0)
    accum_cost = to_int_safe(accum_cost, 0)

    accum_details = []
    # اگر هزینهٔ تجمعی (accum_cost) وجود دارد، تلاش کن منبع آن را پیدا کنی
    if accum_cost and accum_cost > 0:
        cur.execute(
            "SELECT source_system_id, source_note, new_rate_id FROM session_rate_changes WHERE session_id=? ORDER BY datetime(changed_at) DESC LIMIT 1",
            (session_id,)
        )
        rr = cur.fetchone()
        if rr:
            src_sys, src_note, last_new_rate = rr
            if src_sys:
                accum_details.append({"amount": accum_cost, "note": f"انتقال از سیستم {src_sys}"})
            elif src_note and str(src_note).strip() != "":
                accum_details.append({"amount": accum_cost, "note": src_note})
            elif last_new_rate:
                cur.execute("SELECT name FROM ps_rates WHERE id=? LIMIT 1", (last_new_rate,))
                rrr = cur.fetchone()
                if rrr and rrr[0]:
                    accum_details.append({"amount": accum_cost, "note": f"هزینهٔ قبلی ({rrr[0]})"})
                else:
                    accum_details.append({"amount": accum_cost, "note": "هزینهٔ قبلی"})
        else:
            accum_details.append({"amount": accum_cost, "note": "هزینهٔ قبلی"})

    # خواندن تغییرات نرخ مرتب شده صعودی بر اساس زمان
    cur.execute(
        "SELECT old_rate_id, new_rate_id, changed_at, source_system_id, source_note, old_rate_price, old_rate_name, new_rate_price, new_rate_name "
        "FROM session_rate_changes WHERE session_id=? ORDER BY datetime(changed_at) ASC, id ASC",
        (session_id,)
    )
    changes = cur.fetchall() or []

    # اولین رکورد با old_rate_id=NULL معمولاً تعرفهٔ آغازین سشن است.
    # اگر برای شروعِ گذشته انتخاب شده باشد، آن نرخ باید از خودِ start_time اعمال شود،
    # نه از زمانی که کاربر پنجرهٔ انتخاب تعرفه را تأیید کرده است.
    if changes and changes[0][0] is None and changes[0][1] is not None and start_time:
        try:
            session_start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
            first_change_dt = datetime.strptime(changes[0][2], "%Y-%m-%d %H:%M:%S")
            if first_change_dt > session_start_dt:
                first = list(changes[0])
                first[2] = start_time
                changes[0] = tuple(first)
        except Exception:
            pass

    segments = []
    total = 0

    start_time, paused_seconds, accum_cost = r
    paused_seconds = to_int_safe(paused_seconds, 0)
    accum_cost = to_int_safe(accum_cost, 0)


    if not start_time:
        # A paused session has no start_time; use its last recorded tariff snapshot,
        # not systems.price_per_hour (which is intentionally zero for multi-rate systems).
        rate = None
        try:
            cur.execute("""SELECT new_rate_price, new_rate_id FROM session_rate_changes
                           WHERE session_id=? ORDER BY datetime(changed_at) DESC, id DESC LIMIT 1""", (session_id,))
            last = cur.fetchone()
            if last:
                if last[0] is not None:
                    rate = to_float_safe(last[0], 0.0)
                elif last[1] is not None:
                    cur.execute("SELECT price_per_hour FROM ps_rates WHERE id=?", (last[1],))
                    rr = cur.fetchone()
                    if rr: rate = to_float_safe(rr[0], 0.0)
            if rate is None:
                cur.execute("SELECT price_per_hour FROM systems WHERE id=?", (sys_id,))
                rs = cur.fetchone()
                rate = to_float_safe(rs[0], 0.0) if rs and rs[0] is not None else 0.0
        except Exception:
            rate = 0.0

        try:
            paused_cost = int(paused_seconds * (rate / 3600.0))
        except Exception:
            paused_cost = 0

        # New pauses persist the fully calculated amount in sessions.cost before
        # clearing start_time. For legacy paused rows with no saved amount, retain
        # the best-effort fallback based on the last known tariff.
        if accum_cost > 0:
            return int(accum_cost), [], int(accum_cost), accum_details
        total_with_accum = int(paused_cost)
        return total_with_accum, [], 0, accum_details


    # تبدیل start_time به datetime
    try:
        seg_start = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
    except Exception:
        # فرمت نامعتبر → بازگرداندن accum_cost
        return accum_cost, segments, accum_cost, accum_details

    # پردازش هر تغییر نرخ به ترتیب زمانی؛ تغییرات آینده نباید روی هزینهٔ فعلی اثر بگذارند.
    last_effective_new_rate = None
    last_effective_rate_price = None
    last_effective_rate_name = None
    for old_id, new_id, ch_at, src_sys, src_note, old_rate_price, old_rate_name, new_rate_price, new_rate_name in changes:
        try:
            ch_dt = datetime.strptime(ch_at, "%Y-%m-%d %H:%M:%S")
        except Exception:
            # اگر تاریخ تغییر نامعتبر است، آن تغییر را نادیده بگیر
            continue

        # اگر تغییر بعد از until_dt باشد، از حلقه خارج شو
        if ch_dt > until_dt:
            break

        # رکوردهای قبل از شروع سشن را در زمان شروع اعمال کن؛ هرگز قبل از شروع هزینه نساز.
        if ch_dt < seg_start:
            ch_dt = seg_start
        last_effective_new_rate = new_id
        last_effective_rate_price = new_rate_price
        last_effective_rate_name = new_rate_name

        # تعیین نرخ برای بازهٔ فعلی: ابتدا تلاش کن از old_id استفاده کنی
        rate_id = None
        rate_name = None
        rate_val = None
        if old_rate_price is not None:
            # Snapshots remain authoritative even when a single-rate transfer has
            # no ps_rates ID (old_id=None).
            rate_val = to_float_safe(old_rate_price, 0.0)
            rate_name = old_rate_name
            rate_id = old_id
        elif old_id:
            cur.execute("SELECT price_per_hour, name FROM ps_rates WHERE id=? LIMIT 1", (old_id,))
            rr = cur.fetchone()
            if rr:
                rate_val = to_float_safe(rr[0], 0.0)
                rate_name = rr[1] if rr[1] is not None else None
                rate_id = old_id

        # اگر هنوز نرخ مشخص نیست، fallback به نرخ سیستم
        if rate_val is None:
            cur.execute("SELECT price_per_hour FROM systems WHERE id=?", (sys_id,))
            rs = cur.fetchone()
            rate_val = to_float_safe(rs[0], 0.0) if rs else 0.0

        # اگر بازهٔ تغییر طول دارد، محاسبه کن
        if ch_dt > seg_start:
            secs = int((ch_dt - seg_start).total_seconds())
            if secs < 0:
                secs = 0
            cost_seg = int(secs * (rate_val / 3600.0))
            segments.append((seg_start, ch_dt, rate_id, rate_name, rate_val, secs, cost_seg))
            total += cost_seg

        # شروع بازهٔ بعدی از زمان تغییر
        seg_start = ch_dt

    # پس از پردازش همهٔ تغییرات تا اینجا، محاسبهٔ بازهٔ آخر تا until_dt
    # تعیین نرخ آخر (اگر تغییراتی وجود داشته باشد از last_new استفاده کن)
    last_rate_val = None
    last_rate_name = None
    last_rate_id = None
    if last_effective_rate_price is not None:
        # A snapshot can represent a single-rate destination and therefore have
        # no ps_rates ID; never fall back to the previous machine's rate.
        last_rate_val = to_float_safe(last_effective_rate_price, 0.0)
        last_rate_name = last_effective_rate_name
        last_rate_id = last_effective_new_rate
    elif last_effective_new_rate:
        last_new = last_effective_new_rate
        cur.execute("SELECT price_per_hour, name FROM ps_rates WHERE id=? LIMIT 1", (last_new,))
        rr = cur.fetchone()
        if rr:
            last_rate_val = to_float_safe(rr[0], 0.0)
            last_rate_name = rr[1] if rr[1] is not None else None
            last_rate_id = last_new

    # اگر هنوز نرخ آخر مشخص نیست، fallback به نرخ سیستم
    if last_rate_val is None:
        cur.execute("SELECT price_per_hour FROM systems WHERE id=?", (sys_id,))
        rs = cur.fetchone()
        last_rate_val = to_float_safe(rs[0], 0.0) if rs else 0.0

    # محاسبهٔ بازهٔ پایانی (اگر until_dt بعد از seg_start باشد)
    try:
        if until_dt > seg_start:
            secs = int((until_dt - seg_start).total_seconds())
        else:
            secs = 0
    except Exception:
        secs = 0
    if secs < 0:
        secs = 0
    cost_seg = int(secs * (last_rate_val / 3600.0))
    segments.append((seg_start, until_dt, last_rate_id, last_rate_name, last_rate_val, secs, cost_seg))
    total += cost_seg

    # جمع نهایی: total + accum_cost (accum_cost قبلاً جدا نگهداری شده است)
    total_with_accum = int(total) + int(accum_cost or 0)

    # بازگرداندن خروجی با فرمت ثابت
    return int(total_with_accum), segments, int(accum_cost or 0), accum_details