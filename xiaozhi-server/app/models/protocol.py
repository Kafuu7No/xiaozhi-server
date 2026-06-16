"""Protocol message models matching the device firmware's WebSocket protocol.

Reference: xiaozhi.cpp Message_handle() and ws_send_* functions.
"""

import asyncio
from dataclasses import dataclass, field
from enum import Enum
import uuid
import time


class DeviceState(str, Enum):
    """Maps to firmware's kDeviceState* constants."""
    UNKNOWN = "unknown"
    IDLE = "idle"
    LISTENING = "listening"
    SPEAKING = "speaking"


class ListeningMode(str, Enum):
    """Maps to firmware's ListeningMode enum."""
    AUTO_STOP = "auto_stop"
    MANUAL_STOP = "manual_stop"
    ALWAYS_ON = "always_on"


@dataclass
class DeviceSession:
    """Tracks one connected device's state.
    
    Each WebSocket connection gets a session. The session_id is sent
    in the hello response and used by the device in all subsequent messages.
    """
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    device_id: str = ""       # From header: Device-Id (MAC address)
    client_id: str = ""       # From header: Client-Id
    state: DeviceState = DeviceState.UNKNOWN
    connected_at: float = field(default_factory=time.time)
    
    # IoT state cache
    iot_descriptors: list = field(default_factory=list)
    iot_states: list = field(default_factory=list)

    # Opus audio frames accumulated during one utterance.
    audio_buffer: list = field(default_factory=list)
    listen_mode: str = ListeningMode.AUTO_STOP.value
    listen_started_at: float = 0.0
    last_voice_at: float = 0.0
    voice_frame_count: int = 0
    voice_turn_running: bool = False
    auto_stop_task: object | None = None
    voice_proxy: object | None = None
    device_send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
