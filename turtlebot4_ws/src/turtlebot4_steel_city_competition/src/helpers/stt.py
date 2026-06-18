import os
import warnings
from typing import Optional

import numpy as np
import sounddevice as sd
import torch
import whisper

from helpers import config

warnings.filterwarnings("ignore", category=UserWarning, module="torch.cuda")
os.environ.setdefault("CUDA_LAUNCH_BLOCKING", "0")

_model = None
_denoiser = None
_model_device = "cpu"


def _config_value(name: str, default):
    return getattr(config, name, default)


def _load_model() -> whisper.Whisper:
    global _model, _model_device

    if _model is not None:
        return _model

    preferred_device = "cuda" if torch.cuda.is_available() else "cpu"

    try:
        if preferred_device == "cuda":
            torch.cuda.empty_cache()

        _model = whisper.load_model(
            _config_value("WHISPER_MODEL", "small"),
            device=preferred_device,
        )
        _model_device = preferred_device
        print(f"[STT] Whisper model ready on {_model_device}.")
        return _model

    except Exception as exc:
        print(f"[STT] Could not load Whisper on {preferred_device}: {exc}")
        print("[STT] Falling back to CPU.")
        _model = whisper.load_model(_config_value("WHISPER_MODEL", "small"), device="cpu")
        _model_device = "cpu"
        print("[STT] Whisper model ready on CPU.")
        return _model


def _load_denoiser():
    global _denoiser

    if _denoiser is not None:
        return _denoiser

    if not _config_value("ENABLE_DENOISING", False):
        _denoiser = False
        return _denoiser

    model_name = _config_value("HF_DENOISE_MODEL", "speechbrain/metricgan-plus-voicebank")
    savedir = _config_value("HF_DENOISE_SAVEDIR", "pretrained_models/metricgan-plus-voicebank")

    print(f"[STT] Loading Hugging Face denoiser: {model_name}")

    try:
        from speechbrain.inference.enhancement import SpectralMaskEnhancement

        _denoiser = SpectralMaskEnhancement.from_hparams(
            source=model_name,
            savedir=savedir,
            run_opts={"device": "cpu"},
        )
        print("[STT] Hugging Face denoiser ready.")

    except Exception as exc:
        print(f"[STT] Could not load Hugging Face denoiser: {exc}")
        print("[STT] Continuing without denoising.")
        _denoiser = False

    return _denoiser


def _rms(audio: np.ndarray) -> float:
    if audio.size == 0:
        return 0.0

    return float(np.sqrt(np.mean(audio.astype(np.float32) ** 2)))


def _normalize_audio(audio: np.ndarray) -> np.ndarray:
    if audio.size == 0:
        return audio.astype(np.float32)

    audio = audio.astype(np.float32).flatten()
    audio = audio - np.mean(audio)

    peak = np.max(np.abs(audio))

    if peak < 1e-6:
        return audio.astype(np.float32)

    return (audio / peak * 0.95).astype(np.float32)


def _denoise_with_huggingface(audio: np.ndarray) -> np.ndarray:
    if not _config_value("ENABLE_DENOISING", False):
        return audio.astype(np.float32)

    denoiser = _load_denoiser()

    if denoiser is False:
        return audio.astype(np.float32)

    try:
        audio = _normalize_audio(audio)
        wav = torch.tensor(audio, dtype=torch.float32).unsqueeze(0)
        lengths = torch.tensor([1.0], dtype=torch.float32)

        with torch.no_grad():
            enhanced = denoiser.enhance_batch(wav, lengths=lengths)

        enhanced_audio = enhanced.squeeze().detach().cpu().numpy().astype(np.float32)
        enhanced_audio = _normalize_audio(enhanced_audio)

        print("[STT] Hugging Face denoising complete.")
        return enhanced_audio

    except Exception as exc:
        print(f"[STT] Hugging Face denoising failed: {exc}")
        print("[STT] Falling back to original audio.")
        return audio.astype(np.float32)


