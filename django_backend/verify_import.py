
import os
import sys

print("Current CWD:", os.getcwd())
# Simulate manage.py path addition
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(root)
print("Root added:", root)

try:
    import database
    print("Database imported OK")
except ImportError as e:
    print("Database import FAILED:", e)

try:
    from django_backend import settings
    print("Settings imported OK")
except ImportError as e:
    print("Settings import FAILED:", e)

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_backend.settings')
try:
    django.setup()
    print("Django setup OK")
except Exception as e:
    print("Django setup FAILED:", e)
