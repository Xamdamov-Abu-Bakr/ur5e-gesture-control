"""Drawing helpers."""
import cv2
import numpy as np


def corner_rect(img, p1, p2, color, t=3, l=None):
    (x1, y1), (x2, y2) = p1, p2
    l = l or max(10, (x2 - x1) // 5)
    cv2.rectangle(img, p1, p2, color, 1)
    for (x, y, dx, dy) in ((x1, y1, 1, 1), (x2, y1, -1, 1), (x1, y2, 1, -1), (x2, y2, -1, -1)):
        cv2.line(img, (x, y), (x + dx * l, y), color, t)
        cv2.line(img, (x, y), (x, y + dy * l), color, t)


def shade(img, p1, p2, color, alpha=0.12):
    x1, y1, x2, y2 = max(p1[0], 0), max(p1[1], 0), min(p2[0], img.shape[1]), min(p2[1], img.shape[0])
    if x2 > x1 and y2 > y1:
        roi = img[y1:y2, x1:x2]
        img[y1:y2, x1:x2] = cv2.addWeighted(roi, 1 - alpha, np.full_like(roi, color), alpha, 0)
