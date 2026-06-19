"""Text-to-speech helper that returns audio for ROS publication."""

from __future__ import annotations

import os
import platform
import tempfile
from typing import Optional

import numpy as np
import scipy.io.wavfile as wavfile

TTS_CONFIG = {
    "rate": 200,
    "volume": 1.0,
    "target_rate": 16000,
}


def _synthesize_windows(text: str, wav_path: str) -> bool:
    try:
        import pythoncom
        import win32com.client

        pythoncom.CoInitialize()
        try:
            sapi = win32com.client.Dispatch("SAPI.SpVoice")
            stream = win32com.client.Dispatch("SAPI.SpFileStream")
            stream.Open(wav_path, 3)
            sapi.AudioOutputStream = stream
            sapi.Rate = 1
            sapi.Volume = 100
            sapi.Speak(text)
            stream.Close()
            return True
        finally:
            pythoncom.CoUninitialize()

    except Exception as exc:
        print(f"[TTS] Windows SAPI error: {exc}")
        return False


def _synthesize_pyttsx3(text: str, wav_path: str) -> bool:
    try:
        import subprocess
        
        result = subprocess.run(
            ["espeak", "-w", wav_path, text],
            capture_output=True,
            timeout=10
        )
        return result.returncode == 0

    except Exception as exc:
        print(f"[TTS] espeak synthesis error: {exc}")
        return False


def _read_wav_as_float32(wav_path: str) -> tuple[int, np.ndarray]:
    sample_rate, audio_data = wavfile.read(wav_path)

    if np.issubdtype(audio_data.dtype, np.integer):
        max_value = float(np.iinfo(audio_data.dtype).max)
        audio = audio_data.astype(np.float32) / max_value
    else:
        audio = audio_data.astype(np.float32)

    if audio.ndim > 1:
        audio = audio.mean(axis=1)

    audio = np.asarray(audio, dtype=np.float32).flatten()
    audio = np.clip(audio, -1.0, 1.0)

    return int(sample_rate), audio


def _resample_linear(audio: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
    if audio.size == 0 or source_rate == target_rate:
        return audio.astype(np.float32)

    output_length = int(round(audio.shape[0] * target_rate / float(source_rate)))

    if output_length <= 0:
        return np.array([], dtype=np.float32)

    old_indices = np.linspace(0.0, 1.0, num=audio.shape[0], endpoint=False)
    new_indices = np.linspace(0.0, 1.0, num=output_length, endpoint=False)

    return np.interp(new_indices, old_indices, audio).astype(np.float32)


def generate_speech(text: str, target_rate: Optional[int] = None) -> Optional[np.ndarray]:
    if not text or not text.strip():
        return None

    target_rate = int(target_rate or TTS_CONFIG["target_rate"])
    print(f"[TTS] Generating: {text!r}")

    tmp_path = None

    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        system = platform.system()

        if system == "Windows":
            success = _synthesize_windows(text, tmp_path)
        else:
            success = _synthesize_pyttsx3(text, tmp_path)

        if not success:
            print("[TTS] Synthesis failed")
            return None

        sample_rate, audio = _read_wav_as_float32(tmp_path)
        audio = _resample_linear(audio, sample_rate, target_rate)
        
        peak = np.max(np.abs(audio)) if audio.size > 0 else 1.0
        if peak > 0.0:
            audio = audio / peak * 0.95
        audio = np.clip(audio, -1.0, 1.0)

        if audio.size == 0:
            print("[TTS] Generated empty audio")
            return None

        print(f"[TTS] Generated {len(audio)} samples at {target_rate} Hz")
        return audio.astype(np.float32)

    except Exception as exc:
        print(f"[TTS] Error: {exc}")
        return None

    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def speak(text: str) -> Optional[np.ndarray]:
    return generate_speech(text)
