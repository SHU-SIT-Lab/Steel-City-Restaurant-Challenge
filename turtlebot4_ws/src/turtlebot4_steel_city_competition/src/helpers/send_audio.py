#!/usr/bin/env python3

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np


@dataclass
class AudioFrames:
    """Container for different audio processing variants."""
    original: Optional[np.ndarray]
    upsampled: Optional[np.ndarray]
    downsampled: Optional[np.ndarray]
    resampled: Optional[np.ndarray]


# Global settings for audio processing during transmission.
AUDIO_SEND_CONFIG = {
    "upsample_factor": 1.5,  # Upsample by 1.5x (16kHz -> 24kHz)
    "downsample_factor": 0.5,  # Downsample by 0.5x (16kHz -> 8kHz)
    "target_sample_rate": 16000,  # Standard rate for transmission
}


def upsample_audio(audio: np.ndarray, factor: float = 1.5) -> np.ndarray:
    """
    Upsample audio by linear interpolation.

    Args:
        audio: Input audio array (float32).
        factor: Upsample factor (e.g., 1.5 = 50% increase).

    Returns:
        Upsampled audio array.
    """
    if factor == 1.0:
        return audio
    original_length = len(audio)
    new_length = int(original_length * factor)
    old_indices = np.linspace(0, original_length - 1, original_length)
    new_indices = np.linspace(0, original_length - 1, new_length)
    upsampled = np.interp(new_indices, old_indices, audio)
    return upsampled.astype(np.float32)


def downsample_audio(audio: np.ndarray, factor: float = 0.5) -> np.ndarray:
    """
    Downsample audio by linear interpolation.

    Args:
        audio: Input audio array (float32).
        factor: Downsample factor (e.g., 0.5 = 50% reduction).

    Returns:
        Downsampled audio array.
    """
    if factor == 1.0:
        return audio
    original_length = len(audio)
    new_length = int(original_length * factor)
    if new_length < 1:
        new_length = 1
    old_indices = np.linspace(0, original_length - 1, original_length)
    new_indices = np.linspace(0, original_length - 1, new_length)
    downsampled = np.interp(new_indices, old_indices, audio)
    return downsampled.astype(np.float32)


def normalize_audio(audio: np.ndarray) -> np.ndarray:
    """
    Normalize audio to [-1, 1] range by peak normalization.

    Args:
        audio: Input audio array (float32).

    Returns:
        Normalized audio array.
    """
    if len(audio) == 0:
        return audio
    peak = np.max(np.abs(audio))
    if peak > 0:
        audio = audio / peak
    return audio.astype(np.float32)


def process_audio_for_transmission(audio: np.ndarray) -> AudioFrames:
    """
    Process audio for transmission with multiple variants.

    Args:
        audio: Input audio array (float32, normalized to [-1, 1]).

    Returns:
        AudioFrames dataclass with original, upsampled, downsampled, resampled variants.
    """
    original = audio.copy()

    # Upsample variant
    upsampled = upsample_audio(original, AUDIO_SEND_CONFIG["upsample_factor"])
    upsampled = normalize_audio(upsampled)

    # Downsample variant
    downsampled = downsample_audio(original, AUDIO_SEND_CONFIG["downsample_factor"])
    downsampled = normalize_audio(downsampled)

    # Resampled (same as original for transmission)
    resampled = original.copy()

    return AudioFrames(
        original=original,
        upsampled=upsampled,
        downsampled=downsampled,
        resampled=resampled,
    )
