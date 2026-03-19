
import os
import sys

# Simulate what manage.py does
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print(f"Path: {sys.path}")

try:
    import database
    print("Database imported successfully")
except Exception as e:
    print(f"Failed to import database: {e}")

try:
    from django_backend import settings
    print("Settings imported")
except Exception as e:
    print(f"Failed to import settings: {e}")

try:
    import face_model
    print("face_model imported successfully")
except Exception as e:
    print(f"Failed to import face_model: {e}")
