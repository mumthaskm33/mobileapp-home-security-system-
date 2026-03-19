import smtplib
import ssl
from email.message import EmailMessage
import os
from datetime import datetime
import threading
import time

# =========================================================
try:
    from config import EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECEIVER
except ImportError:
    print("⚠️ Config file not found. Email alerts will not work.")
    EMAIL_SENDER = None
    EMAIL_PASSWORD = None
    EMAIL_RECEIVER = None

# Cooldown to prevent spam (in seconds)
ALERT_COOLDOWN = 60

# =========================================================

last_alert_time = 0

def send_email_thread(image_path, timestamp):
    """Function to run in a separate thread so it doesn't block the camera"""
    try:
        msg = EmailMessage()
        msg['Subject'] = f"🚨 INTRUDER ALERT! - {timestamp}"
        msg['From'] = EMAIL_SENDER
        msg['To'] = EMAIL_RECEIVER
        
        body = f"""
        ⚠️ INTRUDER DETECTED!
        
        Time: {timestamp}
        
        See attached photo.
        """
        msg.set_content(body)

        if os.path.exists(image_path):
            with open(image_path, 'rb') as f:
                img_data = f.read()
                msg.add_attachment(img_data, maintype='image', subtype='jpeg', filename="intruder.jpg")

        context = ssl.create_default_context()
        
        print("📧 Sending email alert...")
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
            print("✅ Email Alert Sent Successfully!")
            
    except Exception as e:
        print(f"❌ Failed to send email: {e}")

def trigger_alert(image_path):
    """Checks cooldown and triggers the email thread"""
    global last_alert_time
    
    # Check if credentials are set
    if not EMAIL_SENDER or not EMAIL_PASSWORD:
        print("⚠️ Email Alert Skipped: Please configure email credentials in config.py")
        return

    current_time = time.time()
    
    if current_time - last_alert_time < ALERT_COOLDOWN:
        print("⏳ Alert skipped (Cooldown active)")
        return

    last_alert_time = current_time
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Run in background thread to keep app fast
    t = threading.Thread(target=send_email_thread, args=(image_path, timestamp))
    t.start()
