from app.services.udp_hardware_bridge import (
    JPEG_EOI,
    JPEG_SOI,
    UdpPhotoAssembler,
    build_pump_start_packet,
)


def test_build_pump_start_packet_uses_little_endian_milliseconds():
    assert build_pump_start_packet(5) == bytes([0x10, 0x88, 0x13, 0x00, 0x00])


def test_build_pump_start_packet_clamps_to_firmware_limit():
    assert build_pump_start_packet(999) == bytes([0x10, 0xC0, 0x27, 0x09, 0x00])


def test_photo_assembler_returns_jpeg_after_eoi_marker():
    assembler = UdpPhotoAssembler(max_bytes=1024, idle_timeout=5)
    assert assembler.feed(b"noise") is None
    assert assembler.feed(JPEG_SOI + b"abc") is None
    assert assembler.feed(b"def" + JPEG_EOI + b"tail") == JPEG_SOI + b"abcdef" + JPEG_EOI


def test_photo_assembler_drops_oversized_buffer():
    assembler = UdpPhotoAssembler(max_bytes=4, idle_timeout=5)
    assert assembler.feed(JPEG_SOI + b"abc") is None
    assert assembler.buffer == bytearray()
