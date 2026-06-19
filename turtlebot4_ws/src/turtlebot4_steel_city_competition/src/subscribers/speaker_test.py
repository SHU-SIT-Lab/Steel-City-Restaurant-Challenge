#!/usr/bin/env python3

import time
from pathlib import Path

import numpy as np
import sounddevice as sd
import scipy.io.wavfile as wavfile


# Configuration
SPEAKER_CONFIG = {
    "device_id": 4,  # Change this to your desired device ID
    "wav_file": Path(__file__).parent / "test" / "test.wav",
}


def main() -> None:
    """Load and play audio from test.wav through the speaker."""
    
    device_id = SPEAKER_CONFIG["device_id"]
    wav_path = SPEAKER_CONFIG["wav_file"]
    
    # Get device info
    try:
        device_info = sd.query_devices(device_id)
    except Exception as e:
        print(f"[SPEAKER TEST] ❌ Device not found: {e}")
        return
    
    device_sample_rate = int(device_info["default_samplerate"])
    
    print(f"[SPEAKER TEST] Device: {device_info['name']}")
    print(f"[SPEAKER TEST] Sample rate: {device_sample_rate} Hz")
    
    # Load WAV file
    if not wav_path.exists():
        print(f"[SPEAKER TEST] ❌ File not found: {wav_path}")
        return
    
    try:
        sample_rate, audio_data = wavfile.read(str(wav_path))
        print(f"[SPEAKER TEST] Loaded: {wav_path.name}")
        
        # Convert to float32
        if audio_data.dtype == np.int16:
            audio_float = audio_data.astype(np.float32) / 32768.0
        else:
            audio_float = audio_data.astype(np.float32)
        
        # Resample if needed
        if sample_rate != device_sample_rate:
            print(f"[SPEAKER TEST] Resampling {sample_rate} Hz → {device_sample_rate} Hz...")
            input_length = len(audio_float)
            output_length = int(input_length * device_sample_rate / sample_rate)
            old_indices = np.linspace(0, input_length - 1, input_length, dtype=np.float32)
            new_indices = np.linspace(0, input_length - 1, output_length, dtype=np.float32)
            audio_float = np.interp(new_indices, old_indices, audio_float).astype(np.float32)
        
        print(f"[SPEAKER TEST] 🔊 Playing...")
        
        start_time = time.time()
        sd.play(audio_float, samplerate=device_sample_rate, device=device_id, blocking=True)
        elapsed = time.time() - start_time
        
        print(f"[SPEAKER TEST] ✓ Finished ({elapsed:.2f}s)")
        
    except Exception as e:
        print(f"[SPEAKER TEST] ❌ Error: {e}")


if __name__ == "__main__":
    main()






