"""Audio codecs: Opus frames <-> PCM, MP3 -> PCM. Built on PyAV.

STT PCM is 16kHz mono 16-bit little-endian. Device TTS Opus is 24kHz mono,
matching the reference board firmware's downlink decoder.
"""

from __future__ import annotations

import io
import logging

import av

logger = logging.getLogger("xz.voice.codec")

SAMPLE_RATE = 16000
DEVICE_TTS_SAMPLE_RATE = 24000
FRAME_MS = 60
OPUS_BITRATE = 24000
SAMPLES_PER_FRAME = SAMPLE_RATE * FRAME_MS // 1000


def decode_opus_frames(frames: list[bytes]) -> bytes:
    """Decode device Opus packets into 16kHz mono 16-bit PCM."""
    codec = av.CodecContext.create("libopus", "r")
    codec.sample_rate = SAMPLE_RATE
    resampler = av.AudioResampler(format="s16", layout="mono", rate=SAMPLE_RATE)
    out = bytearray()
    for raw in frames:
        try:
            for frame in codec.decode(av.Packet(raw)):
                for resampled in resampler.resample(frame):
                    out.extend(resampled.to_ndarray().tobytes())
        except Exception as exc:
            logger.error("Opus decode failed; dropping frame: %s", exc)
    return bytes(out)


def encode_pcm_to_opus(pcm: bytes, *, sample_rate: int = DEVICE_TTS_SAMPLE_RATE) -> list[bytes]:
    """Encode mono 16-bit PCM into 60ms Opus packets for the device."""
    codec = av.CodecContext.create("libopus", "w")
    codec.sample_rate = sample_rate
    codec.layout = "mono"
    codec.format = "s16"
    codec.bit_rate = OPUS_BITRATE
    codec.options = {"frame_duration": str(FRAME_MS)}

    frames: list[bytes] = []
    samples_per_frame = sample_rate * FRAME_MS // 1000
    bytes_per_frame = samples_per_frame * 2
    for offset in range(0, len(pcm), bytes_per_frame):
        chunk = pcm[offset : offset + bytes_per_frame]
        if len(chunk) < bytes_per_frame:
            chunk = chunk + b"\x00" * (bytes_per_frame - len(chunk))
        frame = av.AudioFrame(format="s16", layout="mono", samples=samples_per_frame)
        frame.sample_rate = sample_rate
        frame.planes[0].update(chunk)
        for packet in codec.encode(frame):
            frames.append(bytes(packet))
    for packet in codec.encode(None):
        frames.append(bytes(packet))
    return frames


def decode_mp3_to_pcm(mp3: bytes, *, sample_rate: int = DEVICE_TTS_SAMPLE_RATE) -> bytes:
    """Decode MP3 bytes into mono 16-bit PCM."""
    out = bytearray()
    with av.open(io.BytesIO(mp3)) as container:
        resampler = av.AudioResampler(format="s16", layout="mono", rate=sample_rate)
        for frame in container.decode(audio=0):
            for resampled in resampler.resample(frame):
                out.extend(resampled.to_ndarray().tobytes())
        for resampled in resampler.resample(None):
            out.extend(resampled.to_ndarray().tobytes())
    return bytes(out)
