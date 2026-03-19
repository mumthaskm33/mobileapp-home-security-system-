import urllib.request
import json
import base64
import numpy as np
import cv2
import time

def create_dummy_image():
    # Create a black image with a drawn rectangle (simulating a face maybe? No, face detection needs a face)
    # MediaPipe might not detect a face in a black square.
    # We might fail the "face detected" check, but we can verify the API responds.
    # Or we can try to use an existing image if available.
    # Let's try to generate a simple image, but face detection will likely fail.
    # However, we can check if the server returns "No face detected" which is a valid API response.
    img = np.zeros((300, 300, 3), dtype=np.uint8)
    cv2.circle(img, (150, 150), 50, (255, 255, 255), -1)
    _, buffer = cv2.imencode('.jpg', img)
    return base64.b64encode(buffer).decode('utf-8')

def test_api():
    base_url = "http://127.0.0.1:5000"
    image_data = create_dummy_image()
    
    # Test Register
    reg_data = json.dumps({
        "name": "TestAI",
        "image": image_data
    }).encode('utf-8')
    
    req = urllib.request.Request(f"{base_url}/register", data=reg_data, headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(req) as f:
            print("Register Response:", f.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        print("Register Error:", e.code, e.read().decode('utf-8'))
        
    # Test Recognize
    rec_data = json.dumps({
        "image": image_data
    }).encode('utf-8')
    
    req = urllib.request.Request(f"{base_url}/recognize", data=rec_data, headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(req) as f:
            print("Recognize Response:", f.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        print("Recognize Error:", e.code, e.read().decode('utf-8'))

if __name__ == "__main__":
    time.sleep(2) # Wait for server
    try:
        test_api()
    except Exception as e:
        print("Test failed:", e)
