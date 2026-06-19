#!/usr/bin/env python3

import os
import sys
import threading
from typing import Optional

import numpy as np
import pyaudio
import rclpy
from rclpy.node import Node

try:
    from audio_common_msgs.msg import AudioData  # type: ignore
except ImportError:
    from std_msgs.msg import UInt8MultiArray as AudioData


# Global settings for laptop microphone capture.
# Set MIC_DEVICE_INDEX env var to force a specific PyAudio device index.
MIC_CAPTURE_CONFIG = {
    "topic": "/audio",
    "sample_rate": 16000,
    "chunk_size": 2048,
    "channels": 1,
    "sample_width_bytes": 2,
    "device_index": int(os.environ["MIC_DEVICE_INDEX"]) if "MIC_DEVICE_INDEX" in os.environ else None,
}


class MicrophonePublisher(Node):
    def __init__(self) -> None:
        super().__init__("mic_publisher")
        self._silent_frame_streak = 0
        self._stop_event = threading.Event()

        # Guard against multiple concurrent publishers on the same topic.
        existing_publishers = self.get_publishers_info_by_topic(MIC_CAPTURE_CONFIG["topic"])
        if existing_publishers:
            self.get_logger().error(
                f"Another publisher already exists on {MIC_CAPTURE_CONFIG['topic']}. "
                "Stop it before starting mic_publisher to avoid corrupted interleaved audio."
            )
            raise RuntimeError("Duplicate /audio publisher detected")

        self.publisher = self.create_publisher(
            AudioData,
            MIC_CAPTURE_CONFIG["topic"],
            10,
        )

        # Initialize PyAudio for laptop microphone.
        self.p = pyaudio.PyAudio()
        try:
            self.stream = self._open_input_stream_with_device_rate()
        except Exception as e:
            self.get_logger().error(f"Failed to open microphone: {e}")
            sys.exit(1)

        self.get_logger().info(
            f"Streaming laptop mic to {MIC_CAPTURE_CONFIG['topic']} at "
            f"{MIC_CAPTURE_CONFIG['sample_rate']} Hz"
        )

        # Use a dedicated blocking capture loop to avoid timer jitter/overflows.
        self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._capture_thread.start()

    def _get_default_input_device(self) -> Optional[dict]:
        """
        Return the best available input device.

        Priority order:
          1. MIC_DEVICE_INDEX env var (explicit override — most reliable).
          2. Energy-rank probe: open each input device, read several chunks,
             pick the one with the highest total RMS across reads.
             This reliably rejects dummy/loopback hw:1,0-style devices
             that return zeros even while the real DMIC (hw:1,6) does not.
          3. OS default as last resort.
        """
        # 1. Explicit override.
        forced_idx = MIC_CAPTURE_CONFIG.get("device_index")
        if forced_idx is not None:
            try:
                info = self.p.get_device_info_by_index(int(forced_idx))
                self.get_logger().info(
                    f"Using forced device [{forced_idx}] '{info.get('name')}' (MIC_DEVICE_INDEX)"
                )
                return info
            except Exception as e:
                self.get_logger().warn(f"MIC_DEVICE_INDEX={forced_idx} invalid: {e}")

        # 2. Gather all usable input devices.
        default: Optional[dict] = None
        try:
            default = self.p.get_default_input_device_info()
        except Exception:
            pass

        candidates: list[dict] = []
        try:
            for idx in range(self.p.get_device_count()):
                info = self.p.get_device_info_by_index(idx)
                if int(info.get("maxInputChannels", 0)) >= MIC_CAPTURE_CONFIG["channels"]:
                    candidates.append(info)
        except Exception as e:
            self.get_logger().warn(f"Could not enumerate input devices: {e}")

        # Energy-rank probe: read PROBE_READS × PROBE_FRAMES from each device;
        # accumulate total absolute energy and pick the highest.
        PROBE_FRAMES = 1024
        PROBE_READS = 5
        best_info: Optional[dict] = None
        best_energy: float = -1.0

        for info in candidates:
            dev_idx = int(info.get("index", -1))
            dev_rate = int(round(float(info.get("defaultSampleRate", 48000))))
            total_energy = 0.0
            try:
                ps = self.p.open(
                    format=pyaudio.paInt16,
                    channels=MIC_CAPTURE_CONFIG["channels"],
                    rate=dev_rate,
                    input=True,
                    frames_per_buffer=PROBE_FRAMES,
                    input_device_index=dev_idx if dev_idx >= 0 else None,
                )
                for _ in range(PROBE_READS):
                    raw = ps.read(PROBE_FRAMES, exception_on_overflow=False)
                    total_energy += float(np.sum(np.abs(np.frombuffer(raw, dtype="<i2").astype(np.float32))))
                ps.stop_stream()
                ps.close()
            except Exception:
                continue

            self.get_logger().debug(
                f"Device [{dev_idx}] '{info.get('name')}' probe energy={total_energy:.0f}"
            )
            if total_energy > best_energy:
                best_energy = total_energy
                best_info = info

        if best_info is not None:
            dev_idx = best_info.get("index")
            self.get_logger().info(
                f"Selected input device [{dev_idx}] '{best_info.get('name')}' "
                f"(probe energy={best_energy:.0f}; set MIC_DEVICE_INDEX={dev_idx} to pin this)"
            )
            return best_info

        # 3. Last resort: OS default.
        if default is not None:
            self.get_logger().warn(
                f"Probe found no candidate devices. Using OS default [{default.get('index')}] "
                f"'{default.get('name')}'. Set MIC_DEVICE_INDEX to override."
            )
            return default

        return None

    def _open_input_stream_with_device_rate(self):
        default_device = self._get_default_input_device()
        device_index = None if default_device is None else int(default_device.get("index", -1))

        candidate_rates: list[int] = []

        if default_device is not None:
            default_rate = int(round(float(default_device.get("defaultSampleRate", 0.0))))
            if default_rate > 0:
                candidate_rates.append(default_rate)

        # Probe commonly supported rates if device default is unavailable or fails.
        candidate_rates.extend([48000, 44100, 32000, 24000, 22050, 16000, 11025, 8000])

        # Keep order, remove duplicates.
        unique_rates: list[int] = []
        seen = set()
        for rate in candidate_rates:
            if rate not in seen:
                seen.add(rate)
                unique_rates.append(rate)

        last_error: Optional[Exception] = None

        for rate in unique_rates:
            try:
                open_kwargs = {
                    "format": pyaudio.paInt16,
                    "channels": MIC_CAPTURE_CONFIG["channels"],
                    "rate": rate,
                    "input": True,
                    "frames_per_buffer": MIC_CAPTURE_CONFIG["chunk_size"],
                }
                if device_index is not None and device_index >= 0:
                    open_kwargs["input_device_index"] = device_index

                stream = self.p.open(**open_kwargs)
                MIC_CAPTURE_CONFIG["sample_rate"] = rate
                return stream
            except Exception as e:
                last_error = e

        raise RuntimeError(
            f"Could not open microphone at any tested sample rate. Last error: {last_error}"
        )

    def _publish_mic_frame(self) -> None:
        try:
            data = self.stream.read(MIC_CAPTURE_CONFIG["chunk_size"], exception_on_overflow=False)
            if any(data):
                self._silent_frame_streak = 0
            else:
                self._silent_frame_streak += 1
                if self._silent_frame_streak == 100:
                    self.get_logger().warn(
                        "Audio frames are all-zero for an extended period. Verify host mic permissions/device selection."
                    )

            msg = AudioData()
            try:
                msg.data = data
            except TypeError:
                msg.data = list(data)
            self.publisher.publish(msg)
        except Exception as e:
            self.get_logger().warn(f"Mic read error: {e}")

    def _capture_loop(self) -> None:
        while not self._stop_event.is_set() and rclpy.ok():
            self._publish_mic_frame()

    def destroy_node(self) -> bool:
        self._stop_event.set()
        if hasattr(self, "_capture_thread") and self._capture_thread.is_alive():
            self._capture_thread.join(timeout=1.0)
        if hasattr(self, "stream") and self.stream:
            self.stream.stop_stream()
            self.stream.close()
        if hasattr(self, "p") and self.p:
            self.p.terminate()
        return super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = MicrophonePublisher()
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
