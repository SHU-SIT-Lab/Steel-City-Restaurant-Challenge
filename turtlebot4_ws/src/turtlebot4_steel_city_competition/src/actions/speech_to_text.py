#!/usr/bin/env python3

import time
from pathlib import Path
import sys
from typing import Any, Optional

import queue

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

# Make sibling modules in src importable when this script is run directly.
SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from helpers.retrieve_mic import AudioData, MIC_CONFIG, process_mic_bytes


# --- Speech-to-text (Whisper) settings ---
STT_CONFIG = {
    "whisper_model": "base",        # tiny | base | small | medium (bigger = better, slower)
    "language": "en",
    "speech_rms_threshold": 0.05,   # chunk loudness above this counts as speech
    "silence_seconds": 0.8,         # a pause this long ends an utterance
    "min_utterance_seconds": 0.3,   # ignore shorter blips
    "max_utterance_seconds": 15.0,  # force-finish very long speech
    "text_topic": "/speech_text",
}

_whisper_model = None


def load_whisper_model(name: str | None = None):
    """Load and cache the Whisper model (imported lazily to keep startup light)."""
    global _whisper_model
    if _whisper_model is None:
        import whisper
        _whisper_model = whisper.load_model(name or STT_CONFIG["whisper_model"])
    return _whisper_model


def transcribe_array(audio: np.ndarray) -> str:
    """Transcribe a float32 16 kHz mono numpy array to text (no ffmpeg needed)."""
    if audio is None or audio.size == 0:
        return ""
    model = load_whisper_model()
    result = model.transcribe(
        audio.astype(np.float32), language=STT_CONFIG["language"], fp16=False
    )
    return result.get("text", "").strip()


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

        # --- Utterance assembly (streaming voice-activity detection) ---
        self._utterance_buffer: list[np.ndarray] = []
        self._is_speaking = False
        self._silence_elapsed = 0.0
        self._utterance_len = 0.0
        self._utterances: "queue.Queue[str]" = queue.Queue()
        self._sample_rate = MIC_CONFIG["whisper_sample_rate"]

        # Publish finished transcripts so other nodes may subscribe if they prefer.
        self.text_publisher = self.create_publisher(String, STT_CONFIG["text_topic"], 10)

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
        """Assemble streamed mic chunks into utterances and transcribe them.

        Called once per mic message with that chunk's audio. We buffer chunks,
        watch for a pause (silence), then transcribe the whole utterance with
        Whisper and make the text available via get_next_utterance() and the
        /speech_text topic.
        """
        if turtlebot_audio is None or turtlebot_audio.size == 0:
            return

        chunk = turtlebot_audio.astype(np.float32)
        chunk_seconds = chunk.shape[0] / float(self._sample_rate)
        rms = float(np.sqrt(np.mean(chunk * chunk)))
        is_speech = rms >= STT_CONFIG["speech_rms_threshold"]

        if is_speech:
            self._is_speaking = True
            self._silence_elapsed = 0.0
        elif self._is_speaking:
            self._silence_elapsed += chunk_seconds

        if self._is_speaking:
            self._utterance_buffer.append(chunk)
            self._utterance_len += chunk_seconds

        ended = self._is_speaking and self._silence_elapsed >= STT_CONFIG["silence_seconds"]
        too_long = self._utterance_len >= STT_CONFIG["max_utterance_seconds"]
        if ended or too_long:
            self._finalize_utterance()

    def _finalize_utterance(self) -> None:
        """Transcribe the buffered utterance and publish the text."""
        buffer = self._utterance_buffer
        length = self._utterance_len
        # Reset state for the next utterance before the (slow) transcription.
        self._utterance_buffer = []
        self._is_speaking = False
        self._silence_elapsed = 0.0
        self._utterance_len = 0.0

        if not buffer or length < STT_CONFIG["min_utterance_seconds"]:
            return

        audio = np.concatenate(buffer)
        try:
            text = transcribe_array(audio)
        except Exception as exc:
            self.get_logger().error(f"Whisper failed: {exc}")
            return

        if not text:
            return

        self.get_logger().info(f"Heard: {text!r}")
        self._utterances.put(text)
        self.text_publisher.publish(String(data=text))

    def get_next_utterance(self, timeout: float = 8.0) -> Optional[str]:
        """Wait up to `timeout` seconds for the next transcript, else return None.

        Safe to call from a behavior: the mic callback runs on another executor
        thread (MultiThreadedExecutor), so it keeps filling the queue while this
        waits. This is the request-with-timeout the take-order behavior uses.
        """
        try:
            return self._utterances.get(timeout=timeout)
        except queue.Empty:
            return None

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
