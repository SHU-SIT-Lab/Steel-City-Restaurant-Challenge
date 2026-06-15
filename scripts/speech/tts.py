"""Text-to-speech using Windows SAPI directly (offline, no pyttsx3 deadlock)."""

import tempfile
import os
import numpy as np
import sounddevice as sd
import scipy.io.wavfile as wav
import win32com.client
import pythoncom
import config

_output_device: int | None = None


def _find_realtek_device() -> int | None:
    for i, d in enumerate(sd.query_devices()):
        if d["max_output_channels"] > 0 and "realtek" in d["name"].lower() and "speakers" in d["name"].lower():
            return i
    return None


def _synthesize(text: str, wav_path: str) -> None:
    """Use Windows SAPI to write speech to a WAV file."""
    pythoncom.CoInitialize()
    try:
        sapi = win32com.client.Dispatch("SAPI.SpVoice")
        stream = win32com.client.Dispatch("SAPI.SpFileStream")
        stream.Open(wav_path, 3)          # 3 = SSFMCreateForWrite
        sapi.AudioOutputStream = stream
        sapi.Rate = 1                     # -10 (slow) to 10 (fast), 0 = normal
        sapi.Volume = 100
        sapi.Speak(text)
        stream.Close()
    finally:
        pythoncom.CoUninitialize()


def speak(text: str) -> None:
    """Synthesize text and play through Realtek speakers."""
    global _output_device
    print(f"[TTS] Speaking: {text!r}")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        _synthesize(text, tmp_path)

        rate, data = wav.read(tmp_path)
        audio = data.astype(np.float32) / 32768.0
        if audio.ndim > 1:
            audio = audio.mean(axis=1)

        if _output_device is None:
            _output_device = _find_realtek_device()
            if _output_device is not None:
                print(f"[TTS] Using device: {sd.query_devices(_output_device)['name']}")

        sd.play(audio, samplerate=rate, device=_output_device, blocking=True)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
