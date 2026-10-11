import database
from typing import List, Tuple, Optional

# سه بخش ثابت مطابق create_tables تو
SECTIONS = {
    "fridge": "یخچال",
    "buffet": "بوفه",
    "food": "غذا"
}

def ensure_schema() -> None:
    conn = database.get_connection()
    cur = conn.cursor()

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
    conn.commit()

    # درج دسته‌های پیش‌فرض بر اساس نام
    for name in SECTIONS.values():
        cur.execute("INSERT OR IGNORE INTO food_categories (name) VALUES (?)", (name,))
    conn.commit()
    conn.close()

def _get_category_id_by_name(conn, name: str) -> Optional[int]:
    cur = conn.cursor()
    cur.execute("SELECT id FROM food_categories WHERE name=?", (name,))
    r = cur.fetchone()
    return r[0] if r else None

def get_snacks_by_section(section_key: str) -> List[Tuple[int, str, int]]:
    """
    section_key: 'fridge'|'buffet'|'food'
    برمی‌گرداند لیست (id, name, price) برای آیتم‌های فعال در آن بخش.
    """
    if section_key not in SECTIONS:
        return []
    conn = database.get_connection()
    cur = conn.cursor()
    cat_name = SECTIONS[section_key]
    cat_id = _get_category_id_by_name(conn, cat_name)
    if cat_id is None:
        conn.close()
        return []
    cur.execute("SELECT id, name, price FROM foods WHERE category_id=? AND active=1 ORDER BY name ASC", (cat_id,))
    rows = cur.fetchall()
    conn.close()
    return rows

def add_snack(section_key: str, name: str, price: int) -> int:
    if section_key not in SECTIONS:
        raise ValueError("section_key نامعتبر است")
    conn = database.get_connection()
    cur = conn.cursor()
    cat_name = SECTIONS[section_key]
    cat_id = _get_category_id_by_name(conn, cat_name)
    if cat_id is None:
        cur.execute("INSERT INTO food_categories (name) VALUES (?)", (cat_name,))
        conn.commit()
        cat_id = _get_category_id_by_name(conn, cat_name)
    cur.execute("INSERT INTO foods (category_id, name, price, active) VALUES (?, ?, ?, 1)", (cat_id, name, price))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id

def snack_name_exists(section_key: str, name: str) -> bool:
    if section_key not in SECTIONS:
        return False
    conn = database.get_connection()
    cur = conn.cursor()
    cat_name = SECTIONS[section_key]
    cat_id = _get_category_id_by_name(conn, cat_name)
    if cat_id is None:
        conn.close()
        return False
    cur.execute("SELECT id FROM foods WHERE category_id=? AND name=? LIMIT 1", (cat_id, name))
    r = cur.fetchone()
    conn.close()
    return r is not None

def delete_snack(snack_id: int) -> None:
    conn = database.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM session_snacks WHERE snack_id=? LIMIT 1", (snack_id,))
    if cur.fetchone():
        # Keep historical invoice references and prices intact.
        cur.execute("UPDATE foods SET active=0 WHERE id=?", (snack_id,))
    else:
        cur.execute("DELETE FROM foods WHERE id=?", (snack_id,))
    conn.commit()
    conn.close()

def update_snack(snack_id: int, new_name: str, new_price: int) -> None:
    conn = database.get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE foods SET name=?, price=? WHERE id=?", (new_name, new_price, snack_id))
    conn.commit()
    conn.close()

def get_all_sections() -> List[Tuple[str, str]]:
    return list(SECTIONS.items())