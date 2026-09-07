from database import get_connection

def add_system(name , price_per_hour):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO systems (name , price_per_hour)
        VALUES (? , ?)
    """ , (name , price_per_hour))

    conn.commit()
    conn.close()

def remove_system(system_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM systems WHERE id = ?" , (system_id , ))

    conn.commit()
    conn.close()

def get_all_systems():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, name , price_per_hour FROM systems ORDER BY name ASC")
    systems = cursor.fetchall()

    conn.close()
    return systems

def get_system_by_id(system_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id , name , price_per_hour FROM systems WHERE id=?" , (system_id, ))

    system = cursor.fetchone()

    conn.close()
    return system

def update_price_per_hour(system_id , new_price):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE systems
        WHERE id = ?
    """ , (new_price , system_id))

    conn.commit()
    conn.close()


def update_system(system_id , name , price_per_hour):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("UPDATE systems SET name = ? , price_per_hour = ?  WHERE id = ?" , (name , price_per_hour , system_id))

    conn.commit()
    conn.close()

def system_name_exists(name):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM systems WHERE name = ?" , (name,))
    systems = cursor.fetchone()
    
    conn.close()
    return systems is not None