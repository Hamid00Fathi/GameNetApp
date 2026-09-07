import sqlite3


def get_customers():
    conn = sqlite3.connect("gamenet.db")
    cursor = conn.cursor()

    cursor.execute("SELECT id , name ,family , code , balance FROM customers ORDER BY balance DESC")

    rows = cursor.fetchall()

    conn.close()
    return rows

def add_customer(name ,family , code , balance):
    conn = sqlite3.connect("gamenet.db")
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO customers (name, family, code, balance)
        VALUES (?, ?, ?, ?)
    """ , (name, family, code, balance))
    conn.commit()
    conn.close()

def charge_customer(customer_id , amount):
    conn = sqlite3.connect("gamenet.db")
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE customers
        SET balance = balance + ?
        WHERE id = ?
    """ , (amount, customer_id))

    conn.commit()
    conn.close()

def get_balance(customer_id):
    conn = sqlite3.connect("gamenet.db")
    cursor = conn.cursor()

    cursor.execute("SELECT balance FROM customers WHERE id = ?" , (customer_id , ))
    balance = cursor.fetchone()[0]

    conn.close()
    return balance
