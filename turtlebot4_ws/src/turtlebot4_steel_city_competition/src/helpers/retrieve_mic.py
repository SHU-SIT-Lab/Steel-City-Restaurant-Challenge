#!/usr/bin/env python3

from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np
import rclpy
from rclpy.node import Node

try:
	# Preferred message type for ROS audio streams.
	from audio_common_msgs.msg import AudioData  # type: ignore
except ImportError:
	# Fallback message type if audio_common_msgs is not installed.
	from std_msgs.msg import UInt8MultiArray as AudioData


# Global settings: update these values to tune audio behavior.
MIC_CONFIG = {
	"topic": "/audio",
	"queue_size": 20,
	"input_sample_rate": 16000,
	"whisper_sample_rate": 16000,
	"sample_width_bytes": 2,
	"upsample_scale": 2.0,
	"downsample_scale": 0.5,
	"normalize": True,
}


@dataclass
class MicFrames:
	raw_bytes: bytes = b""
	raw_audio: Optional[np.ndarray] = None
	upsampled_audio: Optional[np.ndarray] = None
	downsampled_audio: Optional[np.ndarray] = None
	whisper_audio: Optional[np.ndarray] = None
	features: Optional[Dict[str, float]] = None


def bytes_to_float_audio(payload: bytes, sample_width_bytes: int = 2) -> np.ndarray:
	if not payload:
		return np.array([], dtype=np.float32)

	if sample_width_bytes != 2:
		raise ValueError("Only 16-bit PCM is supported right now.")

	pcm = np.frombuffer(payload, dtype=np.int16)
	return (pcm.astype(np.float32) / 32768.0).copy()


def normalize_audio(audio: np.ndarray) -> np.ndarray:
	if audio.size == 0:
		return audio
	peak = float(np.max(np.abs(audio)))
	if peak <= 1e-9:
		return audio
	return audio / peak


def resample_audio(audio: np.ndarray, from_rate: int, to_rate: int) -> np.ndarray:
	if audio.size == 0 or from_rate == to_rate:
		return audio

	new_length = int(round(audio.shape[0] * float(to_rate) / float(from_rate)))
	if new_length <= 1:
		return np.array([], dtype=np.float32)

	x_old = np.linspace(0.0, 1.0, num=audio.shape[0], endpoint=False)
	x_new = np.linspace(0.0, 1.0, num=new_length, endpoint=False)
	return np.interp(x_new, x_old, audio).astype(np.float32)


def upsample_audio(audio: np.ndarray, scale: Optional[float] = None) -> np.ndarray:
	value = scale if scale is not None else MIC_CONFIG["upsample_scale"]
	to_rate = max(1, int(MIC_CONFIG["input_sample_rate"] * value))
	return resample_audio(audio, MIC_CONFIG["input_sample_rate"], to_rate)


def downsample_audio(audio: np.ndarray, scale: Optional[float] = None) -> np.ndarray:
	value = scale if scale is not None else MIC_CONFIG["downsample_scale"]
	to_rate = max(1, int(MIC_CONFIG["input_sample_rate"] * value))
	return resample_audio(audio, MIC_CONFIG["input_sample_rate"], to_rate)


def prepare_for_whisper(audio: np.ndarray, from_rate: int) -> np.ndarray:
	whisper_audio = resample_audio(audio, from_rate, MIC_CONFIG["whisper_sample_rate"])
	if MIC_CONFIG["normalize"]:
		whisper_audio = normalize_audio(whisper_audio)
	return whisper_audio


def extract_audio_features(audio: np.ndarray, sample_rate: int) -> Dict[str, float]:
	if audio.size == 0:
		return {
			"duration_sec": 0.0,
			"rms": 0.0,
			"peak": 0.0,
			"zero_crossing_rate": 0.0,
		}

	zero_crossings = np.mean(np.abs(np.diff(np.sign(audio)))) / 2.0
	return {
		"duration_sec": float(audio.shape[0] / sample_rate),
		"rms": float(np.sqrt(np.mean(audio * audio))),
		"peak": float(np.max(np.abs(audio))),
		"zero_crossing_rate": float(zero_crossings),
	}


def process_mic_bytes(payload: bytes) -> MicFrames:
	raw_audio = bytes_to_float_audio(payload, MIC_CONFIG["sample_width_bytes"])
	if MIC_CONFIG["normalize"]:
		raw_audio = normalize_audio(raw_audio)

	upsampled = upsample_audio(raw_audio)
	downsampled = downsample_audio(raw_audio)
	whisper_audio = prepare_for_whisper(raw_audio, MIC_CONFIG["input_sample_rate"])
	features = extract_audio_features(whisper_audio, MIC_CONFIG["whisper_sample_rate"])

	return MicFrames(
		raw_bytes=payload,
		raw_audio=raw_audio,
		upsampled_audio=upsampled,
		downsampled_audio=downsampled,
		whisper_audio=whisper_audio,
		features=features,
	)


class RetrieveMicrophone(Node):
	def __init__(self) -> None:
		super().__init__("retrieve_microphone")
		self.latest = MicFrames()

		# Subscribe to TurtleBot microphone topic.
		self.subscription = self.create_subscription(
			AudioData,
			MIC_CONFIG["topic"],
			self._mic_callback,
			MIC_CONFIG["queue_size"],
		)

	def _mic_callback(self, msg: Any) -> None:
		payload = bytes(msg.data)
		self.latest = process_mic_bytes(payload)

	def get_latest_audio(self) -> MicFrames:
		return self.latest


def main(args=None) -> None:
	rclpy.init(args=args)
	node = RetrieveMicrophone()
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
