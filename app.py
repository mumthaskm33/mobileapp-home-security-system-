from flask import Flask, render_template, request, jsonify
from flask_cors import CORS # Import CORS
import mysql.connector
import cv2
import numpy as np
import mediapipe as mp
import base64
import os
import time
from datetime import datetime
from face_model import get_embedding
from utils import recognize_face
from database import get_connection, insert_authorized_user, insert_intruder

app = Flask(__name__)
CORS(app) # Enable CORS for all routes
# Increase max upload size for images
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

# Face Detection will be initialized per-request to avoid timestamp issues

# Initialize Liveness Detector
from liveness import LivenessDetector
liveness_detector = LivenessDetector()
last_live_time = 0
LIVENESS_TIMEOUT = 5.0 # Seconds to remain "verified" after a blink

# Database connection is handled in database.py

# Database connection is handled in database.py

def base64_to_image(base64_string):
    """Convert base64 string to OpenCV image"""
    try:
        if "," in base64_string:
            base64_string = base64_string.split(",")[1]
        decoded_data = base64.b64decode(base64_string)
        np_data = np.frombuffer(decoded_data, np.uint8)
        image = cv2.imdecode(np_data, cv2.IMREAD_COLOR)
        return image
    except Exception as e:
        print(f"Error decoding image: {e}")
        return None

def detect_faces(image):
    """Detect faces using MediaPipe and return list of (face, abs_box, rel_box)"""
    if image is None: 
        return []
        
    rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    
    # Initialize MediaPipe Face Detection per request
    with mp.solutions.face_detection.FaceDetection(model_selection=0, min_detection_confidence=0.6) as face_detection:
        results = face_detection.process(rgb_image)
    
    faces = []
    
    if results.detections:
        h, w, _ = image.shape
        
        for det in results.detections:
            box = det.location_data.relative_bounding_box
            
            x = int(box.xmin * w)
            y = int(box.ymin * h)
            ww = int(box.width * w)
            hh = int(box.height * h)
            
            # Ensure coordinates are within bounds
            x = max(0, x)
            y = max(0, y)
            ww = min(ww, w - x)
            hh = min(hh, h - y)
            
            face = image[y:y+hh, x:x+ww]
            if face.size == 0:
                continue
                
            # Append result
            faces.append((face, (x, y, ww, hh), (box.xmin, box.ymin, box.width, box.height)))
            
    return faces

@app.route("/")
def dashboard():
    return render_template("dashboard.html")

@app.route("/intruders")
def intruders():
    from database import get_intruders
    data = get_intruders()
    return render_template("intruders.html", intruders=data)

@app.route("/authorized")
def authorized():
    from database import get_authorized_users
    data = get_authorized_users()
    return render_template("authorized.html", users=data)

@app.route("/api/history")
def api_history():
    try:
        from database import get_intruders
        # Fetch all and slice last 10 (or first 10 depending on sort)
        # get_intruders orders by ID DESC, so first 10 are latest.
        all_data = get_intruders()
        data = all_data[:10]
        
        # Calculate today's count
        today_str = datetime.now().strftime("%Y-%m-%d")
        today_count = sum(1 for item in all_data if str(item.get('date')) == today_str)

        # Calculate Last 7 Days Graph Data
        from datetime import timedelta, date
        chart_data = []
        chart_labels = []
        
        # Get last 7 days (including today)
        for i in range(6, -1, -1):
            day = datetime.now() - timedelta(days=i)
            day_str = day.strftime("%Y-%m-%d")
            day_name = day.strftime("%a") # Mon, Tue...
            
            # Count for this day
            count = sum(1 for item in all_data if str(item.get('date')) == day_str)
            
            chart_data.append(count)
            chart_labels.append(day_name)
             
        # Convert datetime/timedelta objects to string if necessary, handled by logic or here
        for item in data:
             for key, val in item.items():
                 if isinstance(val, (datetime, date)):
                     item[key] = val.isoformat()
                 elif isinstance(val, timedelta):
                     item[key] = str(val)
                      # Authorized users count
        try:
            from database import get_authorized_users
            auth_users = get_authorized_users()
            auth_count = len(auth_users)
        except:
            auth_count = 0
             
        return jsonify({
            "success": True, 
            "history": data, 
            "today_count": today_count,
            "chart_data": chart_data,
            "chart_labels": chart_labels,
            "auth_count": auth_count
        })
    except Exception as e:
        print(f"Error fetching history: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/intruders/<int:intruder_id>", methods=["DELETE"])
