"""Face detection (YuNet, background thread), sticky one-person tracker, smooth zoom/pan view."""
import math, os, threading, time
import cv2
import numpy as np
from config import *
from models import ensure


class FaceDetector:
    """Runs on the FULL frame (downscaled to FACE_DET_WIDTH) in its own thread, never blocks the UI.
    Output: boxes (cx, cy, side) in ORIGINAL (un-mirrored) source pixels + frame timestamp."""
    def __init__(self):
        self.lock = threading.Lock()
        self.frame, self.in_ts = None, 0.0
        self.out, self.out_ts = [], 0.0
        self.yn = None
        try:
            path = ensure("face_detection_yunet_2023mar.onnx", YUNET_URL)
            self.yn = cv2.FaceDetectorYN.create(path, "", (320, 320), FACE_SCORE, 0.3, 5000)
            print("[face] YuNet")
        except Exception as e:
            print(f"[face] YuNet unavailable ({e}) -> Haar fallback")
            self.haar = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        self.stop_flag = False
        threading.Thread(target=self._run, daemon=True).start()

    def submit(self, frame, ts):
        with self.lock:
            self.frame, self.in_ts = frame, ts

    def result(self):
        with self.lock:
            return list(self.out), self.out_ts

    def _detect(self, frame):
        fh, fw = frame.shape[:2]
        sc = min(1.0, FACE_DET_WIDTH / fw)
        small = cv2.resize(frame, (int(fw * sc), int(fh * sc)), interpolation=cv2.INTER_AREA) if sc < 1 else frame
        boxes = []
        if self.yn is not None:
            self.yn.setInputSize((small.shape[1], small.shape[0]))
            _, f = self.yn.detect(small)
            for r in (f if f is not None else []):
                x, y, w, h = r[:4]
                boxes.append((x + w / 2, y + h / 2, max(w, h) * 1.1, float(r[14])))
        else:
            g = cv2.equalizeHist(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY))
            for (x, y, w, h) in self.haar.detectMultiScale(g, 1.1, 5, minSize=(24, 24)):
                boxes.append((x + w / 2, y + h / 2, max(w, h) * 1.1, 1.0))
        return [(cx / sc, cy / sc, side / sc) for cx, cy, side, _ in boxes]

    def _run(self):
        last = 0.0
        while not self.stop_flag:
            with self.lock:
                fr, ts = self.frame, self.in_ts
            if fr is None or ts == last:
                time.sleep(0.005)
                continue
            last = ts
            try:
                res = self._detect(fr)
            except Exception as e:
                print(f"[face] {e}")
                res = []
            with self.lock:
                self.out, self.out_ts = res, ts

    def stop(self):
        self.stop_flag = True


def ema(old, new, dt, tau):
    return old + (new - old) * (1 - math.exp(-dt / tau))


class Person:
    """Sticky tracker of ONE person's face, in mirrored-source pixel coords (stable under zoom)."""
    def __init__(self):
        self.reset()

    def reset(self):
        self.cx = self.cy = self.side = self.first_seen = None
        self.last_seen = 0.0

    def update(self, faces, now, dt):
        if self.cx is not None and now - self.last_seen > PERSON_RELEASE_S:
            self.reset()
        pick = None
        if faces and self.cx is not None:
            near = min(faces, key=lambda f: math.hypot(f[0] - self.cx, f[1] - self.cy))
            if math.hypot(near[0] - self.cx, near[1] - self.cy) < 1.5 * self.side:
                pick = near                                   # same person
        if faces and pick is None and (self.cx is None or now - self.last_seen > FACE_HOLD_S):
            pick = max(faces, key=lambda f: f[2])             # new person: the closest (largest) face
            self.reset()
        if pick:
            if self.cx is None:
                self.cx, self.cy, self.side = pick
                self.first_seen = now
            else:
                self.cx = ema(self.cx, pick[0], dt, FACE_TAU_S)
                self.cy = ema(self.cy, pick[1], dt, FACE_TAU_S)
                self.side = ema(self.side, pick[2], dt, FACE_TAU_S)
            self.last_seen = now

    def present(self, now):
        return self.cx is not None and now - self.last_seen <= FACE_HOLD_S

    def confirmed(self, now):
        return self.present(now) and now - self.first_seen >= PERSON_CONFIRM_S

    def tracking(self, now):
        return self.cx is not None and now - self.last_seen <= PERSON_RELEASE_S

    def geometry(self):
        k = self.side / FACE_REAL_CM                         # px per cm
        face = (self.cx - self.side / 2, self.cy - self.side / 2,
                self.cx + self.side / 2, self.cy + self.side / 2)
        zx, zy = face[2] + ZONE_GAP_X_CM * k, face[1] + ZONE_DROP_Y_CM * k
        return face, (zx, zy, zx + ZONE_SIZE_CM * k, zy + ZONE_SIZE_CM * k)


class View:
    """Smooth digital pan/zoom window over the (mirrored) full frame."""
    def __init__(self, fw, fh):
        self.fw, self.fh = fw, fh
        self.cx, self.cy, self.zoom = fw / 2, fh / 2, 1.0

    def update(self, person, now, dt):
        tx, ty, tz = self.fw / 2, self.fh / 2, 1.0
        if person.tracking(now):
            face, zone = person.geometry()
            ux1, uy1 = min(face[0], zone[0]), min(face[1], zone[1])
            ux2, uy2 = max(face[2], zone[2]), max(face[3], zone[3])
            tz = min(max(FACE_TARGET_FRAC * self.fh / person.side, MIN_TRACK_ZOOM), MAX_ZOOM)
            tz = min(tz, self.fw / ((ux2 - ux1) * 1.25), self.fh / ((uy2 - uy1) * 1.25), MAX_ZOOM)
            tz = max(tz, 1.0)
            tx, ty = (ux1 + ux2) / 2, (uy1 + uy2) / 2        # frame face AND zone together
        self.zoom = ema(self.zoom, tz, dt, VIEW_TAU_S)
        self.cx = ema(self.cx, tx, dt, VIEW_TAU_S)
        self.cy = ema(self.cy, ty, dt, VIEW_TAU_S)

    def rect(self):
        cw, ch = max(2, int(self.fw / self.zoom)), max(2, int(self.fh / self.zoom))
        x0 = int(min(max(self.cx - cw / 2, 0), self.fw - cw))
        y0 = int(min(max(self.cy - ch / 2, 0), self.fh - ch))
        return x0, y0, cw, ch
