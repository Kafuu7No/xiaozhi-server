# Verify FunASR loads the local model dir and transcribes the official sample.
import asyncio
import time

import av

from app.services.voice import audio_codec, stt

assert stt.local_model_available(), f"local model missing at {stt.LOCAL_MODEL_DIR}"

WAV = str(stt.LOCAL_MODEL_DIR / "example" / "asr_example.wav")


def wav_to_16k_mono_pcm(path: str) -> bytes:
    out = bytearray()
    with av.open(path) as container:
        resampler = av.AudioResampler(format="s16", layout="mono", rate=audio_codec.SAMPLE_RATE)
        for frame in container.decode(audio=0):
            for rs in resampler.resample(frame):
                out.extend(rs.to_ndarray().tobytes())
        for rs in resampler.resample(None):
            out.extend(rs.to_ndarray().tobytes())
    return bytes(out)


t0 = time.monotonic()
provider = stt.FunAsrStt()
print(f"model loaded in {time.monotonic() - t0:.1f}s")

pcm = wav_to_16k_mono_pcm(WAV)
t0 = time.monotonic()
text = asyncio.run(provider.transcribe(pcm))
print(f"transcribed in {time.monotonic() - t0:.1f}s")
print("STT RESULT:", repr(text))
assert text, "STT returned empty text"
print("LOCAL STT OK")
