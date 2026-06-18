#!/usr/bin/env python3

import sys
from typing import Optional

import numpy as np
import sounddevice as sd
import rclpy
from rclpy.node import Node

try:
    from audio_common_msgs.msg import AudioData  # type: ignore
except ImportError:
    from std_msgs.msg import UInt8MultiArray as AudioData


# Global settings for speaker playback.
SPEAKER_CONFIG = {
    "topic": "/audio_output",
    "device_id": 10,  # Change this to your desired device ID (-1 for default)
    "input_sample_rate": 16000,  # Rate of incoming audio
    "output_sample_rate": None,  # Will be auto-detected
    "channels": 1,
}


class SpeakerSubscriber(Node):
    """Node that subscribes to audio and plays it through the speaker."""

    def __init__(self) -> None:
        super().__init__("speaker_subscriber")

        # Get device info
        device_id = SPEAKER_CONFIG["device_id"]
        if device_id == -1:
            device_id = sd.default.device[1]
        
        self.output_device = device_id
        
        try:
            device_info = sd.query_devices(device_id)
            SPEAKER_CONFIG["output_sample_rate"] = int(device_info["default_samplerate"])
            self.get_logger().info(
                f"Speaker device [{device_id}]: {device_info['name']} ({SPEAKER_CONFIG['output_sample_rate']} Hz)"
            )
        except Exception as e:
            self.get_logger().error(f"Failed to query device {device_id}: {e}")
            return

        self.subscription = self.create_subscription(
            AudioData,
            SPEAKER_CONFIG["topic"],
            self._audio_callback,
            10,
        )

        self.get_logger().info(f"Listening for audio on {SPEAKER_CONFIG['topic']}")

    def _resample_audio(self, audio_float: np.ndarray) -> np.ndarray:
        """
        Resample audio from input rate to output rate.

        Args:
            audio_float: Audio as float32 samples (-1.0 to 1.0).

        Returns:
            Resampled audio as float32 samples.
        """
        if (
            SPEAKER_CONFIG["input_sample_rate"]
            == SPEAKER_CONFIG["output_sample_rate"]
        ):
            return audio_float

        # Resample using linear interpolation
        input_length = len(audio_float)
        output_length = int(
            input_length
            * SPEAKER_CONFIG["output_sample_rate"]
            / SPEAKER_CONFIG["input_sample_rate"]
        )

        old_indices = np.linspace(
            0, input_length - 1, input_length, dtype=np.float32
        )
        new_indices = np.linspace(
            0, input_length - 1, output_length, dtype=np.float32
        )
        audio_resampled = np.interp(new_indices, old_indices, audio_float)

        return audio_resampled.astype(np.float32)

    def _audio_callback(self, msg: AudioData) -> None:
        """
        Callback for incoming audio messages.

        Args:
            msg: Audio message (UInt8MultiArray or AudioData).
        """
        try:
            # Handle both message types
            data = msg.data
            if isinstance(data, list):
                data = bytes(data)

            # Convert bytes to int16 array
            audio_int16 = np.frombuffer(data, dtype=np.int16).copy()
            
            # Convert to float32 (-1.0 to 1.0 range for sounddevice)
            audio_float = audio_int16.astype(np.float32) / 32768.0

            # Resample if needed
            if (
                SPEAKER_CONFIG["input_sample_rate"]
                != SPEAKER_CONFIG["output_sample_rate"]
            ):
                audio_float = self._resample_audio(audio_float)

            # Play audio through speaker (non-blocking)
            sd.play(audio_float, samplerate=SPEAKER_CONFIG["output_sample_rate"], device=self.output_device)
            self.get_logger().debug(f"Playing audio samples")
        except Exception as e:
            self.get_logger().warn(f"Speaker playback error: {str(e)}")

    def destroy_node(self) -> bool:
        return super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = SpeakerSubscriber()
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
