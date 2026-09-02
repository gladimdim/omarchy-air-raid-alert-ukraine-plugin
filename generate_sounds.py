#!/usr/bin/env python3
"""Generate audio alerts for air raid siren and all-clear chime."""
import math
import struct
import wave
from pathlib import Path

def generate_siren_wav(path: Path):
    """Two-tone attention siren (880 Hz / 660 Hz alternating pulse, ~2.4s)."""
    sample_rate = 44100
    duration = 2.4
    num_samples = int(sample_rate * duration)

    with wave.open(str(path), "w") as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)

        data = bytearray()
        for i in range(num_samples):
            t = i / sample_rate
            # Cycle every 0.4s between 880 Hz and 660 Hz with frequency modulation
            cycle = (t % 0.4) / 0.4
            freq = 660.0 + 220.0 * math.sin(cycle * math.pi)

            # Amplitude envelope with slight decay at end of 2.4s
            fade = 1.0 if t < 2.0 else max(0.0, (2.4 - t) / 0.4)
            sample = 0.8 * fade * math.sin(2.0 * math.pi * freq * t)
            # Add secondary harmonic for punchy urgency
            sample += 0.2 * fade * math.sin(4.0 * math.pi * freq * t)

            int_sample = int(max(-32767, min(32767, sample * 32767)))
            data.extend(struct.pack("<h", int_sample))

        wav_file.writeframes(data)

def generate_clear_wav(path: Path):
    """Gentle ascending harmonic chime for all-clear (C-E-G major chord, ~1.8s)."""
    sample_rate = 44100
    duration = 1.8
    num_samples = int(sample_rate * duration)

    notes = [
        (0.0, 0.6, 523.25),  # C5
        (0.3, 0.9, 659.25),  # E5
        (0.6, 1.8, 783.99),  # G5
    ]

    with wave.open(str(path), "w") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)

        data = bytearray()
        for i in range(num_samples):
            t = i / sample_rate
            sample = 0.0

            for start, end, freq in notes:
                if start <= t < end:
                    note_t = t - start
                    # Attack & exponential decay envelope
                    envelope = math.exp(-3.5 * note_t) * min(1.0, note_t * 100)
                    sample += 0.45 * envelope * math.sin(2.0 * math.pi * freq * note_t)
                    # Gentle overtone
                    sample += 0.15 * envelope * math.sin(4.0 * math.pi * freq * note_t)

            int_sample = int(max(-32767, min(32767, sample * 32767)))
            data.extend(struct.pack("<h", int_sample))

        wav_file.writeframes(data)

if __name__ == "__main__":
    assets_dir = Path(__file__).resolve().parent / "assets"
    assets_dir.mkdir(exist_ok=True)
    generate_siren_wav(assets_dir / "siren.wav")
    generate_clear_wav(assets_dir / "clear.wav")
    print("Generated siren.wav and clear.wav successfully.")
