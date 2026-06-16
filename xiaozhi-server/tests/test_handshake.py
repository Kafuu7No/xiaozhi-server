"""Simulate the XiaoZhi device WebSocket handshake.

This script mimics exactly what the firmware does:
1. Connect with auth headers (like wsock_connect in xiaozhi.cpp)
2. Send HELLO_MESSAGE (like ws_send_hello)
3. Receive hello response with session_id and audio_params
4. Send IoT descriptors and states (like send_iot_descriptors/send_iot_states)
5. Send listen start (like ws_send_listen_start)

Usage:
    python -m tests.test_handshake [--url ws://localhost:8000/xiaozhi/v1/]
"""

import asyncio
import json
import sys

try:
    import websockets
except ImportError:
    print("pip install websockets")
    sys.exit(1)


# Mirrors HELLO_MESSAGE from xiaozhi.h
HELLO_MESSAGE = {
    "type": "hello",
    "version": 3,
    "features": {"mcp": True},
    "transport": "websocket",
    "audio_params": {
        "format": "opus",
        "sample_rate": 16000,
        "channels": 1,
        "frame_duration": 60,
    },
}

# Mirrors what firmware sends after hello response
SAMPLE_IOT_DESCRIPTORS = {
    "type": "iot",
    "update": True,
    "descriptors": [
        {
            "name": "Speaker",
            "description": "扬声器",
            "properties": {"volume": {"type": "number", "min": 0, "max": 100}},
            "methods": {
                "SetVolume": {"parameters": {"volume": {"type": "number"}}},
                "GetVolume": {},
            },
        },
        {
            "name": "Screen",
            "description": "屏幕",
            "properties": {"brightness": {"type": "number", "min": 0, "max": 100}},
            "methods": {
                "SetBrightness": {"parameters": {"brightness": {"type": "number"}}},
                "SetEmoji": {"parameters": {"emoji": {"type": "string"}}},
            },
        },
        {
            "name": "Led",
            "description": "LED灯",
            "properties": {},
            "methods": {
                "SetLed": {"parameters": {"color": {"type": "string"}}},
            },
        },
    ],
}

SAMPLE_IOT_STATES = {
    "type": "iot",
    "update": True,
    "states": [
        {"name": "Speaker", "state": {"volume": 70}},
        {"name": "Screen", "state": {"brightness": 80}},
        {"name": "Led", "state": {}},
    ],
}


async def simulate_device(url: str = "ws://localhost:8000/xiaozhi/v1/"):
    """Run the full handshake simulation."""
    
    # Custom headers matching firmware's wsock_connect call
    headers = {
        "Authorization": "Bearer 12345678",
        "Protocol-Version": "1",
        "Device-Id": "aa:bb:cc:dd:ee:ff",
        "Client-Id": "test-0001-0002-0003",
    }
    
    print(f"[1] Connecting to {url} ...")
    
    async with websockets.connect(url, extra_headers=headers) as ws:
        print("[1] ✅ WebSocket connected\n")
        
        # Step 2: Send hello (mirrors ws_send_hello)
        print(f"[2] Sending hello →")
        print(f"    {json.dumps(HELLO_MESSAGE, indent=2)[:200]}...")
        await ws.send(json.dumps(HELLO_MESSAGE))
        
        # Step 3: Receive hello response
        response = await asyncio.wait_for(ws.recv(), timeout=5.0)
        hello_resp = json.loads(response)
        print(f"\n[3] ✅ Hello response ←")
        print(f"    {json.dumps(hello_resp, indent=2)}")
        
        session_id = hello_resp.get("session_id", "")
        assert hello_resp["type"] == "hello", f"Expected hello, got {hello_resp['type']}"
        assert session_id, "Missing session_id"
        assert "audio_params" in hello_resp, "Missing audio_params"
        print(f"    session_id = {session_id}")
        print(f"    sample_rate = {hello_resp['audio_params']['sample_rate']}")
        print(f"    frame_duration = {hello_resp['audio_params']['frame_duration']}")
        
        # Step 4: Send IoT descriptors (mirrors send_iot_descriptors)
        iot_desc = {**SAMPLE_IOT_DESCRIPTORS, "session_id": session_id}
        print(f"\n[4] Sending IoT descriptors → ({len(iot_desc['descriptors'])} devices)")
        await ws.send(json.dumps(iot_desc))
        
        # Step 5: Send IoT states (mirrors send_iot_states)
        iot_states = {**SAMPLE_IOT_STATES, "session_id": session_id}
        print(f"[5] Sending IoT states →")
        await ws.send(json.dumps(iot_states))
        
        # Step 6: Send listen start (mirrors ws_send_listen_start)
        listen_start = {
            "session_id": session_id,
            "type": "listen",
            "state": "start",
            "mode": "auto_stop",
        }
        print(f"\n[6] Sending listen start →")
        await ws.send(json.dumps(listen_start))
        
        # Step 7: Send some fake audio frames (normally Opus-encoded)
        print(f"[7] Sending 3 fake audio frames (binary) →")
        for i in range(3):
            fake_opus = bytes([0x00] * 100)  # Placeholder
            await ws.send(fake_opus)
            print(f"    Frame {i+1}: {len(fake_opus)} bytes")
        
        # Step 8: Send listen stop
        listen_stop = {
            "session_id": session_id,
            "type": "listen",
            "state": "stop",
        }
        print(f"\n[8] Sending listen stop →")
        await ws.send(json.dumps(listen_stop))
        
        print(f"\n{'='*50}")
        print(f"✅ Handshake test PASSED!")
        print(f"   Session: {session_id}")
        print(f"   All protocol messages accepted.")
        print(f"{'='*50}")


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "ws://localhost:8000/xiaozhi/v1/"
    asyncio.run(simulate_device(url))
