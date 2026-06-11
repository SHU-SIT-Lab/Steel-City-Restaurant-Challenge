#!/usr/bin/env python3

import sys
from typing import Optional

import pyaudio
import rclpy
from rclpy.node import Node

try:
    from audio_common_msgs.msg import AudioData  # type: ignore
except ImportError:
    from std_msgs.msg import UInt8MultiArray as AudioData


# Global settings for laptop microphone capture.
MIC_CAPTURE_CONFIG = {
    "topic": "/audio",
    "sample_rate": 16000,
    "chunk_size": 2048,
    "channels": 1,
    "sample_width_bytes": 2,
}


class MicrophonePublisher(Node):
    def __init__(self) -> None:
        super().__init__("mic_publisher")
        self.publisher = self.create_publisher(
            AudioData,
            MIC_CAPTURE_CONFIG["topic"],
            10,
        )

        # Initialize PyAudio for laptop microphone.
        self.p = pyaudio.PyAudio()
        try:
            self.stream = self.p.open(
                format=pyaudio.paInt16,
                channels=MIC_CAPTURE_CONFIG["channels"],
                rate=MIC_CAPTURE_CONFIG["sample_rate"],
                input=True,
                frames_per_buffer=MIC_CAPTURE_CONFIG["chunk_size"],
            )
        except Exception as e:
            self.get_logger().error(f"Failed to open microphone: {e}")
            sys.exit(1)

        self.get_logger().info(f"Streaming laptop mic to {MIC_CAPTURE_CONFIG['topic']}")

        # Timer to continuously publish mic frames.
        self.create_timer(0.01, self._publish_mic_frame)

    def _publish_mic_frame(self) -> None:
        try:
            data = self.stream.read(MIC_CAPTURE_CONFIG["chunk_size"], exception_on_overflow=False)
            msg = AudioData()
            msg.data = list(data)
            self.publisher.publish(msg)
        except Exception as e:
            self.get_logger().warn(f"Mic read error: {e}")

    def destroy_node(self) -> bool:
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
