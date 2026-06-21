#!/usr/bin/env python3

import os
import sys
import threading

import pyaudio
import rclpy
from rclpy.node import Node

try:
    from audio_common_msgs.msg import AudioData  # type: ignore
except ImportError:
    from std_msgs.msg import UInt8MultiArray as AudioData

from mic_audio_utils import open_input_stream_with_device_rate


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
        self.p = pyaudio.PyAudio()

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

        try:
            self.stream, opened_rate, device_info = open_input_stream_with_device_rate(
                self.p,
                MIC_CAPTURE_CONFIG["channels"],
                MIC_CAPTURE_CONFIG["chunk_size"],
                device_index=MIC_CAPTURE_CONFIG["device_index"],
            )
            MIC_CAPTURE_CONFIG["sample_rate"] = opened_rate
        except Exception as e:
            self.get_logger().error(f"Failed to open microphone: {e}")
            sys.exit(1)

        if device_info:
            self.get_logger().info(
                f"Using input device [{device_info.get('index')}] '{device_info.get('name')}'"
            )

        self.get_logger().info(
            f"Streaming laptop mic to {MIC_CAPTURE_CONFIG['topic']} at "
            f"{MIC_CAPTURE_CONFIG['sample_rate']} Hz"
        )

        # Use a dedicated blocking capture loop to avoid timer jitter/overflows.
        self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._capture_thread.start()

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