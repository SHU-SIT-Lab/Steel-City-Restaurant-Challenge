#!/usr/bin/env python3

import time
from pathlib import Path
import sys
from typing import Any, Optional

import cv2
import numpy as np
import rclpy
from rclpy.node import Node

# Make sibling modules in src importable when this script is run directly.
SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from helpers.retrieve_mic import AudioData, MIC_CONFIG, process_mic_bytes


# Global params for speech action.
SPEECH_CONFIG = {
    "debug": True,
    "debug_window_name": "turtlebot_mic_waveform",
    "graph_width": 900,
    "graph_height": 300,
    "graph_samples": 1024,
    "debug_refresh_hz": 20.0,
}


class SpeechToText(Node):
    def __init__(self) -> None:
        super().__init__("speech_to_text")
        self.debug = SPEECH_CONFIG["debug"]
        self.turtlebot_audio: Optional[np.ndarray] = None
        self.msg_count = 0
        self.last_msg_time: Optional[float] = None

        # Subscribe to TurtleBot microphone topic.
        self.subscription = self.create_subscription(
            AudioData,
            MIC_CONFIG["topic"],
            self._mic_callback,
            MIC_CONFIG["queue_size"],
        )

        # Refresh debug graph continuously so it feels live.
        if self.debug:
            self.debug_timer = self.create_timer(1.0 / SPEECH_CONFIG["debug_refresh_hz"], self._debug_update)

    def _mic_callback(self, msg: Any) -> None:
        # Handle both AudioData and UInt8MultiArray message types.
        data = msg.data
        if isinstance(data, list):
            data = bytes(data)
        
        processed = process_mic_bytes(data)
        self.msg_count += 1
        self.last_msg_time = time.time()

        # Use whisper_audio as the default input for your speech model.
        self.turtlebot_audio = processed.whisper_audio

        self.todo_run_whisper(self.turtlebot_audio)

    def _debug_update(self) -> None:
        if not self.debug:
            return

        graph = self._build_waveform_graph(self.turtlebot_audio)
        self._draw_status(graph)
        cv2.imshow(SPEECH_CONFIG["debug_window_name"], graph)
        cv2.waitKey(1)

    def _build_waveform_graph(self, audio: Optional[np.ndarray]) -> np.ndarray:
        width = SPEECH_CONFIG["graph_width"]
        height = SPEECH_CONFIG["graph_height"]
        samples = SPEECH_CONFIG["graph_samples"]

        canvas = np.zeros((height, width, 3), dtype=np.uint8)
        mid_y = height // 2

        if audio is None or audio.size == 0:
            cv2.putText(canvas, "Waiting for mic data...", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (180, 180, 180), 2)
            return canvas

        # Keep last N samples so the graph stays stable and easy to read.
        segment = audio[-samples:] if audio.size > samples else audio
        x = np.linspace(0, width - 1, num=segment.size, dtype=np.int32)
        y = (mid_y - (segment * (height * 0.45))).astype(np.int32)
        points = np.stack((x, y), axis=1).reshape((-1, 1, 2))

        cv2.line(canvas, (0, mid_y), (width - 1, mid_y), (70, 70, 70), 1)
        cv2.polylines(canvas, [points], isClosed=False, color=(0, 255, 0), thickness=1)

        return canvas

    def _draw_status(self, canvas: np.ndarray) -> None:
        status = f"topic: {MIC_CONFIG['topic']}"
        count = f"messages: {self.msg_count}"

        if self.last_msg_time is None:
            age_text = "last msg: never"
            color = (0, 180, 255)
        else:
            age_sec = time.time() - self.last_msg_time
            age_text = f"last msg: {age_sec:.2f}s ago"
            color = (0, 255, 0) if age_sec < 1.0 else (0, 180, 255)

        cv2.putText(canvas, status, (20, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (170, 170, 170), 1)
        cv2.putText(canvas, count, (20, 52), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (170, 170, 170), 1)
        cv2.putText(canvas, age_text, (20, 76), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    def todo_run_whisper(self, turtlebot_audio: Optional[np.ndarray]) -> None:
        # TODO: Send turtlebot_audio to Whisper model.
        # TODO: Parse Whisper output and publish or return text.
        _ = turtlebot_audio

    def destroy_node(self) -> bool:
        if self.debug:
            cv2.destroyAllWindows()
        return super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = SpeechToText()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
