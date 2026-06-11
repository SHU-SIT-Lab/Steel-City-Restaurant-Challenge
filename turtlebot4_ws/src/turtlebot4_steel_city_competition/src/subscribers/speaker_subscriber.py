#!/usr/bin/env python3

import sys
from typing import Optional

import numpy as np
import pyaudio
import rclpy
from rclpy.node import Node

try:
    from audio_common_msgs.msg import AudioData  # type: ignore
except ImportError:
    from std_msgs.msg import UInt8MultiArray as AudioData


# Global settings for speaker playback.
SPEAKER_CONFIG = {
    "topic": "/audio_output",
    "input_sample_rate": 16000,  # Rate of incoming audio
    "output_sample_rate": 44100,  # Rate hardware supports
    "channels": 1,
    "sample_width_bytes": 2,
    "frames_per_buffer": 2048,
}


class SpeakerSubscriber(Node):
    """Node that subscribes to audio and plays it through the speaker."""

    def __init__(self) -> None:
        super().__init__("speaker_subscriber")

        self.subscription = self.create_subscription(
            AudioData,
            SPEAKER_CONFIG["topic"],
            self._audio_callback,
            10,
        )

        # Initialize PyAudio for speaker output.
        self.p = pyaudio.PyAudio()
        try:
            self.stream = self.p.open(
                format=pyaudio.paInt16,
                channels=SPEAKER_CONFIG["channels"],
                rate=SPEAKER_CONFIG["output_sample_rate"],
                output=True,
                frames_per_buffer=SPEAKER_CONFIG["frames_per_buffer"],
            )
        except Exception as e:
            self.get_logger().error(f"Failed to open speaker: {e}")
            sys.exit(1)

        self.get_logger().info(f"Listening for audio on {SPEAKER_CONFIG['topic']}")

    def _resample_audio(self, audio_int16: np.ndarray) -> np.ndarray:
        """
        Resample audio from input rate to output rate.

        Args:
            audio_int16: Audio as int16 samples.

        Returns:
            Resampled audio as int16 samples.
        """
        if (
            SPEAKER_CONFIG["input_sample_rate"]
            == SPEAKER_CONFIG["output_sample_rate"]
        ):
            return audio_int16

        # Convert to float
        audio_float = audio_int16.astype(np.float32) / 32768.0

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

        # Convert back to int16
        audio_int16_resampled = (audio_resampled * 32767).astype(np.int16)
        return audio_int16_resampled

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

            # Resample if needed
            if (
                SPEAKER_CONFIG["input_sample_rate"]
                != SPEAKER_CONFIG["output_sample_rate"]
            ):
                audio_int16 = self._resample_audio(audio_int16)

            # Play audio through speaker
            self.stream.write(audio_int16.tobytes(), exception_on_underflow=False)
            self.get_logger().debug(f"Played samples")
        except Exception as e:
            self.get_logger().warn(f"Speaker playback error: {str(e)}")

    def destroy_node(self) -> bool:
        if hasattr(self, "stream") and self.stream:
            self.stream.stop_stream()
            self.stream.close()
        if hasattr(self, "p") and self.p:
            self.p.terminate()
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
