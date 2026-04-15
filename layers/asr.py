"""Layer 2: Automatic Speech Recognition using faster-whisper + Silero VAD.

After wake word detection, captures audio from the microphone,
uses Voice Activity Detection to determine when the user stops speaking,
then transcribes the captured audio.

Uses callback-based audio capture to prevent buffer overflow.
"""

import queue
import time
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
from silero_vad import load_silero_vad, get_speech_timestamps

from utils.logger import setup_logger
from utils.audio import get_device_sample_rate, resample_audio, TARGET_SAMPLE_RATE

logger = setup_logger("baba.asr")


class ASREngine:
    """Speech-to-text using faster-whisper with Silero VAD for end-of-speech detection."""

    def __init__(
        self,
        model_name: str = "base.en",
        silence_threshold_seconds: float = 1.5,
        max_recording_seconds: float = 30.0,
    ):
        self.model_name = model_name
        self.silence_threshold = silence_threshold_seconds
        self.max_recording = max_recording_seconds
        self._whisper_model = None
        self._vad_model = None

    def _load_models(self):
        """Lazy-load whisper and VAD models."""
        if self._whisper_model is None:
            logger.info(f"Loading faster-whisper model: {self.model_name}")
            start = time.time()
            self._whisper_model = WhisperModel(
                self.model_name,
                device="cpu",
                compute_type="int8",
            )
            logger.info(f"Whisper model loaded in {time.time() - start:.1f}s")

        if self._vad_model is None:
            logger.info("Loading Silero VAD model")
            self._vad_model = load_silero_vad()
            logger.info("VAD model loaded")

    def _has_speech(self, audio_16k: np.ndarray) -> bool:
        """Check if an audio chunk contains speech using Silero VAD."""
        import torch
        tensor = torch.from_numpy(audio_16k).float()
        timestamps = get_speech_timestamps(tensor, self._vad_model, sampling_rate=TARGET_SAMPLE_RATE)
        return len(timestamps) > 0

    def record_and_transcribe(self) -> dict:
        """Record audio until silence is detected, then transcribe.

        Uses a callback-based audio stream so capture never drops frames,
        even if VAD processing is slower than real-time.

        Returns:
            dict with transcription result:
            {
                "event": "transcription_complete",
                "text": str,
                "duration_seconds": float,
            }
        """
        self._load_models()

        device_sr = get_device_sample_rate()
        chunk_duration = 0.3  # 300ms chunks for faster VAD response
        device_chunk_frames = int(device_sr * chunk_duration)

        # Audio flows: callback → queue → main thread (no polling, no overflow)
        audio_queue = queue.Queue()

        def _audio_callback(indata, frames, time_info, status):
            if status:
                logger.warning(f"Audio callback status: {status}")
            audio_queue.put(indata.copy())

        collected_audio = []
        silence_start = None
        recording_start = time.time()
        speech_detected = False

        logger.info("Recording... (speak now)")

        stream = sd.InputStream(
            samplerate=device_sr,
            channels=1,
            dtype="float32",
            blocksize=device_chunk_frames,
            callback=_audio_callback,
        )
        stream.start()

        try:
            while True:
                elapsed = time.time() - recording_start

                if elapsed > self.max_recording:
                    logger.warning(f"Max recording duration ({self.max_recording}s) reached")
                    break

                # Block until a chunk is available (timeout to allow checking elapsed)
                try:
                    data = audio_queue.get(timeout=1.0)
                except queue.Empty:
                    continue

                mono = data[:, 0] if data.ndim > 1 else data.flatten()
                chunk_16k = resample_audio(mono, device_sr)

                collected_audio.append(chunk_16k)

                # Check for speech
                has_speech = self._has_speech(chunk_16k)

                if has_speech:
                    speech_detected = True
                    silence_start = None
                else:
                    if speech_detected and silence_start is None:
                        silence_start = time.time()
                    elif speech_detected and silence_start is not None:
                        silence_duration = time.time() - silence_start
                        # Adaptive threshold: longer utterances get more pause tolerance
                        # Short commands (< 3s): use base threshold (1.0s)
                        # Longer speech (> 3s): extend to 1.8s to avoid cutting mid-thought
                        speech_duration = time.time() - recording_start
                        adaptive_threshold = self.silence_threshold
                        if speech_duration > 3.0:
                            adaptive_threshold = min(self.silence_threshold + 0.8, 2.0)
                        if silence_duration >= adaptive_threshold:
                            logger.info(f"End of speech detected ({silence_duration:.1f}s silence, threshold={adaptive_threshold:.1f}s)")
                            break

                # If no speech detected in first 5 seconds, bail
                if not speech_detected and elapsed > 5.0:
                    logger.info("No speech detected in 5 seconds, aborting")
                    return {
                        "event": "transcription_complete",
                        "text": "",
                        "duration_seconds": elapsed,
                    }

        finally:
            stream.stop()
            stream.close()

        if not collected_audio:
            return {
                "event": "transcription_complete",
                "text": "",
                "duration_seconds": 0,
            }

        # Concatenate all audio
        full_audio = np.concatenate(collected_audio)
        duration = len(full_audio) / TARGET_SAMPLE_RATE
        logger.info(f"Captured {duration:.1f}s of audio, transcribing...")

        # Transcribe
        start = time.time()
        segments, info = self._whisper_model.transcribe(
            full_audio,
            beam_size=1,
            language="en",
            vad_filter=True,
        )

        text_parts = []
        for segment in segments:
            text_parts.append(segment.text.strip())

        text = " ".join(text_parts).strip()
        transcribe_time = time.time() - start

        # Clean filler words
        text = self._clean_fillers(text)

        logger.info(f"Transcription ({transcribe_time:.2f}s): '{text}'")

        return {
            "event": "transcription_complete",
            "text": text,
            "duration_seconds": duration,
        }

    @staticmethod
    def _clean_fillers(text: str) -> str:
        """Remove common filler words from transcription."""
        fillers = ["um", "uh", "like", "you know", "so", "well", "hmm", "ah"]
        words = text.split()
        cleaned = []
        for word in words:
            if word.lower().strip(",.!?") not in fillers:
                cleaned.append(word)
        return " ".join(cleaned)
