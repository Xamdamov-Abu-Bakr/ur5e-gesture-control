"""Example pose configuration. Copy to poses.py and teach your OWN poses.

All target coordinates intentionally omitted. Do not operate a robot before
commissioning its safety setup, TCP, payload and every motion path.
"""
# ───────────────────────── POSES ─────────────────────────
# name -> (tcp [x,y,z,rx,ry,rz] base frame m/rad,  joints [q1..q6] rad or None)
POSES = {
    "FIST": (None, None),
    "1 finger": (None, None),
    "2 fingers": (None, None),
    "3 fingers": (None, None),
    "4 fingers": (None, None),
    "5 fingers": (None, None),
}

# "movej": taught poses go by their joint values (safest: no IK flips, no straight-line surprises).
# "movel": always Cartesian with MOVE_SPEED_M_S / MOVE_ACCEL_M_S2. FIST has no joints -> always movel.
MOVE_MODE = "movej"


def classify(state):
    """state = (thumb, index, middle, ring, pinky) -> pose name or None."""
    th, f = state[0], tuple(state[1:])
    if f == (0, 0, 0, 0):
        return "FIST"            # thumb ignored
    if f == (1, 0, 0, 0):
        return "1 finger"
    if f == (1, 1, 0, 0):
        return "2 fingers"
    if f == (1, 1, 1, 0):
        return "3 fingers"
    if f == (1, 1, 1, 1):
        return "5 fingers" if th else "4 fingers"
    return None