def delete_intruder_api(intruder_id):
    try:
        from database import get_intruder_by_id, delete_intruder
        intruder = get_intruder_by_id(intruder_id)
        if not intruder:
            return jsonify({"success": False, "message": "Intruder not found"}), 404
            
        # Try to delete the image file
        image_path = intruder.get("image_path")
        if image_path:
            full_path = os.path.join("static", image_path)
            if os.path.exists(full_path):
                os.remove(full_path)
                
        delete_intruder(intruder_id)
        return jsonify({"success": True})
    except Exception as e:
        print(f"Error deleting intruder: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/authorized", methods=["GET"])
def api_authorized():
    try:
        from database import get_authorized_users
        users = get_authorized_users()
        # Format timestamps if necessary
        for user in users:
            if 'registered_at' in user and isinstance(user['registered_at'], datetime):
                user['registered_at'] = user['registered_at'].isoformat()
        return jsonify({"success": True, "users": users})
    except Exception as e:
        print(f"Error fetching authorized users: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/authorized/<int:user_id>", methods=["DELETE"])
def delete_authorized_api(user_id):
    try:
        from database import get_authorized_user_by_id, delete_authorized_user
        user = get_authorized_user_by_id(user_id)
        if not user:
            return jsonify({"success": False, "message": "User not found"}), 404
            
        name = user.get("name")
        image_path = user.get("face_image_path")
        
        # 1. Delete embedding file
        # Check static folder where it was saved
        if name:
             emb_path = os.path.join("static", "authorized_faces", f"{name}.npy")
             if os.path.exists(emb_path):
                 os.remove(emb_path)
                 
             # Also try the logic from views.py that clears any UUID based files
             # Just in case they are scattered
             import glob
             for f in glob.glob(os.path.join("static", "authorized_faces", f"{name}_*.npy")):
                 try:
                     os.remove(f)
                 except:
                     pass

        # 2. Delete face image
        if image_path:
            full_img_path = os.path.join("static", image_path)
            if os.path.exists(full_img_path):
                os.remove(full_img_path)
                
        delete_authorized_user(user_id)
        return jsonify({"success": True})
    except Exception as e:
        print(f"Error deleting user: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/register", methods=["POST"])
def register():
    data = request.json
    name = data.get("name")
    image_data = data.get("image")
    
    if not name or not image_data:
        print(f"❌ Registration failed: Missing name or image (name='{name}', image len={len(image_data) if image_data else 0})")
        return jsonify({"success": False, "message": "Missing name or image"}), 400
        
    frame = base64_to_image(image_data)
    faces = detect_faces(frame)
    
    if not faces:
        print(f"❌ Registration failed: No face detected in image for user '{name}'")
        return jsonify({"success": False, "message": "No face detected. Ensure good lighting and face camera."}), 400
    
    # For registration, just use the first face detected
    face, _, _ = faces[0] 
    
    try:
        emb = get_embedding(face)
        if emb is None:
            return jsonify({"success": False, "message": "Could not generate embedding"}), 500

        # Check if face is already registered
        is_registered, existing_name = recognize_face(emb, threshold=0.8) # Using slightly stricter threshold for registration
        if is_registered:
            print(f"❌ Registration failed: Face already registered as '{existing_name}'")
            return jsonify({"success": False, "message": f"Face already registered as {existing_name}"}), 400
            
        # Create directories in static folder
        os.makedirs("static/authorized_faces", exist_ok=True)
        
        # Save Embedding
        emb_path = f"static/authorized_faces/{name}.npy"
        np.save(emb_path, emb)
        
        # Save Face Image (for UI display)
        img_path = f"static/authorized_faces/{name}.jpg"
        cv2.imwrite(img_path, face)
        
        # Paths for DB (relative to static)
        db_emb_path = f"authorized_faces/{name}.npy"
        db_img_path = f"authorized_faces/{name}.jpg"
        
        # Register in DB
        try:
            insert_authorized_user(name, db_emb_path, db_img_path)
            print(f"✅ User {name} registered in DB")
        except Exception as e:
            print(f"⚠️ Database error (likely duplicate or missing column): {e}") 
            # Proceeding since file is saved
            
        return jsonify({"success": True, "message": f"Successfully registered {name}"})
        
    except Exception as e:
        print(f"Error in registration: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/recognize", methods=["POST"])
