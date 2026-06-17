#!/usr/bin/env python3

import sys
import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import rclpy
from rclpy.node import Node

try:
    from audio_common_msgs.msg import AudioData  # type: ignore
except ImportError:
    from std_msgs.msg import UInt8MultiArray as AudioData

SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from helpers.send_audio import process_audio_for_transmission


# Global settings for text-to-speech action.
SPEECH_CONFIG = {
    "debug": True,
    "debug_window_name": "turtlebot_tts_waveform",
    "graph_width": 900,
    "graph_height": 300,
    "graph_samples": 1024,
    "debug_refresh_hz": 20.0,
    "white_noise": False,   # set True only to test the audio path with noise
}


def synthesize_to_array(text: str, target_rate: int = 16000) -> Optional[np.ndarray]:
    """Offline TTS -> float32 mono array at target_rate.

    Uses pyttsx3 (SAPI on Windows, espeak on Linux). Returns None if TTS is
    unavailable so the caller can handle the failure gracefully.
    """
    import os
    import tempfile

    try:
        import pyttsx3
        import scipy.io.wavfile as wav
    except Exception:
        return None

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp_path = f.name

        engine = pyttsx3.init()
        engine.save_to_file(text, tmp_path)
        engine.runAndWait()

        sr, data = wav.read(tmp_path)
        audio = data.astype(np.float32)
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        if np.issubdtype(data.dtype, np.integer):
            audio = audio / float(np.iinfo(data.dtype).max)

        # Resample to the rate the robot's audio topic expects.
        if sr != target_rate and audio.size:
            n = int(round(audio.shape[0] * target_rate / sr))
            x_old = np.linspace(0.0, 1.0, num=audio.shape[0], endpoint=False)
            x_new = np.linspace(0.0, 1.0, num=n, endpoint=False)
            audio = np.interp(x_new, x_old, audio).astype(np.float32)

        return audio.astype(np.float32)
    except Exception:
        return None
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


