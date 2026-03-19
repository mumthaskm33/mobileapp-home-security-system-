import ssl
import os

# Fix SSL certificate verification issues
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

from keras_facenet import FaceNet
import cv2
import numpy as np

embedder = FaceNet()

def get_embedding(face_img):
    face_img = cv2.resize(face_img, (160, 160))
    face_img = face_img.astype("float32")
    face_img = np.expand_dims(face_img, axis=0)
    embeddings = embedder.embeddings(face_img)
    return embeddings[0]
