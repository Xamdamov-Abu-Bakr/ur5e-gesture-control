#!/usr/bin/env python3
"""UR5e gesture control: find person -> zoom & follow -> his right-hand zone -> finger count held 3 s -> pose.
Run:  python main.py        Keys: 0-5 manual pose | x STOP | g gestures on/off | q quit
pip install numpy opencv-python mediapipe
"""
import getpass, math, time
from urllib.parse import quote

import cv2
import numpy as np

from config import *
from poses import POSES, MOVE_MODE, classify
from camera import Camera
from robot import Robot
from hand import create_hand_landmarker, mp_image, to_px, fingers_state, palm_center, CONN
from person import FaceDetector, Person, View
from gestures import GestureHold
from ui import corner_rect, shade


def build_url(pw):
    return (f"rtsp://{quote(CAMERA_USER, safe='')}:{quote(pw, safe='')}"
            f"@{CAMERA_IP}:{CAMERA_RTSP_PORT}/Streaming/Channels/{CAMERA_STREAM}")


def main():
    if not CAMERA_IP or not ROBOT_IP or not CAMERA_USER:
        raise RuntimeError("Set UR5E_CAMERA_IP, UR5E_ROBOT_IP and UR5E_CAMERA_USER before starting")
    required = ("FIST", "1 finger", "2 fingers", "3 fingers", "4 fingers", "5 fingers")
    if any(name not in POSES or POSES[name][0] is None or len(POSES[name][0]) != 6
           for name in required):
        raise RuntimeError("Copy poses.example.py to poses.py and teach/validate all six poses first")
    pw = CAMERA_PASSWORD or getpass.getpass(f"Camera password for {CAMERA_USER}@{CAMERA_IP}: ")
    cam = Camera(build_url(pw))
    print("[cam] connecting...")
    cam.wait_first()
    print("[cam] stream OK")
    faces = FaceDetector()
    hands = create_hand_landmarker(2)

    robot = Robot()
    print(f"[robot] RTDE ok, ready={robot.ready()}")
    for n, p in POSES.items():
        dp, da = robot.distance_to(p[0])
        print(f"  {n:10s}: {dp*1000:6.0f} mm / {np.degrees(da):5.1f} deg from current TCP")
    names = list(POSES.keys())
    print(f"\nMode {MOVE_MODE}. Gesture must be held {GESTURE_HOLD_S:.0f} s. E-stop in reach.")
    print("Keys: 0-5 = go to pose manually, x = STOP, g = gestures on/off, q = quit")
    if START_WAIT_FOR_CONFIRM and input("Type YES to enable: ").strip() != "YES":
        return

    person, view, hold = Person(), None, GestureHold()
    control = True
    last_ts, last_face_ts, last_ms = 0.0, 0.0, 0
    fps, tprev = 0.0, time.time()
    robot.last_done = 0.0

    try:
        while True:
            frame, ts = cam.latest()
            if frame is None or ts == last_ts:
                if cv2.waitKey(2) & 0xFF in (27, ord("q")):
                    break
                continue
            last_ts = ts
            now = time.time()
            dt = min(max(now - tprev, 0.001), 0.2)
            tprev = now
            fh, fw = frame.shape[:2]
            faces.submit(frame, ts)

            # ── person: new detections (converted to MIRRORED source coords) ──
            det, det_ts = faces.result()
            if det_ts != last_face_ts:
                last_face_ts = det_ts
                person.update([(fw - cx, cy, sd) for cx, cy, sd in det], now, dt)
            else:
                person.update([], now, dt)
            if view is None or (view.fw, view.fh) != (fw, fh):
                view = View(fw, fh)
            view.update(person, now, dt)

            # ── smooth zoom/pan crop (mirrored display) ──
            x0, y0, cw, ch = view.rect()
            crop = frame[y0:y0 + ch, fw - (x0 + cw):fw - x0]
            disp = cv2.flip(cv2.resize(crop, (DISPLAY_WIDTH, int(DISPLAY_WIDTH * ch / cw)),
                                       interpolation=cv2.INTER_AREA), 1)
            H, W = disp.shape[:2]
            small = cv2.resize(disp, (DETECT_WIDTH, int(H * DETECT_WIDTH / W)), interpolation=cv2.INTER_AREA)
            sx, sy = W / cw, H / ch
            to_d = lambda mx, my: (int((mx - x0) * sx), int((my - y0) * sy))

            # ── draw person + zone ──
            zone_d, zone_ok = None, False
            if person.tracking(now):
                face, zone = person.geometry()
                fp1, fp2 = to_d(face[0], face[1]), to_d(face[2], face[3])
                zone_d = (to_d(zone[0], zone[1]), to_d(zone[2], zone[3]))
                zone_ok = zone[0] >= 0 and zone[1] >= 0 and zone[2] <= fw and zone[3] <= fh
                live = person.present(now)
                for cx, cy, sd in det:                                  # other people: thin grey
                    mx = fw - cx
                    if abs(mx - person.cx) > person.side:
                        cv2.rectangle(disp, to_d(mx - sd / 2, cy - sd / 2), to_d(mx + sd / 2, cy + sd / 2),
                                      (110, 110, 110), 1)
                corner_rect(disp, fp1, fp2, (255, 200, 0) if live else (120, 120, 120), 3)
                cv2.putText(disp, "YOU" if live else "...", (fp1[0], fp1[1] - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 200, 0), 2)
                cv2.line(disp, ((fp1[0] + fp2[0]) // 2, fp2[1]), (zone_d[0][0] + 6, zone_d[0][1] + 6),
                         (90, 90, 90), 1)

            # ── hands: pick HIS right hand inside the zone ──
            ms = max(int(now * 1000), last_ms + 1)
            last_ms = ms
            res = hands.detect_for_video(mp_image(cv2.cvtColor(small, cv2.COLOR_BGR2RGB)), ms)
            chosen = None
            for i, hl in enumerate(res.hand_landmarks):
                lm = to_px(hl, W, H)
                label = res.handedness[i][0].category_name if res.handedness else "Right"
                is_right = label == "Left" or not REQUIRE_RIGHT_HAND
                cx, cy = palm_center(lm)
                inside = (zone_d is not None and zone_ok and person.confirmed(now) and is_right and
                          zone_d[0][0] < cx < zone_d[1][0] and zone_d[0][1] < cy < zone_d[1][1])
                col = (255, 255, 0) if inside else (100, 100, 100)
                for a, b in CONN:
                    cv2.line(disp, lm[a][1:3], lm[b][1:3], col, 3 if inside else 1)
                if inside and chosen is None:
                    chosen = lm
                    for p in lm:
                        cv2.circle(disp, p[1:3], 6, (0, 200, 255), cv2.FILLED)
                    cv2.circle(disp, (cx, cy), 10, (0, 255, 0), cv2.FILLED)

            if zone_d:
                zc = (0, 220, 0) if chosen else ((0, 140, 255) if not zone_ok else (230, 230, 230))
                if chosen:
                    shade(disp, zone_d[0], zone_d[1], zc)
                corner_rect(disp, zone_d[0], zone_d[1], zc, 3)
                cv2.putText(disp, "RIGHT HAND ZONE" if zone_ok else "ZONE OUT OF FRAME",
                            (zone_d[0][0] + 8, zone_d[0][1] + 26), cv2.FONT_HERSHEY_SIMPLEX, 0.7, zc, 2)

            # ── gesture (3 s hold) -> robot ──
            state = fingers_state(chosen) if chosen else None
            target = classify(state) if state else None
            if robot.fault_latched:
                control = False
            if robot.busy or not control:
                hold.clear()
                leader, ratio, prog, ready = None, 0.0, 0.0, False
            else:
                leader, ratio, prog, ready = hold.push(now, target)
            if state:
                cv2.putText(disp, f"fingers:{list(state)}", (20, 110), cv2.FONT_HERSHEY_COMPLEX, 0.8,
                            (0, 255, 0), 2)
            if leader and ratio >= 0.5:
                cv2.putText(disp, leader, (20, 170), cv2.FONT_HERSHEY_COMPLEX, 1.4, (0, 0, 255), 3)
                cv2.rectangle(disp, (20, 190), (420, 220), (255, 255, 255), 2)
                cv2.rectangle(disp, (20, 190), (20 + int(400 * prog), 220), (0, 200, 0), cv2.FILLED)
                if ready and now - robot.last_done >= COOLDOWN_S:
                    print(f"[gesture] {leader} held {GESTURE_HOLD_S:.0f}s -> move")
                    hold.clear()
                    robot.move_async(leader)

            # ── HUD ──
            fps = 0.9 * fps + 0.1 / dt
            who = ("PERSON LOCKED" if person.confirmed(now) else "PERSON..." if person.tracking(now)
                   else "SEARCHING")
            st = robot.rtde.get()
            cv2.putText(disp, f"{who}  zoom x{view.zoom:.2f}  fps:{fps:.0f}  gestures:"
                              f"{'ON' if control else 'OFF'}  {'MOVING' if robot.busy else 'idle'}  "
                              f"at:{robot.cur_target} {'FAULT LATCHED' if robot.fault_latched else ''}", (20, 50), cv2.FONT_HERSHEY_COMPLEX, 0.8, (0, 255, 0), 2)
            if st:
                x, y, z = st["actual_TCP_pose"][:3]
                cv2.putText(disp, f"TCP {x:.3f} {y:.3f} {z:.3f}", (20, H - 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)
            else:
                cv2.putText(disp, "RTDE LOST", (20, 260), cv2.FONT_HERSHEY_COMPLEX, 1.2, (0, 0, 255), 3)
                control = False
                robot.fault_latched = True

            cv2.imshow("UR5e gesture control", disp)
            k = cv2.waitKey(1) & 0xFF
            if k in (27, ord("q")):
                break
            if k == ord("x"):
                robot.fault_latched = True
                robot.stop()
                control = False
                print("[robot] STOP, gestures OFF")
            elif k == ord("g"):
                if not robot.fault_latched:
                    control = not control
                else:
                    print("[robot] fault/stop latch active; restart required")
            elif ord("0") <= k <= ord("5") and not robot.busy and not robot.fault_latched:
                robot.move_async(names[k - ord("0")])
    finally:
        if robot.busy:
            robot.stop()
        cam.stop()
        faces.stop()
        robot.close()
        hands.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