class TextToSpeech(Node):
    """Node that generates speech from text and publishes audio."""

    def __init__(self) -> None:
        super().__init__("text_to_speech")
        self.publisher = self.create_publisher(
            AudioData,
            "/audio_output",
            10,
        )

        self.turtlebot_audio: Optional[np.ndarray] = None
        self.message_count = 0
        self.last_message_time = time.time()

        # Debug visualization timer.
        if SPEECH_CONFIG["debug"]:
            self.create_timer(
                1.0 / SPEECH_CONFIG["debug_refresh_hz"],
                self._debug_update,
            )

        # Optional: continuous white-noise generator, only for testing the audio path.
        if SPEECH_CONFIG.get("white_noise", False):
            self.create_timer(0.2, self._generate_and_publish_noise)

        self.get_logger().info("Text-to-speech node initialized")

    def todo_run_tts(self, text: str) -> Optional[np.ndarray]:
        """Convert text to a 16 kHz mono float32 waveform (offline).

        Args:
            text: Input text to convert to speech.

        Returns:
            Audio array (float32, 16kHz) or None if TTS is unavailable.
        """
        audio = synthesize_to_array(text, target_rate=16000)
        if audio is None or audio.size == 0:
            self.get_logger().error(
                "TTS produced no audio (is pyttsx3 + espeak installed in this environment?)"
            )
            return None

        self.get_logger().info(f"TTS generated {audio.shape[0]} samples for: '{text}'")
        return audio

    def generate_speech(self, text: str) -> None:
        """
        Generate speech from text and publish as audio.

        Args:
            text: Text to synthesize.
        """
        audio = self.todo_run_tts(text)
        if audio is None:
            self.get_logger().error("TTS failed to generate audio")
            return

        # Process for transmission
        processed = process_audio_for_transmission(audio)
        self.turtlebot_audio = processed.original

        # Publish audio
        int16_audio = (processed.original * 32767).astype(np.int16)
        msg = AudioData()
        msg.data = list(int16_audio.tobytes())
        self.publisher.publish(msg)

        self.message_count += 1
        self.last_message_time = time.time()
        self.get_logger().info(f"Published audio #{self.message_count}")

    def _generate_and_publish_noise(self) -> None:
        """Timer callback to continuously generate and publish white noise."""
        # Generate short burst of white noise (100ms)
        sample_rate = 16000
        duration_sec = 0.1
        num_samples = int(sample_rate * duration_sec)

        # Pure white noise (70%) + low frequency tone (30%)
        white_noise = np.random.uniform(-1, 1, num_samples).astype(np.float32)
        
        # Add low frequency rumble (100Hz)
        t = np.linspace(0, duration_sec, num_samples, dtype=np.float32)
        low_tone = np.sin(2 * np.pi * 100 * t).astype(np.float32)
        
        audio = (white_noise * 0.7 + low_tone * 0.3).astype(np.float32)
        audio = (audio * 0.8).astype(np.float32)
        audio = np.clip(audio, -1.0, 1.0).astype(np.float32)

        self.turtlebot_audio = audio

        # Publish audio
        int16_audio = (audio * 32767).astype(np.int16)
        msg = AudioData()
        msg.data = list(int16_audio.tobytes())
        self.publisher.publish(msg)

        self.message_count += 1
        self.last_message_time = time.time()

    def _build_waveform_graph(self, audio: Optional[np.ndarray]) -> np.ndarray:
        """
        Build debug waveform visualization.

        Args:
            audio: Audio array to visualize.

        Returns:
            Canvas image (numpy array).
        """
        canvas = np.ones(
            (SPEECH_CONFIG["graph_height"], SPEECH_CONFIG["graph_width"], 3),
            dtype=np.uint8,
        ) * 255

        if audio is not None and len(audio) > 0:
            # Plot last N samples
            num_samples = min(len(audio), SPEECH_CONFIG["graph_samples"])
            samples = audio[-num_samples:]

            # Scale to canvas height
            mid_y = SPEECH_CONFIG["graph_height"] // 2
            half_height = (SPEECH_CONFIG["graph_height"] - 20) // 2
            x_indices = np.linspace(0, SPEECH_CONFIG["graph_width"] - 1, num_samples, dtype=int)
            y_indices = (mid_y - samples * half_height).astype(int)
            y_indices = np.clip(y_indices, 0, SPEECH_CONFIG["graph_height"] - 1)

            # Draw waveform as green line
            for i in range(len(x_indices) - 1):
                cv2.line(
                    canvas,
                    (x_indices[i], y_indices[i]),
                    (x_indices[i + 1], y_indices[i + 1]),
                    (0, 255, 0),  # Green
                    1,
                )

            # Draw center line (quiet reference)
            cv2.line(canvas, (0, mid_y), (SPEECH_CONFIG["graph_width"], mid_y), (200, 200, 200), 1)

        return canvas

    def _draw_status(self, canvas: np.ndarray) -> None:
        """
        Draw status text overlay.

        Args:
            canvas: Canvas to draw on (modified in place).
        """
        time_since_last = time.time() - self.last_message_time
        time_color = (0, 255, 0) if time_since_last < 1.0 else (255, 0, 0)

        texts = [
            f"Output: /audio_output",
            f"Messages: {self.message_count}",
            f"Last: {time_since_last:.1f}s ago",
        ]

        y_pos = 25
        for text in texts:
            cv2.putText(
                canvas,
                text,
                (10, y_pos),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                time_color,
                1,
            )
            y_pos += 25

    def _debug_update(self) -> None:
        """Timer callback to update debug visualization."""
        if not SPEECH_CONFIG["debug"]:
            return

        canvas = self._build_waveform_graph(self.turtlebot_audio)
        self._draw_status(canvas)
        cv2.imshow(SPEECH_CONFIG["debug_window_name"], canvas)
        cv2.waitKey(1)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = TextToSpeech()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
