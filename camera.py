"""RTSP camera: ffmpeg pipe (NVDEC) or OpenCV fallback, latest-frame thread."""
import os, shutil, subprocess, threading, time
import cv2
import numpy as np
from config import *


def _find(exe, explicit):
    return explicit if explicit and os.path.isfile(explicit) else shutil.which(exe)


class Camera:
    def __init__(self, url):
        self.url = url
        self.frame, self.ts = None, 0.0
        self.lock = threading.Lock()
        self.stop_flag = False
        self.use_nvdec = USE_NVDEC
        self.ffmpeg = _find("ffmpeg", FFMPEG_PATH) if USE_FFMPEG_PIPE else None
        self.ffprobe = _find("ffprobe", FFPROBE_PATH)
        if USE_FFMPEG_PIPE and not self.ffmpeg:
            print("[cam] ffmpeg not found -> OpenCV fallback")
        threading.Thread(target=self._run, daemon=True).start()

    def _set(self, f):
        with self.lock:
            self.frame, self.ts = f, time.time()

    def latest(self):
        with self.lock:
            return (None if self.frame is None else self.frame.copy()), self.ts

    def wait_first(self, timeout=20):
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.latest()[0] is not None:
                return
            time.sleep(0.05)
        raise RuntimeError("No camera frames (check IP / password / ffmpeg)")

    def _probe(self):
        if self.ffprobe:
            try:
                out = subprocess.check_output(
                    [self.ffprobe, "-v", "error", "-rtsp_transport", RTSP_TRANSPORT,
                     "-select_streams", "v:0", "-show_entries", "stream=width,height",
                     "-of", "csv=p=0", self.url], timeout=15).decode().strip()
                w, h = out.split(",")[:2]
                return int(w), int(h)
            except Exception:
                pass
        cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
        ok, f = cap.read()
        cap.release()
        if not ok:
            raise RuntimeError("cannot open RTSP stream")
        return f.shape[1], f.shape[0]

    def _run(self):
        while not self.stop_flag:
            try:
                self._run_pipe() if self.ffmpeg else self._run_cv()
            except Exception as e:
                print(f"[cam] {e}; retry in 2 s")
            time.sleep(2)

    def _run_cv(self):
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
            f"rtsp_transport;{RTSP_TRANSPORT}|fflags;nobuffer|flags;low_delay")
        cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        while not self.stop_flag:
            ok, f = cap.read()
            if not ok:
                break
            self._set(f)
        cap.release()

    def _run_pipe(self):
        w, h = self._probe()
        cmd = [self.ffmpeg, "-hide_banner", "-loglevel", "error"]
        if self.use_nvdec:
            cmd += ["-hwaccel", "cuda"]
        cmd += ["-rtsp_transport", RTSP_TRANSPORT, "-fflags", "nobuffer", "-flags", "low_delay",
                "-probesize", "32", "-analyzeduration", "0", "-i", self.url,
                "-an", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                bufsize=w * h * 3 * 2)
        n, got = w * h * 3, 0
        try:
            while not self.stop_flag:
                buf = proc.stdout.read(n)
                if len(buf) < n:
                    break
                got += 1
                self._set(np.frombuffer(buf, np.uint8).reshape(h, w, 3).copy())
        finally:
            proc.kill()
        if got == 0 and self.use_nvdec:
            print("[cam] NVDEC failed -> CPU decoding")
            self.use_nvdec = False

    def stop(self):
        self.stop_flag = True
