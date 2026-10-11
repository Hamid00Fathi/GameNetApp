import database
from datetime import datetime
from typing import Optional, Tuple, List

def add_system(name: str, price_per_hour: int) -> None:
    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO systems (name, price_per_hour, last_update_time)
        VALUES (?, ?, datetime('now'))
    """, (name, price_per_hour))
    conn.commit()
    conn.close()

def remove_system(system_id: int) -> None:
    conn = database.get_connection()
    cursor = conn.cursor()
    # Delete dependent history in FK-safe order.
    cursor.execute("DELETE FROM session_rate_changes WHERE session_id IN (SELECT id FROM sessions WHERE system_id = ?)", (system_id,))
    cursor.execute("DELETE FROM session_snacks WHERE session_id IN (SELECT id FROM sessions WHERE system_id = ?)", (system_id,))
    cursor.execute("DELETE FROM sessions WHERE system_id = ?", (system_id,))
    # حذف نرخ‌ها (ps_rates)
    cursor.execute("DELETE FROM ps_rates WHERE system_id = ?", (system_id,))
    # حذف خود سیستم
    cursor.execute("DELETE FROM systems WHERE id = ?", (system_id,))
    conn.commit()
    conn.close()

def get_all_systems() -> List[Tuple[int, str, int]]:
    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name, price_per_hour
        FROM systems
        ORDER BY CAST(substr(name, 3) AS INTEGER) ASC
    """)
    systems = cursor.fetchall()
    conn.close()
    return systems

def get_system_by_id(system_id: int) -> Optional[Tuple[int, str, int]]:
    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name, price_per_hour
        FROM systems
        WHERE id = ?
    """, (system_id,))
    system = cursor.fetchone()
    conn.close()
    return system

def update_price_per_hour(system_id: int, new_price: int) -> None:
    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE systems
        SET price_per_hour = ?
        WHERE id = ?
    """, (new_price, system_id))
    conn.commit()
    conn.close()

