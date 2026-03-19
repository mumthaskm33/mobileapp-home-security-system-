import database
import json

try:
    print("Testing get_connection...")
    conn = database.get_connection()
    print("Connection successful!")
    conn.close()

    print("Testing get_intruders()...")
    intruders = database.get_intruders()
    print(f"Intruders type: {type(intruders)}")
    print(f"Intruders: {intruders}")
    
    print("Testing get_authorized_users()...")
    users = database.get_authorized_users()
    print(f"Users: {users}")

except Exception as e:
    print(f"ERROR: {e}")
