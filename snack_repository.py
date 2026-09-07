import sqlite3


def get_snacks():
    conn = sqlite3.connect("gamenet.db")
    cursor = conn.cursor()

    cursor.execute("SELECT id , name ,price FROM snacks ORDER BY name ASC")

    rows = cursor.fetchall()

    conn.close()
    return rows

def add_snack(name ,price):
    conn = sqlite3.connect("gamenet.db")
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO snacks (name, price)
        VALUES (?, ?)
    """ , (name, price))
    conn.commit()
    conn.close()

def snack_name_exists(name):
    conn = sqlite3.connect("gamenet.db")
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM snacks WHERE name = ?" , (name,))
    result = cursor.fetchone()

    conn.close()
    return result is not None

def delete_snack(snack_id):
    conn = sqlite3.connect("gamenet.db")
    cursor = conn.cursor()

    cursor.execute("DELETE FROM snacks WHERE id = ?" , (snack_id,))

    conn.commit()
    conn.close()
