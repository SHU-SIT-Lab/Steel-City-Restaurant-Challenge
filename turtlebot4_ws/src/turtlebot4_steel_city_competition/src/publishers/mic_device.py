#!/usr/bin/env python3
"""Shared PyAudio input device selection for mic_publisher and mic_test."""

from __future__ import annotations

import os
from typing import Optional

import numpy as np
import pyaudio

PROBE_FRAMES = 1024
PROBE_READS = 5


def forced_device_index() -> Optional[int]:
    """Return MIC_DEVICE_INDEX env override, if set."""
    raw = os.environ.get("MIC_DEVICE_INDEX")
    if raw is None:
        return None
    return int(raw)


def list_input_devices(p: pyaudio.PyAudio, min_channels: int = 1) -> list[dict]:
    """Return input devices with at least min_channels."""
    devices: list[dict] = []
    for idx in range(p.get_device_count()):
        info = p.get_device_info_by_index(idx)
        if int(info.get("maxInputChannels", 0)) >= min_channels:
            devices.append(info)
    return devices


def probe_device_energy(
    p: pyaudio.PyAudio,
    device_index: int,
    channels: int,
    sample_rate: int,
) -> float:
    """Read several frames and return total absolute sample energy."""
    total_energy = 0.0
    ps = p.open(
        format=pyaudio.paInt16,
        channels=channels,
        rate=sample_rate,
        input=True,
        frames_per_buffer=PROBE_FRAMES,
        input_device_index=device_index,
    )
    try:
        for _ in range(PROBE_READS):
            raw = ps.read(PROBE_FRAMES, exception_on_overflow=False)
            total_energy += float(
                np.sum(np.abs(np.frombuffer(raw, dtype="<i2").astype(np.float32)))
            )
    finally:
        ps.stop_stream()
        ps.close()
    return total_energy


def select_input_device(
    p: pyaudio.PyAudio,
    channels: int,
    log_fn=print,
) -> Optional[dict]:
    """
    Pick the best available input device.

    Priority:
      1. MIC_DEVICE_INDEX env var
      2. Highest energy across a short probe of each candidate
      3. OS default
    """
    forced_idx = forced_device_index()
    if forced_idx is not None:
        try:
            info = p.get_device_info_by_index(forced_idx)
            log_fn(
                f"[INFO] Using forced device [{forced_idx}] "
                f"'{info.get('name')}' (MIC_DEVICE_INDEX)"
            )
            return info
        except Exception as e:
            log_fn(f"[WARN] MIC_DEVICE_INDEX={forced_idx} invalid: {e}")

    default: Optional[dict] = None
    try:
        default = p.get_default_input_device_info()
    except Exception:
        pass

    candidates = list_input_devices(p, min_channels=channels)
    best_info: Optional[dict] = None
    best_energy = -1.0

    for info in candidates:
        dev_idx = int(info.get("index", -1))
        dev_rate = int(round(float(info.get("defaultSampleRate", 48000))))
        try:
            energy = probe_device_energy(p, dev_idx, channels, dev_rate)
        except Exception:
            continue

        log_fn(
            f"[DEBUG] Device [{dev_idx}] '{info.get('name')}' probe energy={energy:.0f}"
        )
        if energy > best_energy:
            best_energy = energy
            best_info = info

    if best_info is not None:
        dev_idx = best_info.get("index")
        log_fn(
            f"[INFO] Selected input device [{dev_idx}] '{best_info.get('name')}' "
            f"(probe energy={best_energy:.0f}; set MIC_DEVICE_INDEX={dev_idx} to pin this)"
        )
        return best_info

    if default is not None:
        log_fn(
            f"[WARN] Probe found no candidate devices. Using OS default "
            f"[{default.get('index')}] '{default.get('name')}'. "
            "Set MIC_DEVICE_INDEX to override."
        )
        return default

    return None


def open_input_stream_with_device_rate(
    p: pyaudio.PyAudio,
    device_info: Optional[dict],
    channels: int,
    chunk_size: int,
) -> tuple[pyaudio.Stream, int]:
    """Open an input stream, probing sample rates until one works."""
    device_index = None if device_info is None else int(device_info.get("index", -1))

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
            if device_index is not None and device_index >= 0:
                open_kwargs["input_device_index"] = device_index

            stream = p.open(**open_kwargs)
            return stream, rate
        except Exception as e:
            last_error = e

    raise RuntimeError(
        f"Could not open microphone at any tested sample rate. Last error: {last_error}"
    )
