import cv2
import mediapipe as mp
import numpy as np
from scipy.spatial import distance as dist

class LivenessDetector:
    def __init__(self):
        # Eye landmarks (Left and Right)

        self.LEFT_EYE = [362, 385, 387, 263, 373, 380]
        self.RIGHT_EYE = [33, 160, 158, 133, 153, 144]
        
        # Blink threshold
        self.EAR_THRESHOLD = 0.25
        # Consecutive frames for a blink
        self.CONSEC_FRAMES = 1
        
        self.blink_count = 0
        self.frame_counter = 0
        self.is_blinking = False

    def calculate_ear(self, landmarks, eye_indices):
        # Retrieve the landmarks for the eye
        # Landmarks are normalized (x, y, z), we need to maintain that or denormalize if using pixels
        # Distance calculation works on ratios, so normalized logic works if aspect ratio is preserved?
        # Actually EAR is a ratio of distances, so unit doesn't matter as long as consistent.
        # But Mediapipe gives normalized 0-1. 
        # Let's convert to pixel coordinates for safety or just use relative.
        # It's better to use pixels if we want real Euclidean distance.
        # But we don't have image shape here readily unless passed.
        # Let's assume passed landmarks are in pixels or use relative dist.
        # Relative dist is fine.
        
        # Vertical landmarks
        A = dist.euclidean(landmarks[eye_indices[1]], landmarks[eye_indices[5]])
        B = dist.euclidean(landmarks[eye_indices[2]], landmarks[eye_indices[4]])
        # Horizontal
        C = dist.euclidean(landmarks[eye_indices[0]], landmarks[eye_indices[3]])

        if C == 0: return 0
        ear = (A + B) / (2.0 * C)
        return ear

    def check_liveness(self, image):
        """
        Returns (is_live, ratio)
        is_live: True if a blink occurred recently
        """
        img_h, img_w, _ = image.shape
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Initialize FaceMesh per frame to avoid timestamp issues in API
        with mp.solutions.face_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        ) as face_mesh:
            results = face_mesh.process(rgb_image)

        
        if not results.multi_face_landmarks:
            print(f"DEBUG: Liveness - No face landmarks detected. Image shape: {img_w}x{img_h}")
            return False, 0.0

        for face_landmarks in results.multi_face_landmarks:
            # Convert landmarks to numpy array (x, y)
            landmarks = []
            for lm in face_landmarks.landmark:
                landmarks.append((int(lm.x * img_w), int(lm.y * img_h)))
            
            left_ear = self.calculate_ear(landmarks, self.LEFT_EYE)
            right_ear = self.calculate_ear(landmarks, self.RIGHT_EYE)
            
            avg_ear = (left_ear + right_ear) / 2.0
            
            # Check for blink
            if avg_ear < self.EAR_THRESHOLD:
                self.frame_counter += 1
                self.is_blinking = True
            else:
                if self.frame_counter >= self.CONSEC_FRAMES:
                    self.blink_count += 1
                    # Blink completed
                    return True, avg_ear
                
                self.frame_counter = 0
                self.is_blinking = False
        
        # Log EAR for debugging (all values)
        # if avg_ear < 0.35: # Only log when blink is likely
        print(f"DEBUG: EAR: {avg_ear:.4f} Threshold: {self.EAR_THRESHOLD} Blinking: {self.is_blinking} Count: {self.blink_count}")
            
        return False, avg_ear
