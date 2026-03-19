import json
import base64
import cv2
import numpy as np
from datetime import datetime
from collections import deque, Counter
from pathlib import Path
import uuid
import time

LAST_INTRUDER_SAVE = 0

from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render

import mediapipe as mp

from face_model import get_embedding
from utils import recognize_face
from database import (
    insert_intruder, 
    insert_authorized_user, 
    get_intruders, 
    get_authorized_users,
    clear_intruders
)


# ===============================
# BASE PROJECT DIRECTORY
# ===============================
BASE_DIR = Path(__file__).resolve().parent.parent.parent

AUTHORIZED_DIR = BASE_DIR / "static" / "authorized_faces"
INTRUDER_DIR = BASE_DIR / "static" / "intruders"

AUTHORIZED_DIR.mkdir(exist_ok=True)
INTRUDER_DIR.mkdir(exist_ok=True)


# ===============================
# MediaPipe Face Detector
# ===============================
mp_face = mp.solutions.face_detection.FaceDetection(
    model_selection=0,
    min_detection_confidence=0.6
)


# ===============================
# Decision smoothing buffers
# ===============================
decision_buffer = deque(maxlen=10)
name_buffer = deque(maxlen=10)


# ===============================
# Frontend page
# ===============================
def camera_page(request):
    return render(request, "camera.html")

def register_page(request):
    return render(request, "register.html")

def logs_page(request):
    logs = get_intruders()
    return render(request, "logs.html", {"logs": logs})

def authorized_page(request):
    users = get_authorized_users()
    return render(request, "authorized.html", {"users": users})


def home(request):
    return HttpResponse("Backend is running")


# ===============================
# Helper: Decode image
# ===============================
def decode_image(data):
    try:
        img_bytes = base64.b64decode(data.split(",")[1])
        np_img = np.frombuffer(img_bytes, np.uint8)
        return cv2.imdecode(np_img, cv2.IMREAD_COLOR)
    except Exception:
        return None


# ===============================
# Helper: Extract face
# ===============================
# ===============================
# Helper: Extract all faces
# ===============================
def extract_faces(frame):
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = mp_face.process(rgb)

    if not results.detections:
        return []

    faces = []
    h, w, _ = frame.shape
    
    pad = 20

    for det in results.detections:
        box = det.location_data.relative_bounding_box
        x = int(box.xmin * w)
        y = int(box.ymin * h)
        ww = int(box.width * w)
        hh = int(box.height * h)

        face_img = frame[
            max(0, y - pad):min(h, y + hh + pad),
            max(0, x - pad):min(w, x + ww + pad)
        ]
        
        if face_img.size == 0:
            continue
            
        faces.append({
            "image": face_img,
            "box": [box.xmin, box.ymin, box.width, box.height], # Relative coords
            "pixel_box": [x, y, ww, hh]
        })

    return faces


# ===============================
# REGISTER FACE API (Legacy support for single face)
# ===============================
@csrf_exempt
def register_face_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    body = json.loads(request.body)
    name = body.get("name")
    image = body.get("image")

    if not name or not image:
        return JsonResponse({"error": "Missing name or image"}, status=400)

    frame = decode_image(image)
    if frame is None:
        return JsonResponse({"error": "Invalid image"})

    faces = extract_faces(frame)
    if not faces:
        return JsonResponse({"error": "No face detected"})
    
    # Use the first/largest face for registration
    face = faces[0]["image"]

    emb = get_embedding(face)
    if emb is None:
        return JsonResponse({"error": "Embedding failed"})
    
    # Check for duplicate face
    authorized, existing_name = recognize_face(emb)
    if authorized:
        return JsonResponse({"error": f"Person already registered as {existing_name}"}, status=400)
    
    for i in range(5):
      file_path = AUTHORIZED_DIR / f"{name}_{uuid.uuid4().hex}.npy"
      np.save(file_path, emb)

    # Save Face Image for UI
    img_filename = f"{name}_{uuid.uuid4().hex}.jpg"
    img_path = AUTHORIZED_DIR / img_filename
    cv2.imwrite(str(img_path), frame)

    try:
        db_img_path = f"authorized_faces/{img_filename}"
        insert_authorized_user(name, str(file_path), db_img_path)
    except Exception as e:
        print("DB Error:", e)

    return JsonResponse({
        "status": "success",
        "message": f"{name} registered"
    })


