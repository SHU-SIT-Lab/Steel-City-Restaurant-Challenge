#!/usr/bin/env python3

import queue
import sys
import time
from pathlib import Path
from typing import Any, Optional

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from helpers.retrieve_mic import AudioData, MIC_CONFIG, process_mic_bytes
from helpers import stt


CONFIG = {
    "debug": False,
    "debug_record_duration_sec": 3.0,
    "silence_duration_sec": 0.8,
    "min_audio_seconds": 0.4,
    "max_audio_seconds": 10.0,
    "min_speech_threshold": 0.01,
    "max_speech_threshold": 0.12,
    "speech_threshold_multiplier": 3.0,
    "noise_ema_alpha": 0.08,
    "speech_text_topic": "/speech_text",
}


class SpeechToText(Node):
    def __init__(self) -> None:
        super().__init__("speech_to_text")

        self.debug = CONFIG["debug"]
        self.turtlebot_audio: Optional[np.ndarray] = None

        self._speech_active = False
        self._speech_frames: list[np.ndarray] = []
        self._speech_samples = 0
        self._silent_samples = 0

        self._noise_rms = CONFIG["min_speech_threshold"]
        self._has_noise_baseline = False

        self._last_msg_time: Optional[float] = None
        self._estimated_input_rate = int(MIC_CONFIG["input_sample_rate"])

        self._debug_start_time: Optional[float] = None
        self._debug_audio_frames: list[np.ndarray] = []
        self._debug_raw_frames: list[np.ndarray] = []
        self._debug_saved_once = False

        self._utterances: "queue.Queue[str]" = queue.Queue()

        self.text_publisher = self.create_publisher(
            String,
            CONFIG["speech_text_topic"],
            10,
        )

        self.subscription = self.create_subscription(
            AudioData,
            MIC_CONFIG["topic"],
            self._mic_callback,
            MIC_CONFIG["queue_size"],
        )

        self.get_logger().info(
            f"Speech-to-Text started on {MIC_CONFIG['topic']} "
            f"(debug={self.debug}, text_topic={CONFIG['speech_text_topic']})"
        )

    def _mic_callback(self, msg: Any) -> None:
        data = msg.data if isinstance(msg.data, bytes) else bytes(msg.data)

        source_rate = self._estimate_input_sample_rate(data)
        processed = process_mic_bytes(data, input_sample_rate=source_rate)

        self.turtlebot_audio = processed.whisper_audio

        if self.debug:
            self._record_debug_audio(data, source_rate)
            return

        self._process_speech()

    def _estimate_input_sample_rate(self, data: bytes) -> int:
        chunk_samples = len(data) // int(MIC_CONFIG["sample_width_bytes"])
        now = time.time()

        if self._last_msg_time is not None and chunk_samples > 0:
            dt = now - self._last_msg_time

            if dt > 1e-3:
                instantaneous_rate = chunk_samples / dt

                if 8000.0 <= instantaneous_rate <= 96000.0:
                    alpha = 0.2
                    self._estimated_input_rate = int(
                        round(
                            (1.0 - alpha) * self._estimated_input_rate
                            + alpha * instantaneous_rate
                        )
                    )

        self._last_msg_time = now

        common_rates = [8000, 11025, 16000, 22050, 24000, 32000, 44100, 48000]
        snapped_rate = min(
            common_rates,
            key=lambda rate: abs(rate - self._estimated_input_rate),
        )

        MIC_CONFIG["input_sample_rate"] = int(snapped_rate)

        return int(snapped_rate)

    def _record_debug_audio(self, data: bytes, source_rate: int) -> None:
        if self._debug_saved_once:
            return

        if self._debug_start_time is None:
            self._debug_start_time = time.time()
            print(
                f"[DEBUG] Recording {CONFIG['debug_record_duration_sec']:.1f}s "
                f"from {MIC_CONFIG['topic']} at estimated {source_rate} Hz..."
            )

        raw_chunk = np.frombuffer(data, dtype=np.int16).copy()

        if raw_chunk.size > 0:
            self._debug_raw_frames.append(raw_chunk)

        if self.turtlebot_audio is not None:
            self._debug_audio_frames.append(self.turtlebot_audio.copy())

        elapsed = time.time() - self._debug_start_time

        if elapsed < float(CONFIG["debug_record_duration_sec"]):
            return

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        debug_dir = Path(__file__).parent / "debug"
        debug_dir.mkdir(exist_ok=True)

        try:
            import scipy.io.wavfile as wavfile

            raw_audio = np.concatenate(self._debug_raw_frames, axis=0)

            target_samples = int(
                float(CONFIG["debug_record_duration_sec"]) * source_rate
            )

            if raw_audio.size > target_samples:
                raw_audio = raw_audio[:target_samples]

            raw_filename = debug_dir / f"stt_topic_raw_3s_{timestamp}.wav"

            wavfile.write(
                str(raw_filename),
                int(source_rate),
                raw_audio.astype(np.int16),
            )

            processed = process_mic_bytes(
                raw_audio.tobytes(),
                input_sample_rate=source_rate,
            )

            whisper_audio = processed.whisper_audio.astype(np.float32)
            whisper_filename = debug_dir / f"stt_topic_whisper_3s_{timestamp}.wav"

            wavfile.write(
                str(whisper_filename),
                int(MIC_CONFIG["whisper_sample_rate"]),
                (whisper_audio * 32767).astype(np.int16),
            )

            raw_peak = (
                np.max(np.abs(raw_audio.astype(np.float32))) / 32768.0
                if raw_audio.size
                else 0.0
            )

            whisper_peak = (
                float(np.max(np.abs(whisper_audio)))
                if whisper_audio.size
                else 0.0
            )

            print(f"[DEBUG] Saved raw capture to {raw_filename}")
            print(f"[DEBUG] Saved whisper capture to {whisper_filename}")
            print(
                f"[DEBUG] Raw duration: {raw_audio.size / float(source_rate):.2f}s, "
                f"raw peak: {raw_peak:.3f}, whisper peak: {whisper_peak:.3f}"
            )

        except Exception as exc:
            print(f"[ERROR] Failed to save debug audio: {exc}")

        self._debug_saved_once = True
        self._debug_audio_frames = []
        self._debug_raw_frames = []

    def _process_speech(self) -> None:
        if self.turtlebot_audio is None:
            return

        chunk = self.turtlebot_audio.astype(np.float32).flatten()

        if chunk.size == 0:
            return

        rms = float(np.sqrt(np.mean(chunk ** 2)))

        if not self._speech_active:
            if not self._has_noise_baseline:
                self._noise_rms = max(rms, CONFIG["min_speech_threshold"])
                self._has_noise_baseline = True
            else:
                alpha = CONFIG["noise_ema_alpha"]
                self._noise_rms = (1.0 - alpha) * self._noise_rms + alpha * rms

        threshold = self._noise_rms * CONFIG["speech_threshold_multiplier"]
        threshold = max(threshold, CONFIG["min_speech_threshold"])
        threshold = min(threshold, CONFIG["max_speech_threshold"])

        if not self._speech_active and rms > threshold:
            self._speech_active = True
            self._speech_frames = [chunk.copy()]
            self._speech_samples = chunk.size
            self._silent_samples = 0
            print("[STT] Recording started...")
            return

        if not self._speech_active:
            return

        self._speech_frames.append(chunk.copy())
        self._speech_samples += chunk.size

        if rms > threshold:
            self._silent_samples = 0
        else:
            self._silent_samples += chunk.size

        sample_rate = int(MIC_CONFIG["whisper_sample_rate"])
        silence_samples = int(CONFIG["silence_duration_sec"] * sample_rate)
        max_samples = int(CONFIG["max_audio_seconds"] * sample_rate)

        silence_reached = self._silent_samples >= silence_samples
        max_duration_reached = self._speech_samples >= max_samples

        if silence_reached or max_duration_reached:
            self._finalize_utterance()

    def _finalize_utterance(self) -> None:
        sample_rate = int(MIC_CONFIG["whisper_sample_rate"])
        min_samples = int(CONFIG["min_audio_seconds"] * sample_rate)

        frames = self._speech_frames
        total_samples = self._speech_samples

        self._speech_active = False
        self._speech_frames = []
        self._speech_samples = 0
        self._silent_samples = 0

        if not frames or total_samples < min_samples:
            return

        audio = np.concatenate(frames, axis=0).astype(np.float32)

        duration = audio.size / float(sample_rate)
        print(f"[STT] Recording finished ({duration:.2f}s)")
        print("[STT] Transcribing...")

        try:
            text = stt.transcribe_audio(audio)
        except Exception as exc:
            self.get_logger().error(f"STT transcription failed: {exc}")
            return

        if not text:
            return

        text = text.strip()

        if not text:
            return

        print(f"[STT] ✓ {text}")
        self.get_logger().info(f"Heard: {text!r}")

        self._utterances.put(text)
        self.text_publisher.publish(String(data=text))

    def get_next_utterance(self, timeout: float = 8.0) -> Optional[str]:
        try:
            return self._utterances.get(timeout=timeout)
        except queue.Empty:
            return None

    def destroy_node(self) -> bool:
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
