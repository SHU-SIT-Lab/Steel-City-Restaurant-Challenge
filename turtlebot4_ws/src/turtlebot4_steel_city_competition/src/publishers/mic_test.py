#!/usr/bin/env python3

import time
from pathlib import Path
import pyaudio
import numpy as np

from mic_audio_utils import open_input_stream_with_device_rate

MIC_CONFIG = {
    "sample_rate": 16000,
    "chunk_size": 2048,
    "channels": 1,
    "sample_width_bytes": 2,
    "record_duration_sec": 3,
    "device_index": int(__import__("os").environ["MIC_DEVICE_INDEX"]) if "MIC_DEVICE_INDEX" in __import__("os").environ else None,
}


def test_microphone() -> None:
    """Test mic setup and save 3 seconds of audio."""
    print("[MIC TEST] Starting microphone test...")

    try:
        p = pyaudio.PyAudio()

        # Open stream with working sample rate
        stream, working_rate, device_info = open_input_stream_with_device_rate(
            p,
            MIC_CONFIG["channels"],
            MIC_CONFIG["chunk_size"],
            device_index=MIC_CONFIG["device_index"],
        )
        MIC_CONFIG["sample_rate"] = working_rate
        print(f"[SUCCESS] Opened stream at {working_rate} Hz")
        if device_info:
            print(f"[INFO] Device: {device_info.get('name', 'Unknown')}")
            print(f"[INFO] Max input channels: {device_info.get('maxInputChannels', 'Unknown')}")
            print(f"[INFO] Default sample rate: {device_info.get('defaultSampleRate', 'Unknown')} Hz")
        print(f"[INFO] Channels: {MIC_CONFIG['channels']}")
        print(f"[INFO] Chunk size: {MIC_CONFIG['chunk_size']}")

        # Record audio
        print(f"[RECORDING] Recording for {MIC_CONFIG['record_duration_sec']} seconds...")
        frames = []
        total_frames = int(round(working_rate * MIC_CONFIG["record_duration_sec"]))
        frames_remaining = total_frames
        chunk_count = 0
        total_chunks = int(np.ceil(total_frames / MIC_CONFIG["chunk_size"]))

        while frames_remaining > 0:
            frames_to_read = min(MIC_CONFIG["chunk_size"], frames_remaining)
            data = stream.read(frames_to_read, exception_on_overflow=False)
            frames.append(np.frombuffer(data, dtype=np.int16))
            frames_remaining -= frames_to_read
            chunk_count += 1
            progress = int(chunk_count / total_chunks * 100)
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
    finally:
        try:
            stream.stop_stream()
            stream.close()
        except Exception:
            pass
        try:
            p.terminate()
        except Exception:
            pass


if __name__ == "__main__":
    test_microphone()
