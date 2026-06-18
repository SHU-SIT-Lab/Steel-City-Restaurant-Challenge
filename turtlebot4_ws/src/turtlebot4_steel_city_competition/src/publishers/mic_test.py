#!/usr/bin/env python3

import time
from pathlib import Path
from typing import Optional

import numpy as np
import pyaudio


MIC_CONFIG = {
    "sample_rate": 16000,
    "chunk_size": 2048,
    "channels": 1,
    "sample_width_bytes": 2,
    "record_duration_sec": 3,
}


def get_default_input_device() -> Optional[dict]:
    """Get info about the default input device."""
    p = pyaudio.PyAudio()
    try:
        device_info = p.get_default_input_device_info()
        return device_info
    except Exception as e:
        print(f"[ERROR] Could not query default input device: {e}")
        return None
    finally:
        p.terminate()


def open_input_stream_with_device_rate() -> tuple[pyaudio.PyAudio, pyaudio.Stream, int]:
    """Open audio stream, probing sample rates to find one that works."""
    p = pyaudio.PyAudio()
    default_device = p.get_default_input_device_info()
    device_index = int(default_device.get("index", -1)) if default_device else None
    device_name = default_device.get("name", "Unknown") if default_device else "Unknown"

    candidate_rates: list[int] = []

    if default_device is not None:
        default_rate = int(round(float(default_device.get("defaultSampleRate", 0.0))))
        if default_rate > 0:
            candidate_rates.append(default_rate)

    candidate_rates.extend([48000, 44100, 32000, 24000, 22050, 16000, 11025, 8000])

    # Remove duplicates while preserving order
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
                "channels": MIC_CONFIG["channels"],
                "rate": rate,
                "input": True,
                "frames_per_buffer": MIC_CONFIG["chunk_size"],
            }
            if device_index is not None and device_index >= 0:
                open_kwargs["input_device_index"] = device_index

            stream = p.open(**open_kwargs)
            return p, stream, rate
        except Exception as e:
            last_error = e

    p.terminate()
    raise RuntimeError(f"Could not open microphone at any tested sample rate. Last error: {last_error}")


def test_microphone() -> None:
    """Test mic setup and save 3 seconds of audio."""
    print("[MIC TEST] Starting microphone test...")

    try:
        # Get device info
        device_info = get_default_input_device()
        if device_info:
            print(f"[INFO] Device: {device_info.get('name', 'Unknown')}")
            print(f"[INFO] Max input channels: {device_info.get('maxInputChannels', 'Unknown')}")
            print(f"[INFO] Default sample rate: {device_info.get('defaultSampleRate', 'Unknown')} Hz")

        # Open stream with working sample rate
        p, stream, working_rate = open_input_stream_with_device_rate()
        print(f"[SUCCESS] Opened stream at {working_rate} Hz")
        print(f"[INFO] Channels: {MIC_CONFIG['channels']}")
        print(f"[INFO] Chunk size: {MIC_CONFIG['chunk_size']}")

        # Record audio
        print(f"[RECORDING] Recording for {MIC_CONFIG['record_duration_sec']} seconds...")
        frames = []
        num_chunks = int((working_rate / MIC_CONFIG["chunk_size"]) * MIC_CONFIG["record_duration_sec"])

        for i in range(num_chunks):
            data = stream.read(MIC_CONFIG["chunk_size"], exception_on_overflow=False)
            frames.append(np.frombuffer(data, dtype=np.int16))
            progress = int((i + 1) / num_chunks * 100)
            print(f"[RECORDING] {progress}%", end="\r")

        print("[SUCCESS] Recording complete!              ")

        # Save audio
        debug_dir = Path(__file__).parent / "debug"
        debug_dir.mkdir(exist_ok=True)

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = debug_dir / f"mic_test_{timestamp}.wav"

        try:
            import scipy.io.wavfile as wavfile
            audio = np.concatenate(frames, axis=0).astype(np.int16)
            wavfile.write(str(filename), working_rate, audio)
            print(f"[SUCCESS] Saved to {filename}")
            print(f"[INFO] Audio length: {len(audio) / working_rate:.2f} seconds")
            print(f"[INFO] Audio peak: {np.max(np.abs(audio.astype(np.float32))) / 32768:.3f} (normalized)")
        except Exception as e:
            print(f"[ERROR] Failed to save: {e}")

        # Cleanup
        stream.stop_stream()
        stream.close()
        p.terminate()

        print("[SUCCESS] Microphone test completed!")

    except Exception as e:
        print(f"[ERROR] Microphone test failed: {e}")


if __name__ == "__main__":
    test_microphone()
