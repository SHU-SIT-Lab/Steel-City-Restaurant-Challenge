import os
import warnings
import numpy as np
import sounddevice as sd
import whisper
import torch

# Suppress CUDA initialization warnings
warnings.filterwarnings("ignore", category=UserWarning, module="torch.cuda")

# Ensure CUDA runtime is properly initialized
os.environ.setdefault("CUDA_LAUNCH_BLOCKING", "0")

from helpers import config

_model = None
_denoiser = None


def _load_model() -> whisper.Whisper:
    global _model

    if _model is None:
        device = "cuda"
        try:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            else:
                device = "cpu"
        except Exception:
            device = "cpu"
        
        _model = whisper.load_model(config.WHISPER_MODEL, device=device)

    return _model


def _load_denoiser():
    global _denoiser

    if _denoiser is None:
        print(f"[STT] Loading Hugging Face denoiser: {config.HF_DENOISE_MODEL}")

        try:
            from speechbrain.inference.enhancement import SpectralMaskEnhancement

            _denoiser = SpectralMaskEnhancement.from_hparams(
                source=config.HF_DENOISE_MODEL,
                savedir=config.HF_DENOISE_SAVEDIR,
                run_opts={"device": "cpu"},
            )

            print("[STT] Hugging Face denoiser ready.")

        except Exception as e:
            print(f"[STT] Could not load Hugging Face denoiser: {e}")
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

    audio = audio.astype(np.float32)
    audio = audio - np.mean(audio)

    peak = np.max(np.abs(audio))

    if peak < 1e-6:
        return audio.astype(np.float32)

    audio = audio / peak * 0.95

    return audio.astype(np.float32)


def _calibrate_noise(stream, chunk: int, sr: int) -> float:
    calibration_frames = int(config.NOISE_CALIBRATION_SECONDS * sr)

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
        config.MIN_SPEECH_THRESHOLD,
        noise_level * config.SPEECH_THRESHOLD_MULTIPLIER,
    )

    threshold = min(threshold, config.MAX_SPEECH_THRESHOLD)

    print(f"[STT] Room noise RMS: {noise_level:.5f}")
    print(f"[STT] Speech threshold: {threshold:.5f}")

    if noise_level > 0.01:
        print("[STT] Warning: calibration was noisy. Try staying quiet until calibration finishes.")

    return threshold


def _record_until_silence() -> np.ndarray:
    sr = config.SAMPLE_RATE
    silence_frames = int(config.SILENCE_DURATION * sr)
    max_record_frames = int(config.MAX_RECORD_SECONDS * sr)
    max_wait_frames = int(config.MAX_WAIT_FOR_SPEECH_SECONDS * sr)
    chunk = int(sr * 0.1)

    print("[STT] Listening... speak after calibration, pause to finish.")

    frames: list[np.ndarray] = []
    silent_count = 0
    started_speaking = False
    waited_frames = 0
    recorded_frames = 0

    with sd.InputStream(
        samplerate=sr,
        channels=config.CHANNELS,
        dtype="float32",
    ) as stream:

        speech_threshold = _calibrate_noise(stream, chunk, sr)

        while True:
            data, _ = stream.read(chunk)
            data = data.astype(np.float32)

            rms = _rms(data)
            waited_frames += chunk

            if rms > speech_threshold:
                started_speaking = True
                silent_count = 0
            else:
                if started_speaking:
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

    audio = np.concatenate(frames, axis=0).flatten()

    return audio.astype(np.float32)


def _denoise_with_huggingface(audio: np.ndarray) -> np.ndarray:
    if not config.ENABLE_DENOISING:
        return audio.astype(np.float32)

    denoiser = _load_denoiser()

    if denoiser is False:
        return audio.astype(np.float32)

    try:
        import torch

        audio = _normalize_audio(audio)

        wav = torch.tensor(audio, dtype=torch.float32).unsqueeze(0)
        lengths = torch.tensor([1.0], dtype=torch.float32)

        with torch.no_grad():
            enhanced = denoiser.enhance_batch(
                wav,
                lengths=lengths,
            )

        enhanced_audio = enhanced.squeeze().detach().cpu().numpy().astype(np.float32)
        enhanced_audio = _normalize_audio(enhanced_audio)

        print("[STT] Hugging Face denoising complete.")

        return enhanced_audio

    except Exception as e:
        print(f"[STT] Hugging Face denoising failed: {e}")
        print("[STT] Falling back to original audio.")

        return audio.astype(np.float32)


def transcribe_audio(audio: np.ndarray) -> str | None:
    min_samples = int(config.MIN_AUDIO_SECONDS * config.SAMPLE_RATE)

    if audio.size < min_samples:
        print("[STT] Audio too short, ignoring.")
        return None

    normalized_audio = _normalize_audio(audio)
    enhanced_audio = _denoise_with_huggingface(normalized_audio)

    try:
        model = _load_model()

        result = model.transcribe(
            enhanced_audio.astype(np.float32),
            language=config.WHISPER_LANGUAGE,
            fp16=False,
            condition_on_previous_text=False,
            no_speech_threshold=0.6,
        )

        text = result["text"].strip()

        print(f"[STT] Heard: {text!r}")

        return text if text else None

    except Exception as e:
        print(f"[STT] Error: {e}")
        return None


def listen() -> str | None:
    audio = _record_until_silence()
    return transcribe_audio(audio)