# ===============================
# RECOGNIZE FACE API (Multi-face)
# ===============================
@csrf_exempt
def recognize_face_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    body = json.loads(request.body)
    image = body.get("image")

    frame = decode_image(image)
    if frame is None:
        return JsonResponse({"results": []})

    faces = extract_faces(frame)
    if not faces:
        return JsonResponse({"results": []})

    results = []
    
    for item in faces:
        face_img = item["image"]
        emb = get_embedding(face_img)
        
        if emb is None:
            results.append({
                "authorized": False,
                "name": "Unknown",
                "box": item["box"]
            })
            continue

        authorized, name = recognize_face(emb)
        
        # Simple logging for now
        if not authorized:
             # Save Intruder (Throttled)
             global LAST_INTRUDER_SAVE
             try:
                 now = time.time()
                 if now - LAST_INTRUDER_SAVE > 5:  # 5 seconds cooldown
                     LAST_INTRUDER_SAVE = now
                     
                     # Generate filename
                     timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                     filename = f"intruder_{timestamp}_{uuid.uuid4().hex[:6]}.jpg"
                     file_path = INTRUDER_DIR / filename
                     
                     # Save image
                     cv2.imwrite(str(file_path), frame)
                     
                     # Save to DB
                     db_path = f"intruders/{filename}"
                     current_date = datetime.now().strftime("%Y-%m-%d")
                     current_time = datetime.now().strftime("%H:%M:%S")
                     
                     try:
                        insert_intruder(current_date, current_time, db_path)
                        print(f"Intruder saved: {filename}")
                     except Exception as db_err:
                        print(f"DB Error saving intruder: {db_err}")
                        
             except Exception as e:
                 print(f"Error processing intruder: {e}")

        results.append({
            "authorized": authorized,
            "name": name if authorized else "Unauthorized",
            "box": item["box"]
        })

    return JsonResponse({"results": results})

@csrf_exempt
def clear_logs_api(request):
    if request.method == "POST":
        clear_intruders()
        # Also clean up files? Optional but good practice.
        # For now, we only clear DB to fix the mismatch.
        return JsonResponse({"status": "success"})
    return JsonResponse({"error": "POST only"}, status=405)

@csrf_exempt
def delete_user_api(request, user_id):
    if request.method == "POST":
        from database import get_authorized_user_by_id, delete_authorized_user
        
        user = get_authorized_user_by_id(user_id)
        if not user:
            return JsonResponse({"error": "User not found"}, status=404)
            
        # Delete files
        try:
             # embedding_path and face_image_path are stored in DB
             # Need to handle potential full paths vs relative paths messiness
             # Based on insert, they might be absolute or relative.
             # Ideally use pathlib
             
             # FIX: Registration creates 5 embedding files but DB only stores the last one.
             # We must delete ALL files associated with this user's name.
             name = user.get("name")
             if name:
                 # Delete all associated embeddings
                 for embed_file in AUTHORIZED_DIR.glob(f"{name}_*.npy"):
                     try:
                         embed_file.unlink()
                     except Exception as e:
                         print(f"Failed to delete {embed_file}: {e}")

                 # Delete all associated images (if any others exist, though likely just one)
                 # But sticking to the specific one in DB is safer for images unless we use strict naming there too.
                 # The DB has the specific face image path.
            
             if user.get("face_image_path"):
                 p_img = BASE_DIR.parent / "static" / user["face_image_path"]
                 if p_img.exists():
                     p_img.unlink()
                     
        except Exception as e:
            print(f"Error deleting files: {e}")

        delete_authorized_user(user_id)
        return JsonResponse({"status": "success"})

    return JsonResponse({"error": "POST only"}, status=405)
