"""Hand landmarks (MediaPipe Tasks) + finger-state rule from the original robodk_vision script."""
import numpy as np
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python import vision as mpv
from config import HAND_MODEL_URL
from models import ensure

CONN = [(0,1),(1,2),(2,3),(3,4),(0,5),(5,6),(6,7),(7,8),(5,9),(9,10),(10,11),(11,12),
        (9,13),(13,14),(14,15),(15,16),(13,17),(17,18),(18,19),(19,20),(0,17)]


def create_hand_landmarker(num_hands=2):
    path = ensure("hand_landmarker.task", HAND_MODEL_URL)
    return mpv.HandLandmarker.create_from_options(mpv.HandLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=path), running_mode=mpv.RunningMode.VIDEO,
        num_hands=num_hands, min_hand_detection_confidence=0.6,
        min_hand_presence_confidence=0.5, min_tracking_confidence=0.5))


def mp_image(rgb):
    return mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))


def to_px(hand, w, h):
    return [(i, int(l.x * w), int(l.y * h), l.z) for i, l in enumerate(hand)]


def lm_dist(a, b):
    return int(np.hypot(b[1] - a[1], b[2] - a[2]))


def fingers_state(lm):
    """(thumb, index, middle, ring, pinky), 1 = up."""
    up = []
    for tip in (4, 8, 12, 16, 20):
        ref = 17 if tip == 4 else 0
        up.append(1 if lm_dist(lm[tip], lm[ref]) > lm_dist(lm[tip - 2], lm[ref]) else 0)
    return tuple(up)


def palm_center(lm):
    ids = (0, 1, 5, 9, 13, 17)
    return (sum(lm[i][1] for i in ids) // 6, sum(lm[i][2] for i in ids) // 6)
