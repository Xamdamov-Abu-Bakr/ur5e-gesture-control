"""Read-only RTDE v2 client for UR robots; no third-party RTDE package needed."""
import socket
import struct
import threading
import time

import numpy as np
from config import RTDE_PORT


class RTDE:
    _FIELDS = b"actual_TCP_pose,actual_TCP_speed,robot_mode,safety_mode"
    _TYPES = "VECTOR6D,VECTOR6D,INT32,INT32"
    _DATA = struct.Struct(">12d2i")

    def __init__(self, host):
        self.stop_flag = False
        self._lock = threading.Lock()
        self._state = None
        self._updated = 0.0
        self._sock = socket.create_connection((host, RTDE_PORT), timeout=5)
        self._sock.settimeout(5)
        try:
            self._send(b"V", struct.pack(">H", 2))
            if self._reply(b"V") != b"\x01":
                raise RuntimeError("Robot rejected RTDE protocol v2")
            self._send(b"O", struct.pack(">d", 125.0) + self._FIELDS)
            reply = self._reply(b"O")
            if not reply or reply[0] == 0 or reply[1:].decode("ascii") != self._TYPES:
                raise RuntimeError(f"RTDE output recipe rejected: {reply!r}")
            self._recipe = reply[0]
            self._send(b"S")
            if self._reply(b"S") != b"\x01":
                raise RuntimeError("Robot rejected RTDE start")
            # Obtain an initial sample before Robot.ready() or distance_to().
            deadline = time.monotonic() + 5
            while self._state is None and time.monotonic() < deadline:
                kind, payload = self._packet()
                if kind == b"U":
                    self._update(payload)
            if self._state is None:
                raise TimeoutError("No RTDE data received from robot")
            self._sock.settimeout(1.0)
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
        except Exception:
            self._sock.close()
            raise

    def _send(self, kind, payload=b""):
        self._sock.sendall(struct.pack(">Hc", len(payload) + 3, kind) + payload)

    def _read_exact(self, n):
        chunks = bytearray()
        while len(chunks) < n:
            data = self._sock.recv(n - len(chunks))
            if not data:
                raise ConnectionError("RTDE connection closed")
            chunks.extend(data)
        return bytes(chunks)

    def _packet(self):
        size, kind = struct.unpack(">Hc", self._read_exact(3))
        if size < 3:
            raise ValueError("Invalid RTDE packet size")
        return kind, self._read_exact(size - 3)

    def _reply(self, expected):
        while True:
            kind, payload = self._packet()
            if kind == expected:
                return payload
            if kind != b"M":
                raise RuntimeError(f"Unexpected RTDE packet: {kind!r}")

    def _update(self, payload):
        if len(payload) != 1 + self._DATA.size or payload[0] != self._recipe:
            raise ValueError("Invalid RTDE data package")
        values = self._DATA.unpack(payload[1:])
        state = {"actual_TCP_pose": np.array(values[:6]),
                 "actual_TCP_speed": np.array(values[6:12]),
                 "robot_mode": values[12], "safety_mode": values[13]}
        with self._lock:
            self._state = state
            self._updated = time.monotonic()

    def _run(self):
        try:
            while not self.stop_flag:
                kind, payload = self._packet()
                if kind == b"U":
                    self._update(payload)
        except (OSError, ValueError, struct.error) as exc:
            if not self.stop_flag:
                print(f"[rtde] connection lost: {exc}")
        finally:
            with self._lock:
                self._state = None
            self._sock.close()

    def get(self):
        with self._lock:
            if self._state is None or time.monotonic() - self._updated > 1.0:
                return None
            return self._state.copy()
