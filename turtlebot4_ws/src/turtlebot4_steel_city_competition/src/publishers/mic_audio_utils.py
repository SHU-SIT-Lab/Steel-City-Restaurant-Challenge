#!/usr/bin/env python3

from typing import Optional

import numpy as np
import pyaudio


def get_best_input_device(
    p: pyaudio.PyAudio,
    channels: int,
    device_index: Optional[int] = None,
) -> Optional[dict]:
    """Return the most likely real microphone input device.

    Priority order:
      1. Explicit device_index override.
      2. Energy probe across all input devices.
      3. OS default as a fallback.
    """
    if device_index is not None:
        try:
            return p.get_device_info_by_index(int(device_index))
        except Exception:
            pass

    default: Optional[dict] = None
    try:
        default = p.get_default_input_device_info()
    except Exception:
        pass

    candidates: list[dict] = []
    try:
        for idx in range(p.get_device_count()):
            info = p.get_device_info_by_index(idx)
            if int(info.get("maxInputChannels", 0)) >= channels:
                candidates.append(info)
    except Exception:
        candidates = []

    probe_frames = 1024
    probe_reads = 5
    best_info: Optional[dict] = None
    best_energy = -1.0

    for info in candidates:
        dev_idx = int(info.get("index", -1))
        dev_rate = int(round(float(info.get("defaultSampleRate", 48000))))
        total_energy = 0.0
        try:
            stream = p.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=dev_rate,
                input=True,
                frames_per_buffer=probe_frames,
                input_device_index=dev_idx if dev_idx >= 0 else None,
            )
            for _ in range(probe_reads):
                raw = stream.read(probe_frames, exception_on_overflow=False)
                total_energy += float(np.sum(np.abs(np.frombuffer(raw, dtype="<i2").astype(np.float32))))
            stream.stop_stream()
            stream.close()
        except Exception:
            continue

        if total_energy > best_energy:
            best_energy = total_energy
            best_info = info

    if best_info is not None:
        return best_info

    return default


def open_input_stream_with_device_rate(
    p: pyaudio.PyAudio,
    channels: int,
    chunk_size: int,
    device_index: Optional[int] = None,
) -> tuple[pyaudio.Stream, int, Optional[dict]]:
    """Open audio input at a working sample rate on the best available device."""
    device_info = get_best_input_device(p, channels, device_index=device_index)
    selected_device_index = None if device_info is None else int(device_info.get("index", -1))

    candidate_rates: list[int] = []
    if device_info is not None:
        default_rate = int(round(float(device_info.get("defaultSampleRate", 0.0))))
        if default_rate > 0:
            candidate_rates.append(default_rate)

    candidate_rates.extend([48000, 44100, 32000, 24000, 22050, 16000, 11025, 8000])

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
                "channels": channels,
                "rate": rate,
                "input": True,
                "frames_per_buffer": chunk_size,
            }
            if selected_device_index is not None and selected_device_index >= 0:
                open_kwargs["input_device_index"] = selected_device_index

            stream = p.open(**open_kwargs)
            return stream, rate, device_info
        except Exception as e:
            last_error = e

    raise RuntimeError(f"Could not open microphone at any tested sample rate. Last error: {last_error}")