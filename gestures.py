"""Gesture must be held GESTURE_HOLD_S (tolerant to short flicker)."""
from config import GESTURE_HOLD_S


class GestureHold:
    def __init__(self):
        self.samples = []

    def clear(self):
        self.samples.clear()

    def push(self, now, target):
        """-> (leader, ratio, progress 0..1, ready)"""
        self.samples.append((now, target))
        self.samples = [x for x in self.samples if x[0] >= now - GESTURE_HOLD_S - 0.3]
        vals = [t for _, t in self.samples if t]
        if not vals:
            return None, 0.0, 0.0, False
        leader = max(set(vals), key=vals.count)
        ratio = vals.count(leader) / len(self.samples)
        span = now - self.samples[0][0]
        ok = ratio >= 0.85
        return leader, ratio, (min(span / GESTURE_HOLD_S, 1.0) if ok else 0.0), ok and span >= GESTURE_HOLD_S
