"""Audio feedback sounds for Baba voice assistant."""

import numpy as np
import sounddevice as sd


def beep(frequency: int = 800, duration: float = 0.15, volume: float = 0.3):
    """Play a short beep sound to indicate recording start."""
    sr = 24000
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    # Sine wave with fade in/out to avoid clicks
    wave = np.sin(2 * np.pi * frequency * t) * volume
    fade = int(sr * 0.02)
    wave[:fade] *= np.linspace(0, 1, fade)
    wave[-fade:] *= np.linspace(1, 0, fade)
    sd.play(wave.astype(np.float32), samplerate=sr)
    sd.wait()


def soft_beep(frequency: int = 600, duration: float = 0.08, volume: float = 0.15):
    """Play a soft short beep — ready for next command in session."""
    sr = 24000
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    wave = np.sin(2 * np.pi * frequency * t) * volume
    fade = int(sr * 0.01)
    wave[:fade] *= np.linspace(0, 1, fade)
    wave[-fade:] *= np.linspace(1, 0, fade)
    sd.play(wave.astype(np.float32), samplerate=sr)
    sd.wait()


def descending_beep(volume: float = 0.2):
    """Play a descending tone — session ended."""
    sr = 24000
    duration = 0.3
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    freq = np.linspace(800, 400, len(t))
    wave = np.sin(2 * np.pi * freq * t / sr * sr) * volume
    # Simpler: just sweep
    phase = np.cumsum(2 * np.pi * freq / sr)
    wave = np.sin(phase) * volume
    fade = int(sr * 0.02)
    wave[:fade] *= np.linspace(0, 1, fade)
    wave[-fade:] *= np.linspace(1, 0, fade)
    sd.play(wave.astype(np.float32), samplerate=sr)
    sd.wait()


def double_beep(frequency: int = 600, duration: float = 0.1, volume: float = 0.25):
    """Play a double beep to indicate recording stop."""
    sr = 24000
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    wave = np.sin(2 * np.pi * frequency * t) * volume
    fade = int(sr * 0.015)
    wave[:fade] *= np.linspace(0, 1, fade)
    wave[-fade:] *= np.linspace(1, 0, fade)
    gap = np.zeros(int(sr * 0.06), dtype=np.float32)
    full = np.concatenate([wave, gap, wave]).astype(np.float32)
    sd.play(full, samplerate=sr)
    sd.wait()
