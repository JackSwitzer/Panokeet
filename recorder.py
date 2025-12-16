"""Audio recording module using sounddevice."""

import tempfile
import wave
from pathlib import Path
from threading import Thread, Event
import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
CHANNELS = 1


class Recorder:
    def __init__(self, on_level_change=None):
        self.recording = False
        self.audio_data = []
        self.stream = None
        self.current_level = 0.0
        self.on_level_change = on_level_change  # Callback for UI updates

    def start(self):
        """Start recording audio."""
        self.audio_data = []
        self.recording = True
        self.current_level = 0.0
        self.stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=np.float32,
            callback=self._callback
        )
        self.stream.start()

    def _callback(self, indata, frames, time, status):
        """Audio input callback - runs on audio thread."""
        if self.recording:
            self.audio_data.append(indata.copy())
            # Calculate audio level for visualization
            self.current_level = min(1.0, np.abs(indata).max() * 3)
            if self.on_level_change:
                self.on_level_change(self.current_level)

    def stop(self):
        """Stop recording and return (audio_path, duration) or None."""
        self.recording = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

        if not self.audio_data:
            return None

        # Combine all audio chunks
        audio = np.concatenate(self.audio_data, axis=0)
        duration = len(audio) / SAMPLE_RATE

        # Save to temp WAV file (16-bit PCM for whisper)
        temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        audio_int16 = (audio * 32767).astype(np.int16)

        with wave.open(temp_file.name, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio_int16.tobytes())

        return Path(temp_file.name), duration

    @property
    def is_recording(self):
        return self.recording
