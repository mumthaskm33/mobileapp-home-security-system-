import cv2
import mediapipe as mp
from face_model import get_embedding
from utils import recognize_face
from database import insert_intruder
import time
import os
from datetime import datetime

last_intruder_save_time = 0
INTRUDER_COOLDOWN = 5  # seconds

def recognize_face_from_frame(face):
    emb = get_embedding(face)
    if emb is None:
        return False, "Unknown"
    return recognize_face(emb)


# ---------------- SCRIPT MODE ----------------
def main():
    print("Starting live recognition...")
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

    if not cap.isOpened():
        print("❌ Camera not opened")
        return

    mp_face = mp.solutions.face_detection.FaceDetection(
        model_selection=0,
        min_detection_confidence=0.6
    )

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = mp_face.process(rgb)

        if results.detections:
            for det in results.detections:
                box = det.location_data.relative_bounding_box
                h, w, _ = frame.shape

                x = int(box.xmin * w)
                y = int(box.ymin * h)
                ww = int(box.width * w)
                hh = int(box.height * h)

                face = frame[y:y+hh, x:x+ww]
                if face.size == 0:
                    continue

                authorized, name = recognize_face_from_frame(face)
                if authorized:
                    color = (0, 255, 0)
                    label = f"Authorized: {name}"
                else:
                    color = (0, 0, 255)
                    label = "Unauthorized"
                    
                    with open("debug_log.txt", "a") as f:
                        f.write(f"Unauthorized detected: {name}, Auth: {authorized}\n")

                    global last_intruder_save_time
                    if time.time() - last_intruder_save_time > INTRUDER_COOLDOWN:
                        os.makedirs("intruders", exist_ok=True)
                        now = datetime.now()
                        date_str = now.strftime("%Y-%m-%d")
                        time_str = now.strftime("%H:%M:%S")
                        filename = f"intruders/intruder_{now.strftime('%Y%m%d_%H%M%S')}.jpg"
                        
                        cv2.imwrite(filename, frame)
                        print(f"📸 Intruder detected! Saved to {filename}")
                        
                        try:
                            insert_intruder(date_str, time_str, filename)
                            with open("debug_log.txt", "a") as f:
                                f.write("INTRUDER SAVED TO DB SUCCESS\n")
                        except Exception as e:
                            with open("debug_log.txt", "a") as f:
                                f.write(f"DB ERROR: {str(e)}\n")
                        
                        last_intruder_save_time = time.time()

                cv2.rectangle(frame, (x, y), (x + ww, y + hh), color, 2)
                cv2.putText(frame, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)

                print(authorized, name)

        cv2.imshow("Live", frame)
        if cv2.waitKey(1) & 0xFF == 27:
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
