"""All settings in one place."""
import os

# ───────────────────────── CAMERA ─────────────────────────
CAMERA_IP = os.environ.get("UR5E_CAMERA_IP", "")
CAMERA_RTSP_PORT = 554
CAMERA_USER = os.environ.get("UR5E_CAMERA_USER", "")
CAMERA_PASSWORD = ""              # keep empty: ask at startup (hidden input)
FFMPEG_PATH = ""                  # full path to ffmpeg.exe, only if it is not found automatically
FFPROBE_PATH = ""                 # full path to ffprobe.exe (optional)
CAMERA_STREAM = "101"             # "101" = main stream, "102" = sub stream
RTSP_TRANSPORT = "tcp"            # "tcp" = stable, "udp" = slightly lower latency
USE_FFMPEG_PIPE = True            # lowest latency, needs ffmpeg (otherwise OpenCV is used)
USE_NVDEC = True                  # NVIDIA hardware decoding (RTX)

# ───────────────────────── ROBOT ─────────────────────────
ROBOT_IP = os.environ.get("UR5E_ROBOT_IP", "")
URSCRIPT_PORT = 30002             # URScript is sent here (plain socket)
RTDE_PORT = 30004                 # live state, READ ONLY (pose, joints, telemetry)

# SINGLE SOURCE OF TRUTH for requested Cartesian motion parameters.
# Never inferred from the observed RTDE actual_TCP_speed.
MOVE_SPEED_M_S = 0.05
MOVE_ACCEL_M_S2 = 0.1
# Joint-space motion parameters. Distinct units from the Cartesian settings.
JOINT_SPEED_RAD_S = 0.25
JOINT_ACCEL_RAD_S2 = 0.5

# ───────────────────────── TUNING ─────────────────────────
GESTURE_HOLD_S = 3.0       # same gesture must be held this long (debounce)
COOLDOWN_S = 1.0           # pause after a move finished
POS_TOL_M = 0.0005
ROT_TOL_RAD = 0.004
STOP_SPEED_M_S = 0.001
MOVE_TIMEOUT_S = 180.0
DETECT_WIDTH = 640         # frame width fed to MediaPipe (speed)
DISPLAY_WIDTH = 1600
START_WAIT_FOR_CONFIRM = True
# Working zone on the preview image (mirrored), normalized x1,y1,x2,y2. Palm centre must be inside.
ZONE = (0.05, 0.05, 0.95, 0.95)
MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
             "hand_landmarker/float16/1/hand_landmarker.task")
MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hand_landmarker.task")



# ───────────────────────── MODELS ─────────────────────────
MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
HAND_MODEL_URL = MODEL_URL
YUNET_URL = ("https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/"
             "face_detection_yunet_2023mar.onnx")

# ───────────────────────── PERSON / FACE ─────────────────────────
FACE_DET_WIDTH = 1280      # full frame is downscaled to this width for face search (small faces ok)
FACE_SCORE = 0.5           # YuNet confidence (lower = finds more, more false positives)
FACE_REAL_CM = 16.0        # real size of the face square = ruler for the centimetre offsets
ZONE_GAP_X_CM = 20.0       # zone starts 20 cm to the person's RIGHT of the face square
ZONE_DROP_Y_CM = 5.0      # ...and 5 cm LOWER than the top of the face square
ZONE_SIZE_CM = 30.0        # zone side
FACE_TARGET_FRAC = 0.22    # auto-zoom keeps the face square at this fraction of the view height
MIN_TRACK_ZOOM = 1.6       # as soon as a person is found, zoom in at least this much
MAX_ZOOM = 3.0
VIEW_TAU_S = 0.35          # camera pan/zoom smoothness (lower = snappier)
FACE_TAU_S = 0.12          # face box smoothness
FACE_HOLD_S = 1.2          # keep the box this long if the detector blinks
PERSON_CONFIRM_S = 0.4     # person must be tracked this long before gestures count
PERSON_RELEASE_S = 3.0     # no face for this long -> zoom out, forget the person
REQUIRE_RIGHT_HAND = True  # only HIS right hand in the zone (display is mirrored)
