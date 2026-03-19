
import os
import sys
import traceback

POSSIBLE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(POSSIBLE_ROOT)

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "BOOT_LOG.txt")

def log(msg):
    with open(LOG_FILE, "a") as f:
        f.write(msg + "\n")
    print(msg)

if os.path.exists(LOG_FILE):
    os.remove(LOG_FILE)

log(f"Starting debug boot...")
log(f"Added to sys.path: {POSSIBLE_ROOT}")
log(f"Current CWD: {os.getcwd()}")
log(f"Python executable: {sys.executable}")

try:
    log("Attempting to import database...")
    import database
    log("Import details: " + str(database))
    log("database imported successfully.")
except Exception:
    log("Failed to import database.")
    log(traceback.format_exc())

try:
    log("Attempting to import face_model...")
    import face_model
    log("face_model imported successfully.")
except Exception:
    log("Failed to import face_model.")
    log(traceback.format_exc())

try:
    log("Attempting to load utils...")
    import utils
    log("utils imported successfully.")
except Exception:
    log("Failed to import utils.")
    log(traceback.format_exc())

try:
    log("Attempting to setup Django...")
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_backend.settings')
    import django
    django.setup()
    log("Django setup successful.")
except Exception:
    log("Failed to setup Django.")
    log(traceback.format_exc())
