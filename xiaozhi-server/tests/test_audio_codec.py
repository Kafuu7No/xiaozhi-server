import io
import math
import struct

import av

from app.services.voice import audio_codec


def make_sine_pcm(seconds=1.0, rate=16000, freq=440):
    n = int(seconds * rate)
    return b"".join(
        struct.pack("<h", int(0.3 * 32767 * math.sin(2 * math.pi * freq * i / rate)))
        for i in range(n)
    )


def make_stereo_sine_pcm(seconds=1.0, rate=16000):
    n = int(seconds * rate)
    samples = []
    for i in range(n):
        left = int(0.3 * 32767 * math.sin(2 * math.pi * 440 * i / rate))
        right = int(0.3 * 32767 * math.sin(2 * math.pi * 660 * i / rate))
        samples.append(struct.pack("<hh", left, right))
    return b"".join(samples)


def encode_stereo_pcm_to_opus(pcm: bytes, rate=16000) -> list[bytes]:
    codec = av.CodecContext.create("libopus", "w")
    codec.sample_rate = rate
    codec.layout = "stereo"
    codec.format = "s16"

    frames = []
    samples_per_frame = rate * audio_codec.FRAME_MS // 1000
    bytes_per_frame = samples_per_frame * 2 * 2
    for offset in range(0, len(pcm), bytes_per_frame):
        chunk = pcm[offset : offset + bytes_per_frame]
        if len(chunk) < bytes_per_frame:
            chunk = chunk + b"\x00" * (bytes_per_frame - len(chunk))
        frame = av.AudioFrame(format="s16", layout="stereo", samples=samples_per_frame)
        frame.sample_rate = rate
        frame.planes[0].update(chunk)
        for packet in codec.encode(frame):
            frames.append(bytes(packet))
    for packet in codec.encode(None):
        frames.append(bytes(packet))
    return frames


def pcm_to_mp3(pcm: bytes, rate=16000) -> bytes:
    """Encode test PCM into MP3 via PyAV."""
    buf = io.BytesIO()
    with av.open(buf, mode="w", format="mp3") as container:
        stream = container.add_stream("mp3", rate=rate)
        frame = av.AudioFrame(format="s16", layout="mono", samples=len(pcm) // 2)
        frame.sample_rate = rate
        frame.planes[0].update(pcm)
        for packet in stream.encode(frame):
            container.mux(packet)
        for packet in stream.encode(None):
            container.mux(packet)
    return buf.getvalue()


def test_opus_round_trip_preserves_audio():
    pcm = make_sine_pcm(seconds=1.0)
    frames = audio_codec.encode_pcm_to_opus(pcm, sample_rate=16000)
    assert len(frames) > 0
    decoded = audio_codec.decode_opus_frames(frames)
    assert abs(len(decoded) - len(pcm)) < 16000 * 2 * 0.2
    assert any(byte != 0 for byte in decoded)


def test_device_tts_opus_defaults_to_24khz_and_decodes_for_stt():
    pcm = make_sine_pcm(seconds=1.0, rate=24000)
    frames = audio_codec.encode_pcm_to_opus(pcm)
    assert len(frames) > 0
    decoded = audio_codec.decode_opus_frames(frames)
    assert abs(len(decoded) - 16000 * 2) < 16000 * 2 * 0.2
    assert any(byte != 0 for byte in decoded)


def test_board_stereo_opus_decodes_to_stt_mono_pcm():
    pcm = make_stereo_sine_pcm(seconds=1.0, rate=16000)
    frames = encode_stereo_pcm_to_opus(pcm, rate=16000)
    assert len(frames) > 0
    decoded = audio_codec.decode_opus_frames(frames)
    assert abs(len(decoded) - 16000 * 2) < 16000 * 2 * 0.2
    assert any(byte != 0 for byte in decoded)


def test_decode_mp3_to_pcm():
    pcm = make_sine_pcm(seconds=1.0)
    mp3 = pcm_to_mp3(pcm)
    decoded = audio_codec.decode_mp3_to_pcm(mp3)
    assert len(decoded) > 16000
    assert any(byte != 0 for byte in decoded)