def transcribe_audio(audio: np.ndarray) -> Optional[str]:
    if audio is None:
        return None

    audio = np.asarray(audio, dtype=np.float32).flatten()

    sample_rate = int(_config_value("SAMPLE_RATE", 16000))
    min_audio_seconds = float(_config_value("MIN_AUDIO_SECONDS", 0.4))
    min_samples = int(min_audio_seconds * sample_rate)

    if audio.size < min_samples:
        print("[STT] Audio too short, ignoring.")
        return None

    normalized_audio = _normalize_audio(audio)
    enhanced_audio = _denoise_with_huggingface(normalized_audio)

    try:
        model = _load_model()
        fp16 = bool(_model_device == "cuda")

        result = model.transcribe(
            enhanced_audio.astype(np.float32),
            language=_config_value("WHISPER_LANGUAGE", "en"),
            fp16=fp16,
            condition_on_previous_text=False,
            no_speech_threshold=0.6,
        )

        text = result.get("text", "").strip()
        print(f"[STT] Heard: {text!r}")
        return text if text else None

    except Exception as exc:
        print(f"[STT] Error: {exc}")
        return None


def _calibrate_noise(stream, chunk: int, sr: int) -> float:
    calibration_frames = int(_config_value("NOISE_CALIBRATION_SECONDS", 0.8) * sr)
    collected = []
    total = 0

    print("[STT] Calibrating room noise... please stay quiet briefly.")

    while total < calibration_frames:
        data, _ = stream.read(chunk)
        collected.append(data.copy())
        total += len(data)

    noise_audio = np.concatenate(collected, axis=0).flatten()
    noise_level = _rms(noise_audio)

    threshold = max(
        _config_value("MIN_SPEECH_THRESHOLD", 0.006),
        noise_level * _config_value("SPEECH_THRESHOLD_MULTIPLIER", 1.5),
    )
    threshold = min(threshold, _config_value("MAX_SPEECH_THRESHOLD", 0.025))

    print(f"[STT] Room noise RMS: {noise_level:.5f}")
    print(f"[STT] Speech threshold: {threshold:.5f}")

    if noise_level > 0.01:
        print("[STT] Warning: calibration was noisy. Try staying quiet until calibration finishes.")

    return threshold


def _record_until_silence() -> np.ndarray:
    sr = int(_config_value("SAMPLE_RATE", 16000))
    silence_frames = int(_config_value("SILENCE_DURATION", 1.4) * sr)
    max_record_frames = int(_config_value("MAX_RECORD_SECONDS", 15) * sr)
    max_wait_frames = int(_config_value("MAX_WAIT_FOR_SPEECH_SECONDS", 5) * sr)
    chunk = int(sr * 0.1)

    print("[STT] Listening... speak after calibration, pause to finish.")

    frames: list[np.ndarray] = []
    silent_count = 0
    started_speaking = False
    waited_frames = 0
    recorded_frames = 0

    with sd.InputStream(samplerate=sr, channels=_config_value("CHANNELS", 1), dtype="float32") as stream:
        speech_threshold = _calibrate_noise(stream, chunk, sr)

        while True:
            data, _ = stream.read(chunk)
            data = data.astype(np.float32)
            rms = _rms(data)
            waited_frames += chunk

            if rms > speech_threshold:
                started_speaking = True
                silent_count = 0
            elif started_speaking:
                silent_count += chunk

            if started_speaking:
                frames.append(data.copy())
                recorded_frames += chunk

            if not started_speaking and waited_frames >= max_wait_frames:
                print("[STT] No speech detected, timing out.")
                break

            if started_speaking and silent_count >= silence_frames:
                break

            if started_speaking and recorded_frames >= max_record_frames:
                break

    print("[STT] Recording done.")

    if not frames:
        return np.array([], dtype=np.float32)

    return np.concatenate(frames, axis=0).flatten().astype(np.float32)


def listen() -> Optional[str]:
    audio = _record_until_silence()
    return transcribe_audio(audio)