def recognize():
    try:
        data = request.json
        image_data = data.get("image")
        
        if not image_data:
            return jsonify({"success": False, "results": [], "message": "No image data"}), 400
            
        frame = base64_to_image(image_data)
        faces = detect_faces(frame)
        
        if not faces:
            # Even if no faces, we might want to check for objects, but the current UI logic
            # relies heavily on faces. We will let it proceed to check objects anyway if we want.
            pass
        
        response_results: list = []
        object_results: list = []
        intruder_detected = False
        threat_detected = False
        
        # --- FACE DETECTION PROCESSING ---
        for face, abs_box, relative_box in faces:
            face_result = {
                "box": {
                    "x": relative_box[0], 
                    "y": relative_box[1], 
                    "w": relative_box[2], 
                    "h": relative_box[3]
                }
            }
            
            try:
                emb = get_embedding(face)
                if emb is None:
                    face_result.update({"authorized": False, "name": "Unknown"})
                else:
                    authorized, name = recognize_face(emb)
                    
                    # --- LIVENESS CHECK ---
                    global last_live_time
                    is_blinking, ear = liveness_detector.check_liveness(frame)
                    
                    if is_blinking:
                        last_live_time = time.time()
                    
                    if authorized:
                         time_diff = time.time() - last_live_time
                         if time_diff > LIVENESS_TIMEOUT:
                             print(f"DEBUG: Liveness - Timeout ({time_diff:.2f}s > {LIVENESS_TIMEOUT}s). Asking to Blink.")
                             authorized = False
                             name = "Blink to Verify"
                         else:
                             # print(f"DEBUG: Liveness - Verified (Last blink {time_diff:.2f}s ago)")
                             pass
                    
                    face_result.update({"authorized": authorized, "name": name})
                    
                    if not authorized and name != "Blink to Verify":
                        intruder_detected = True
                        
            except Exception as e:
                print(f"Error processing face: {e}")
                face_result.update({"authorized": False, "name": "Error"})
                
            response_results.append(face_result)

        # --- Intruder Handling (Per Frame) ---
        if intruder_detected:
             try:
                 os.makedirs("static/intruders", exist_ok=True)
                 now = datetime.now()
                 date_str = now.strftime("%Y-%m-%d")
                 time_str = now.strftime("%H:%M:%S")
                 
                 filename_base = f"intruder_{now.strftime('%Y%m%d_%H%M%S_%f')}.jpg"
                 save_path = f"static/intruders/{filename_base}"
                 db_path = f"intruders/{filename_base}"
                 
                 cv2.imwrite(save_path, frame)
                 insert_intruder(date_str, time_str, db_path)
                 print(f"📸 Intruder detected! Saved to {save_path}")
                 
                 # 📧 TRIGGER EMAIL ALERT
                 try:
                     from alert_service import trigger_alert
                     trigger_alert(save_path)
                 except Exception as e:
                     print(f"Alert Error: {e}")
                     
             except Exception as e:
                 print(f"Error saving intruder: {e}")

        return jsonify({
            "success": True, 
            "results": response_results
        })
        
    except Exception as e:
        print(f"Error in recognition endpoint: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

def start_udp_discovery_server():
    import socket
    import threading
    
    def run_server():
        try:
            udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # Use SO_REUSEADDR to avoid address already in use errors on reload
            udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            udp_socket.bind(('', 5555))
            print("🌟 UDP Discovery Server listening on port 5555...")
            while True:
                try:
                    message, address = udp_socket.recvfrom(1024)
                    if message.decode('utf-8') == 'DISCOVER_FACE_SERVER':
                        # print(f"Received discovery request from {address}")
                        udp_socket.sendto(b'FACE_SERVER_ACK:5000', address)
                except Exception as e:
                    pass
        except Exception as e:
            print(f"Could not start UDP discovery server: {e}")
            
    threading.Thread(target=run_server, daemon=True).start()

if __name__ == "__main__":
    start_udp_discovery_server()
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
