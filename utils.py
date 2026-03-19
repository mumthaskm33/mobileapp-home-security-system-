import numpy as np
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
AUTH_DIR = BASE_DIR / "static" / "authorized_faces"

def recognize_face(embedding, threshold=0.85):
    files = list(AUTH_DIR.glob("*.npy"))

    if not files:
        return False, "Unknown"

    best_dist = float("inf")
    best_name = "Unknown"

    for file in files:
        ref_emb = np.load(file)
        dist = np.linalg.norm(ref_emb - embedding)

        if dist < best_dist:
            best_dist = dist
            best_name = file.stem.split("_")[0]

    print("BEST DIST:", best_dist, "BEST NAME:", best_name)

    if best_dist < threshold:
        return True, best_name
    else:
        return False, "Unauthorized"
