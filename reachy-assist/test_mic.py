"""Quick mic level test — speak and see what RMS values your mic produces."""
import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
CHUNK = 0.1  # 100ms chunks

print("=== Mic Level Test ===")
print("Speak into your mic. Press Ctrl+C to stop.\n")
print(f"{'RMS':>8}  {'Bar'}")
print("-" * 50)

try:
    while True:
        chunk = sd.rec(int(SAMPLE_RATE * CHUNK), samplerate=SAMPLE_RATE,
                       channels=1, dtype="float32")
        sd.wait()
        rms = float(np.sqrt(np.mean(chunk ** 2)))
        bar = "█" * int(rms * 500)
        print(f"{rms:8.5f}  {bar}")
except KeyboardInterrupt:
    print("\nDone!")
