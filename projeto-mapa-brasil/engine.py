from collections import deque
import time
from typing import Optional
import numpy as np


class GestureEngine:
    """Classifica gestos e transforma movimentos em eventos de interface."""

    def __init__(self) -> None:
        self.min_zoom = 0.8
        self.max_zoom = 3.5
        self.zoom = 1.0
        self.zoom_smoothing = 0.2

        self.swipe_history = deque(maxlen=20)
        self.swipe_window = 0.35
        self.swipe_min_distance = 0.8
        self.last_swipe = 0.0
        self.swipe_cooldown = 0.8

        self.fist_start: Optional[float] = None
        self.fist_hold_time = 1.5

    @staticmethod
    def to_pixels(hand_landmarks, width: int, height: int) -> np.ndarray:
        return np.array(
            [[landmark.x * width, landmark.y * height] for landmark in hand_landmarks],
            dtype=np.float32,
        )

    @staticmethod
    def _fingers_extended(landmarks: np.ndarray) -> list[bool]:
        wrist = landmarks[0]
        pairs = [(8, 6), (12, 10), (16, 14), (20, 18)]
        return [
            np.linalg.norm(landmarks[tip] - wrist)
            > np.linalg.norm(landmarks[pip] - wrist)
            for tip, pip in pairs
        ]

    @staticmethod
    def _thumb_extended(landmarks: np.ndarray) -> bool:
        wrist = landmarks[0]
        return np.linalg.norm(landmarks[4] - wrist) > np.linalg.norm(landmarks[3] - wrist)

    def classify(self, landmarks: Optional[np.ndarray]) -> dict:
        if landmarks is None:
            return {
                "gesture": "none",
                "pointer": None,
                "hand_size": None,
                "pinch": None,
                "center": None,
            }

        hand_size = float(np.linalg.norm(landmarks[0] - landmarks[9])) or 1.0
        extended = self._fingers_extended(landmarks)
        thumb_open = self._thumb_extended(landmarks)
        pointer = tuple(landmarks[8].astype(int))
        center = (float(np.mean(landmarks[:, 0])), float(np.mean(landmarks[:, 1])))
        count = sum(extended)

        if count == 0:
            gesture = "fist"
            pinch = None
        elif count >= 3:
            gesture = "open"
            pinch = None
        elif extended == [True, False, False, False]:
            pinch = float(np.linalg.norm(landmarks[4] - landmarks[8])) / hand_size
            gesture = "zoom" if thumb_open else "point"
        else:
            gesture = "none"
            pinch = None

        return {
            "gesture": gesture,
            "pointer": pointer,
            "hand_size": hand_size,
            "pinch": pinch,
            "center": center,
        }

    def process(self, landmarks: Optional[np.ndarray], now: Optional[float] = None) -> dict:
        now = time.monotonic() if now is None else now
        state = self.classify(landmarks)
        gesture = state["gesture"]
        action = None

        if gesture == "zoom" and state["pinch"] is not None:
            normalized = np.clip((state["pinch"] - 0.18) / 0.82, 0.0, 1.0)
            target = self.min_zoom + normalized * (self.max_zoom - self.min_zoom)
            self.zoom += (target - self.zoom) * self.zoom_smoothing

        if gesture == "open" and state["center"] and state["hand_size"]:
            self.swipe_history.append((now, state["center"][0]))
            while self.swipe_history and now - self.swipe_history[0][0] > self.swipe_window:
                self.swipe_history.popleft()
            if len(self.swipe_history) >= 3 and now - self.last_swipe > self.swipe_cooldown:
                dx = (self.swipe_history[-1][1] - self.swipe_history[0][1]) / state["hand_size"]
                if abs(dx) >= self.swipe_min_distance:
                    action = "next" if dx < 0 else "previous"
                    self.last_swipe = now
                    self.swipe_history.clear()
        else:
            self.swipe_history.clear()

        if gesture == "fist":
            if self.fist_start is None:
                self.fist_start = now
            elif now - self.fist_start >= self.fist_hold_time:
                action = "quit"
                self.reset_zoom()
        else:
            self.fist_start = None

        return {**state, "action": action}

    def reset_zoom(self) -> None:
        self.zoom = 1.0