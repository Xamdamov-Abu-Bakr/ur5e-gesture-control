"""UR5e control: URScript on 30002, state from RTDE."""
import socket, time, threading
import config as motion_config
import cv2
import numpy as np
from config import *
from poses import *
from rtde_client import RTDE


def rot_angle(rv1, rv2):
    R1, _ = cv2.Rodrigues(np.array(rv1, float))
    R2, _ = cv2.Rodrigues(np.array(rv2, float))
    return float(np.arccos(np.clip((np.trace(R1.T @ R2) - 1) / 2, -1.0, 1.0)))


class Robot:
    def __init__(self):
        self.rtde = RTDE(ROBOT_IP)
        self.busy = False
        self.cur_target = None
        self.fault_latched = False  # fail closed after a failed motion; restart to re-arm

    def _script(self, body):
        prog = "def gesture_prog():\n" + "".join(f"  {l}\n" for l in body) + "end\n"
        with socket.create_connection((ROBOT_IP, URSCRIPT_PORT), timeout=3) as s:
            s.sendall(prog.encode())

    def ready(self):
        st = self.rtde.get()
        # robot_mode 7 = RUNNING, safety_mode 1 = NORMAL (2 = REDUCED is also fine)
        return bool(st) and st["robot_mode"] == 7 and st["safety_mode"] in (1, 2)

    def distance_to(self, pose):
        tcp = self.rtde.get()["actual_TCP_pose"]
        return (float(np.linalg.norm(tcp[:3] - np.array(pose[:3]))),
                rot_angle(tcp[3:], pose[3:]))

    def stop(self):
        try:
            self._script([f"stopl({MOVE_ACCEL_M_S2 * 5})"])
        except OSError as e:
            print(f"[robot] stop failed: {e}")

    def move_to(self, name):
        """Blocking. Run in a worker thread."""
        pose, q = POSES[name]
        if not self.ready():
            print("[robot] not ready (mode/safety) -> refusing to move")
            return False
        dp, da = self.distance_to(pose)
        if dp < POS_TOL_M and da < ROT_TOL_RAD:
            self.cur_target = name
            return True
        print(f"[robot] -> {name}  (dist {dp*1000:.0f} mm)")
        if MOVE_MODE == "movej" and q is not None:
            qs = ",".join(f"{v:.6f}" for v in q)
            self._script([f"movej([{qs}], a={motion_config.JOINT_ACCEL_RAD_S2}, v={motion_config.JOINT_SPEED_RAD_S})"])
        else:
            p = ",".join(f"{v:.6f}" for v in pose)
            self._script([f"movel(p[{p}], a={motion_config.MOVE_ACCEL_M_S2}, v={motion_config.MOVE_SPEED_M_S})"])

        t0, ok_since = time.time(), None
        time.sleep(0.15)
        while time.time() - t0 < MOVE_TIMEOUT_S:
            st = self.rtde.get()
            if not st:
                print("[robot] RTDE lost; requesting stop")
                self.stop()
                return False
            if st["safety_mode"] not in (1, 2) or st["robot_mode"] != 7:
                print(f"[robot] ABORT: safety_mode={st['safety_mode']} robot_mode={st['robot_mode']}")
                return False
            dp, da = self.distance_to(pose)
            v = float(np.linalg.norm(st["actual_TCP_speed"][:3]))
            if dp < POS_TOL_M and da < ROT_TOL_RAD and v < STOP_SPEED_M_S:
                ok_since = ok_since or time.time()
                if time.time() - ok_since > 0.3:
                    self.cur_target = name
                    print(f"[robot] reached {name}")
                    return True
            else:
                ok_since = None
            time.sleep(0.02)
        print("[robot] move timeout")
        self.stop()
        return False

    def move_async(self, name):
        if self.busy or self.fault_latched:
            return
        self.busy = True

        def work():
            try:
                if not self.move_to(name):
                    self.fault_latched = True
                    print("[robot] motion failed; commands locked until restart")
            except Exception as e:
                self.fault_latched = True
                print(f"[robot] error: {e}; commands locked until restart")
            finally:
                self.last_done = time.time()
                self.busy = False
        self.last_done = time.time()
        threading.Thread(target=work, daemon=True).start()

    def close(self):
        self.rtde.stop_flag = True
