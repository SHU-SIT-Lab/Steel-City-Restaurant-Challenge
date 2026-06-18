"""Text-to-speech with cross-platform support (Windows SAPI / Linux pyttsx3)."""

import tempfile
import os
import platform
from typing import Optional

import numpy as np
import scipy.io.wavfile as wavfile


# Configuration
TTS_CONFIG = {
    "rate": 200,  # Speech rate (words per minute)
    "volume": 1.0,  # Volume (0.0 to 1.0)
}


def _synthesize_windows(text: str, wav_path: str) -> bool:
    """Use Windows SAPI to write speech to a WAV file."""
    try:
        import win32com.client
        import pythoncom
        
        pythoncom.CoInitialize()
        try:
            sapi = win32com.client.Dispatch("SAPI.SpVoice")
            stream = win32com.client.Dispatch("SAPI.SpFileStream")
            stream.Open(wav_path, 3)  # 3 = SSFMCreateForWrite
            sapi.AudioOutputStream = stream
            sapi.Rate = 1  # -10 (slow) to 10 (fast), 0 = normal
            sapi.Volume = 100
            sapi.Speak(text)
            stream.Close()
            return True
        finally:
            pythoncom.CoUninitialize()
    except Exception as e:
        print(f"[TTS] Windows SAPI error: {e}")
        return False


def _synthesize_linux(text: str, wav_path: str) -> bool:
    """Use pyttsx3 to synthesize speech on Linux."""
    try:
        import pyttsx3
        
        engine = pyttsx3.init()
        engine.setProperty("rate", TTS_CONFIG["rate"])
        engine.setProperty("volume", TTS_CONFIG["volume"])
        engine.save_to_file(text, wav_path)
        engine.runAndWait()
        return True
    except Exception as e:
        print(f"[TTS] Linux synthesis error: {e}")
        return False


def generate_speech(text: str) -> Optional[np.ndarray]:
    """
    Generate speech audio from text.

    Args:
        text: Text to synthesize.

    Returns:
        Audio array (float32, normalized -1.0 to 1.0) or None if generation fails.
    """
    print(f"[TTS] Generating: {text!r}")
    
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        # Choose synthesis method based on OS
        system = platform.system()
        success = False
        
        if system == "Windows":
            success = _synthesize_windows(text, tmp_path)
        else:
            success = _synthesize_linux(text, tmp_path)
        
        if not success:
            print("[TTS] Synthesis failed")
            return None
        
        # Read and convert WAV file
        sample_rate, audio_data = wavfile.read(tmp_path)
        
        # Convert to float32 normalized (-1.0 to 1.0)
        if audio_data.dtype == np.int16:
            audio = audio_data.astype(np.float32) / 32768.0
        else:
            audio = audio_data.astype(np.float32)
        
        # Handle stereo to mono
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        
        print(f"[TTS] Generated {len(audio)} samples at {sample_rate} Hz")
        return audio
        
    except Exception as e:
        print(f"[TTS] Error: {e}")
        return None
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def speak(text: str) -> Optional[np.ndarray]:
    """
    Generate speech audio (returns audio instead of playing).
    
    Args:
        text: Text to synthesize.
    
    Returns:
        Audio array (float32) or None if generation fails.
    """
    return generate_speech(text)
