#!/usr/bin/env python3

import sys
import time
from pathlib import Path
from typing import Optional

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

from helpers import tts
from helpers.send_audio import process_audio_for_transmission





class TextToSpeech(Node):
    """Node that generates speech from text and publishes audio."""

    def __init__(self) -> None:
        super().__init__("text_to_speech")
        self.publisher = self.create_publisher(
            AudioData,
            "/audio_output",
            10,
        )

        self.message_count = 0

        self.get_logger().info("Text-to-speech node initialized")

    def generate_and_publish_speech(self, text: str) -> bool:
        """
        Generate speech from text and publish to /audio_output.

        Args:
            text: Text to synthesize and publish.

        Returns:
            True if successful, False otherwise.
        """
        self.get_logger().info(f"Generating speech: {text!r}")
        
        # Generate audio using TTS
        audio = tts.speak(text)
        if audio is None:
            self.get_logger().error("TTS failed to generate audio")
            return False

        # Process for transmission
        processed = process_audio_for_transmission(audio)

        # Convert to int16 and publish
        int16_audio = (processed.original * 32767).astype(np.int16)
        msg = AudioData()
        msg.data = list(int16_audio.tobytes())
        self.publisher.publish(msg)

        self.message_count += 1
        self.get_logger().info(f"Published audio message #{self.message_count}")
        return True




def main(args=None) -> None:
    rclpy.init(args=args)
    node = TextToSpeech()
    
    # Test string to generate
    test_str = "Hello. How are you doing today? This is a test of the text-to-speech system."

    try:
        # Give ROS time to initialize subscriptions
        time.sleep(1)
        
        # Generate and publish test speech
        success = node.generate_and_publish_speech(test_str)
        
        if success:
            print(f"[TTS] Speech published successfully")
        else:
            print(f"[TTS] Failed to generate speech")
        
    except KeyboardInterrupt:
        print("\n[TTS] Interrupted")
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
