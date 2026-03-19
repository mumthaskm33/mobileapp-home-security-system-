import mysql.connector
import sqlite3
import os
from datetime import datetime

# CONFIGURATION
# Set checking environment variable or default to 'SQLITE' for portability
DB_TYPE = os.environ.get('DB_TYPE', 'MYSQL')  # Options: 'MYSQL', 'SQLITE'

def get_connection():
    if DB_TYPE == 'MYSQL':
        # Need dictionary cursor for compatibility
        return mysql.connector.connect(
            host="127.0.0.1",
            user="root",          # change if different
            password="root",          # 🔴 put your MySQL password
            database="face_security"
        )
    else:
        # SQLite Connection
        conn = sqlite3.connect('face_security.db', check_same_thread=False)
        conn.row_factory = sqlite3.Row # Access columns by name
        return conn

def execute_query(query, params=(), commit=False, fetch=False):
    """Helper to execute queries compatibly across DBs"""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True) if DB_TYPE == 'MYSQL' else conn.cursor()
    
    try:
        # Compatibility: Replace %s with ? for SQLite
        if DB_TYPE == 'SQLITE':
            query = query.replace('%s', '?').replace('NOW()', "datetime('now', 'localtime')")
        
        cursor.execute(query, params)
        
        if commit:
            conn.commit()
            
        if fetch:
            if DB_TYPE == 'SQLITE':
                # Convert Row objects to dict for compatibility
                return [dict(row) for row in cursor.fetchall()]
            return cursor.fetchall()
            
    finally:
        cursor.close()
        conn.close()

def insert_intruder(date, time, image_path):
    sql = """
        INSERT INTO intruders (date, time, image_path, status)
        VALUES (%s, %s, %s, %s)
    """
    execute_query(sql, (date, time, image_path, "UNAUTHORIZED"), commit=True)

def insert_authorized_user(name, embedding_path, face_image_path):
    # Note: SQLite doesn't have NOW(), handled in execute_query helper
    sql = """
        INSERT INTO authorized_users (name, embedding_path, face_image_path, registered_at)
        VALUES (%s, %s, %s, NOW())
    """
    execute_query(sql, (name, embedding_path, face_image_path), commit=True)

def get_intruders():
    return execute_query("SELECT * FROM intruders ORDER BY id DESC", fetch=True)

def get_authorized_users():
    return execute_query("SELECT * FROM authorized_users ORDER BY id DESC", fetch=True)

def clear_intruders():
    execute_query("DELETE FROM intruders", commit=True)

def get_intruder_by_id(intruder_id):
    results = execute_query("SELECT * FROM intruders WHERE id = %s", (intruder_id,), fetch=True)
    return results[0] if results else None

def delete_intruder(intruder_id):
    execute_query("DELETE FROM intruders WHERE id = %s", (intruder_id,), commit=True)

def get_authorized_user_by_id(user_id):
    results = execute_query("SELECT * FROM authorized_users WHERE id = %s", (user_id,), fetch=True)
    return results[0] if results else None

def delete_authorized_user(user_id):
    execute_query("DELETE FROM authorized_users WHERE id = %s", (user_id,), commit=True)

# Initialize SQLite tables if needed
if DB_TYPE == 'SQLITE':
    conn = get_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS intruders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT,
                    time TEXT,
                    image_path TEXT,
                    status TEXT DEFAULT 'UNAUTHORIZED',
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS authorized_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    embedding_path TEXT,
                    face_image_path TEXT,
                    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
    conn.commit()
    conn.close()
elif DB_TYPE == 'MYSQL':
    try:
        # First ensure the database exists
        temp_conn = mysql.connector.connect(host="127.0.0.1", user="root", password="root")
        temp_cursor = temp_conn.cursor()
        temp_cursor.execute("CREATE DATABASE IF NOT EXISTS face_security")
        temp_cursor.close()
        temp_conn.close()

        # Connect and create tables
        conn = get_connection()
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS intruders (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        date VARCHAR(50),
                        time VARCHAR(50),
                        image_path VARCHAR(255),
                        status VARCHAR(50) DEFAULT 'UNAUTHORIZED',
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )''')
        c.execute('''CREATE TABLE IF NOT EXISTS authorized_users (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        name VARCHAR(255),
                        embedding_path VARCHAR(255),
                        face_image_path VARCHAR(255),
                        registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )''')
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error initializing MySQL database: {e}")
