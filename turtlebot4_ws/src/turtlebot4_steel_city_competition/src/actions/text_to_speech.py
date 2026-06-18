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


CONFIG = {
    "audio_output_topic": "/audio_output",
    "publish_queue_size": 10,
    "test_sentence": "Hello. I am ServerBot. This is a test of the text-to-speech system.",
}


class TextToSpeech(Node):
    def __init__(self) -> None:
        super().__init__("text_to_speech")

        self.publisher = self.create_publisher(
            AudioData,
            CONFIG["audio_output_topic"],
            CONFIG["publish_queue_size"],
        )

        self.message_count = 0
        self.last_message_time: Optional[float] = None

        self.get_logger().info(
            f"Text-to-speech node initialized. Publishing to {CONFIG['audio_output_topic']}"
        )

    def generate_speech(self, text: str) -> bool:
        self.get_logger().info(f"Generating speech: {text!r}")

        try:
            audio = tts.speak(text)
        except Exception as exc:
            self.get_logger().error(f"TTS generation failed: {exc}")
            return False

        if audio is None:
            self.get_logger().error("TTS returned no audio")
            return False

        try:
            audio = np.asarray(audio, dtype=np.float32).flatten()
        except Exception as exc:
            self.get_logger().error(f"Could not convert TTS audio to numpy array: {exc}")
            return False

        if audio.size == 0:
            self.get_logger().error("TTS audio array is empty")
            return False

        try:
            processed = process_audio_for_transmission(audio)
            output_audio = np.asarray(processed.original, dtype=np.float32).flatten()
        except Exception as exc:
            self.get_logger().error(f"Audio processing for transmission failed: {exc}")
            return False

        if output_audio.size == 0:
            self.get_logger().error("Processed audio array is empty")
            return False

        output_audio = np.clip(output_audio, -1.0, 1.0)
        int16_audio = (output_audio * 32767.0).astype(np.int16)

        msg = AudioData()
        payload = int16_audio.tobytes()

        try:
            msg.data = payload
        except TypeError:
            msg.data = list(payload)

        self.publisher.publish(msg)

        self.message_count += 1
        self.last_message_time = time.time()

        self.get_logger().info(
            f"Published audio message #{self.message_count} "
            f"({len(int16_audio)} samples)"
        )

        return True

    def generate_and_publish_speech(self, text: str) -> bool:
        return self.generate_speech(text)

    def destroy_node(self) -> bool:
        return super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = TextToSpeech()

    try:
        time.sleep(1.0)

        success = node.generate_speech(CONFIG["test_sentence"])

        if success:
            print("[TTS] Speech published successfully")
        else:
            print("[TTS] Failed to generate speech")

        time.sleep(1.0)

    except KeyboardInterrupt:
        print("\n[TTS] Interrupted")

    finally:
        node.destroy_node()

        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
