import cv2
import mediapipe as mp
import numpy as np
import os

from face_model import get_embedding
from database import insert_authorized_user


# ✅ FUNCTION USED BY DJANGO
def register_face_from_frame(frame, name):
    emb = get_embedding(frame)
    if emb is None:
        return False

    os.makedirs("authorized_faces", exist_ok=True)
    path = f"authorized_faces/{name}.npy"
    np.save(path, emb)

    np.save(path, emb)

    try:
        insert_authorized_user(name, path)
        print("✅ Saved to database")
    except Exception as e:
        print(f"⚠️ Database error: {e}")
        print("✅ Saved to file only")
    
    return True


# ---------------- SCRIPT MODE (FOR TERMINAL TESTING ONLY) ----------------

def main():
    print("Starting camera...")
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

    if not cap.isOpened():
        print("❌ Camera not opened")
        return

    mp_face = mp.solutions.face_detection.FaceDetection(
        model_selection=0,
        min_detection_confidence=0.6
    )

    import sys
    if len(sys.argv) > 1:
        name = sys.argv[1]
        print(f"Using name: {name}")
    else:
        name = input("Enter person name: ")

    print("Press 's' to save face, ESC to exit")

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

                cv2.rectangle(frame, (x,y), (x+ww,y+hh), (0,255,0), 2)

                key = cv2.waitKey(1) & 0xFF
                if key == ord('s'):
                    register_face_from_frame(face, name)
                    print("✅ Face registered")
                    cap.release()
                    cv2.destroyAllWindows()
                    return

        cv2.imshow("Register Face", frame)
        if cv2.waitKey(1) & 0xFF == 27:
            break

    cap.release()
    cv2.destroyAllWindows()


# 🔒 THIS LINE IS NON-NEGOTIABLE
if __name__ == "__main__":
    main()