def update_system(system_id: int, name: str, price_per_hour: int) -> None:
    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE systems
        SET name = ?, price_per_hour = ?
        WHERE id = ?
    """, (name, price_per_hour, system_id))
    conn.commit()
    conn.close()

def system_name_exists(name: str) -> bool:
    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM systems WHERE name = ?", (name,))
    system = cursor.fetchone()
    conn.close()
    return system is not None

def get_rate_count(system_id: int) -> int:
    conn = database.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM ps_rates WHERE system_id=?", (system_id,))
    r = cur.fetchone()
    conn.close()
    return r[0] if r else 0

def get_price_per_hour(conn, system_id: int, controllers_count: int = 1) -> int:
    """Compatibility helper used by the main window and legacy callers."""
    return database.get_price_per_hour(conn, system_id, controllers_count)


def get_price_per_hour_wrapper(system_id: int, controllers_count: int = 1) -> int:
    conn = database.get_connection()
    try:
        return get_price_per_hour(conn, system_id, controllers_count)
    finally:
        conn.close()

def add_or_update_rate(system_id: int, controllers_count: int, price_per_hour: int, name: Optional[str] = None) -> None:
    conn = database.get_connection()
    cur = conn.cursor()
    if name is not None:
        cur.execute("""
            INSERT INTO ps_rates (system_id, controllers_count, price_per_hour, name)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(system_id, controllers_count) DO UPDATE SET price_per_hour=excluded.price_per_hour, name=excluded.name
        """, (system_id, controllers_count, price_per_hour, name))
    else:
        cur.execute("""
            INSERT INTO ps_rates (system_id, controllers_count, price_per_hour)
            VALUES (?, ?, ?)
            ON CONFLICT(system_id, controllers_count) DO UPDATE SET price_per_hour=excluded.price_per_hour
        """, (system_id, controllers_count, price_per_hour))
    conn.commit()
    conn.close()

def start_session(conn_or_none, system_id: int, customer_id: Optional[int] = None, controllers_count: int = 1, start_time: Optional[str] = None) -> int:
    own_conn = False
    if conn_or_none is None:
        conn = database.get_connection()
        own_conn = True
    else:
        conn = conn_or_none

    cur = conn.cursor()
    try:
        # Serialize competing start requests and reject missing/busy systems.
        cur.execute("BEGIN IMMEDIATE")
        cur.execute("SELECT active FROM systems WHERE id=?", (system_id,))
        system_row = cur.fetchone()
        if system_row is None:
            raise ValueError(f"System {system_id} does not exist")
        cur.execute(
            "SELECT id FROM sessions WHERE system_id=? AND end_time IS NULL LIMIT 1",
            (system_id,),
        )
        if cur.fetchone() is not None:
            raise ValueError(f"System {system_id} already has an open session")
        if int(system_row[0] or 0) != 0:
            raise ValueError(f"System {system_id} is not available")

        now = start_time or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute("""
            INSERT INTO sessions (system_id, customer_id, start_time, paused_seconds, controllers_count)
            VALUES (?, ?, ?, 0, ?)
        """, (system_id, customer_id, now, controllers_count))
        session_id = cur.lastrowid
        cur.execute(
            "UPDATE systems SET active=1, customer_id=?, last_update_time=? WHERE id=?",
            (customer_id, now, system_id),
        )
        conn.commit()
        return session_id
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        if own_conn:
            conn.close()

def change_controllers_keep_session(conn_or_none, system_id: int, new_controllers_count: int) -> Optional[int]:
    own_conn = False
    if conn_or_none is None:
        conn = database.get_connection()
        own_conn = True
    else:
        conn = conn_or_none
    cur = conn.cursor()

    cur.execute("SELECT id FROM sessions WHERE system_id=? AND end_time IS NULL ORDER BY id DESC LIMIT 1", (system_id,))
    row = cur.fetchone()
    if not row:
        if own_conn:
            conn.close()
        return None
    session_id = row[0]

    try:
        cur.execute("UPDATE sessions SET controllers_count=? WHERE id=?", (new_controllers_count, session_id))
        conn.commit()
    finally:
        if own_conn:
            conn.close()
    return session_id


def change_rate_mid_session(conn_or_none, system_id: int, new_rate_id: int, source_system_id: int = None, source_note: str = ""):
    from datetime import datetime
    own_conn = False
    if conn_or_none is None:
        conn = database.get_connection()
        own_conn = True
    else:
        conn = conn_or_none
    cur = conn.cursor()

    cur.execute("SELECT id, controllers_count FROM sessions WHERE system_id=? AND end_time IS NULL ORDER BY id DESC LIMIT 1", (system_id,))
    s = cur.fetchone()
    if not s:
        if own_conn:
            conn.close()
        return None
    session_id, old_controllers = s

    cur.execute("SELECT new_rate_id FROM session_rate_changes WHERE session_id=? ORDER BY datetime(changed_at) DESC, id DESC LIMIT 1", (session_id,))
    rcur = cur.fetchone()
    old_rate_id = rcur[0] if rcur else None

    # انتخاب دوبارهٔ همان تعرفه تغییر واقعی نیست؛ تاریخچهٔ سشن را آلوده نکن.
    if old_rate_id is not None and int(old_rate_id) == int(new_rate_id):
        if own_conn:
            conn.close()
        return session_id

    cur.execute("SELECT controllers_count FROM ps_rates WHERE id=? LIMIT 1", (new_rate_id,))
    rnew = cur.fetchone()
    new_controllers = int(rnew[0]) if rnew and rnew[0] is not None else old_controllers

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        cur.execute("BEGIN IMMEDIATE")
        cur.execute(
            "INSERT INTO session_rate_changes (session_id, old_rate_id, new_rate_id, changed_at, source_system_id, source_note) VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, old_rate_id, new_rate_id, now_str, source_system_id, source_note)
        )
        cur.execute("UPDATE sessions SET controllers_count=? WHERE id=?", (new_controllers, session_id))
        if own_conn:
            conn.commit()
    except Exception:
        if own_conn:
            conn.rollback()
            conn.close()
        raise

    if own_conn:
        conn.close()
    return session_id



def recover_interrupted_session(conn, session_id: int, system_id: int, last_update_dt: datetime) -> Tuple[int, int]:
    """Persist elapsed time and accrued billing before pausing a session after a crash/power loss.

    ``last_update_dt`` is the last heartbeat saved by the UI timer, so we do not
    bill the unknown interval after the machine stopped updating its heartbeat.
    Returns (total_elapsed_seconds, accrued_cost). Raises on failure so callers
    can roll back instead of silently losing the accrued amount.
    """
    cur = conn.cursor()
    cur.execute(
        "SELECT start_time, paused_seconds, cost FROM sessions WHERE id=? AND system_id=? AND end_time IS NULL",
        (session_id, system_id),
    )
    row = cur.fetchone()
    if not row:
        raise ValueError("No open session found for interrupted system")

    start_time, paused_seconds, saved_cost = row
    paused_seconds = max(0, int(paused_seconds or 0))
    saved_cost = max(0, int(saved_cost or 0))

    # Already paused: preserve the persisted totals; do not accrue time while off.
    if not start_time:
        return paused_seconds, saved_cost

    try:
        start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid session start_time; refusing unsafe recovery") from exc

    cutoff = max(start_dt, last_update_dt)
    elapsed = max(0, int((cutoff - start_dt).total_seconds()))
    total_seconds = paused_seconds + elapsed

    # Calculate and persist the final running interval before clearing start_time.
    # Without this snapshot, checkout after a restart knows the total cost but
    # cannot show the start/end clock times for the last interval.
    calc_cost, running_segments, _accum_cost, _accum_details = (
        calc_session_cost_and_segments(conn, session_id, system_id, until_dt=cutoff)
    )
    accrued_cost = max(saved_cost, int(calc_cost or 0))

    cur.execute("SELECT name FROM systems WHERE id=?", (system_id,))
    system_row = cur.fetchone()
    system_name = system_row[0] if system_row and system_row[0] else f"سیستم {system_id}"
    persist_cost_segments(conn, session_id, system_id, system_name, running_segments)

    cur.execute(
        "UPDATE sessions SET cost=?, paused_seconds=?, start_time=NULL WHERE id=?",
        (accrued_cost, total_seconds, session_id),
    )
    return total_seconds, accrued_cost


def calculate_checkout_totals(session_cost, transfer_cost=0, snack_cost=0, discount=0):
    """Return normalized checkout subtotals; discount is a fixed currency amount."""
    def amount(value):
        try:
            return max(0, int(str(value if value is not None else 0).replace(",", "").strip() or 0))
        except (TypeError, ValueError, OverflowError):
            return 0

    session_cost = amount(session_cost)
    transfer_cost = amount(transfer_cost)
    snack_cost = amount(snack_cost)
    discount = amount(discount)
    subtotal = session_cost + transfer_cost + snack_cost
    discount = min(discount, subtotal)
    return {
        "session_cost": session_cost,
        "transfer_cost": transfer_cost,
        "snack_cost": snack_cost,
        "discount": discount,
        "subtotal": subtotal,
        "total": subtotal - discount,
    }


def persist_cost_segments(conn, session_id: int, system_id: int, system_name: str, segments):
    """Persist completed running intervals so checkout can explain cumulative cost.

    Only positive-duration intervals are stored. The rate name and price are
    snapshots, so later tariff edits/deletions cannot rewrite an old receipt.
    Caller owns the transaction and should commit together with the pause.
    """
    cur = conn.cursor()
    saved = 0
    for segment in segments or []:
        try:
            start_dt, end_dt, rate_id, rate_name, rate_price, seconds, cost = segment
            seconds = max(0, int(seconds or 0))
            cost = max(0, int(cost or 0))
            if seconds <= 0:
                continue
            start_text = start_dt.strftime("%Y-%m-%d %H:%M:%S") if hasattr(start_dt, "strftime") else str(start_dt)
            end_text = end_dt.strftime("%Y-%m-%d %H:%M:%S") if hasattr(end_dt, "strftime") else str(end_dt)
            # Idempotency guard: a repeated stop/transfer callback must not
            # create the same billing interval twice. SQLite's NULL semantics
            # mean rate_id is compared with IS rather than =.
            cur.execute("""
                SELECT 1 FROM session_cost_segments
                WHERE session_id=? AND system_id IS ? AND start_time=? AND end_time=?
                  AND rate_id IS ? AND rate_price=? AND elapsed_seconds=? AND cost=?
                LIMIT 1
            """, (session_id, system_id, start_text, end_text, rate_id,
                  max(0, int(float(rate_price or 0))), seconds, cost))
            if cur.fetchone():
                continue
            cur.execute("""
                INSERT INTO session_cost_segments
                    (session_id, system_id, system_name, rate_id, rate_name, rate_price,
                     start_time, end_time, elapsed_seconds, cost)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (session_id, system_id, str(system_name or ""), rate_id,
                  str(rate_name or ""), max(0, int(float(rate_price or 0))),
                  start_text, end_text, seconds, cost))
            saved += 1
        except (TypeError, ValueError, OverflowError):
            # A malformed display segment must not make pausing lose session state.
            continue
    return saved


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
        # Paused sessions must use their recorded tariff, not the legacy base price.
        rate = None
        try:
            cur.execute("SELECT new_rate_price, new_rate_id FROM session_rate_changes WHERE session_id=? ORDER BY datetime(changed_at) DESC, id DESC LIMIT 1", (session_id,))
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

    # فقط تغییرهایی را در محاسبه وارد کن که تا زمان محاسبه رخ داده‌اند.
    # تغییرهای آینده نباید نرخ بازهٔ پایانی را تغییر دهند.
    applicable_changes = []

    # پردازش هر تغییر نرخ به ترتیب زمانی
    for old_id, new_id, ch_at, src_sys, src_note, old_rate_price, old_rate_name, new_rate_price, new_rate_name in changes:
        try:
            ch_dt = datetime.strptime(ch_at, "%Y-%m-%d %H:%M:%S")
        except Exception:
            # اگر تاریخ تغییر نامعتبر است، آن تغییر را نادیده بگیر
            continue

        # اگر تغییر بعد از until_dt باشد، از حلقه خارج شو
        if ch_dt > until_dt:
            break
        # Clamp stale history to session start so no cost is charged before the session began.
        if ch_dt < seg_start:
            ch_dt = seg_start
        applicable_changes.append((old_id, new_id, ch_at, src_sys, src_note, old_rate_price, old_rate_name, new_rate_price, new_rate_name))

        # تعیین نرخ برای بازهٔ فعلی: ابتدا تلاش کن از old_id استفاده کنی
        rate_id = None
        rate_name = None
        rate_val = None
        if old_rate_price is not None:
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
    if applicable_changes:
        last_change = applicable_changes[-1]
        last_new = last_change[1]
        if last_change[7] is not None:
            last_rate_val = to_float_safe(last_change[7], 0.0)
            last_rate_name = last_change[8]
            last_rate_id = last_new
        elif last_new:
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