"""
WebSocket 握手测试

模拟设备端行为，验证 Hello 握手流程。
用法: python tests/test_ws_handshake.py [server_url]
"""

import asyncio
import json
import sys

import websockets


async def test_hello_handshake(uri: str = "ws://localhost:8000/xiaozhi/v1/"):
    """模拟设备端的完整握手流程"""
    print(f"[Test] Connecting to {uri}")

    # 设备端连接时携带的 header（对应 xiaozhi.cpp wsock_connect 调用）
    headers = {
        "Authorization": "Bearer 12345678",
        "Protocol-Version": "1",
        "Device-Id": "aa:bb:cc:dd:ee:ff",
        "Client-Id": "test-0001-0002-0003",
    }

    async with websockets.connect(uri, additional_headers=headers) as ws:
        print("[Test] Connected ✓")

        # Step 1: 发送 Hello（对应 HELLO_MESSAGE）
        hello = {
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
        await ws.send(json.dumps(hello))
        print(f"[Test] Sent hello →")

        # Step 2: 等待 Hello 响应
        response = await asyncio.wait_for(ws.recv(), timeout=5.0)
        resp = json.loads(response)
        print(f"[Test] Received ← {json.dumps(resp, indent=2)}")

        # 验证响应
        assert resp["type"] == "hello", f"Expected type 'hello', got '{resp['type']}'"
        assert "session_id" in resp, "Missing session_id"
        assert len(resp["session_id"]) <= 8, f"session_id too long: {resp['session_id']}"
        assert resp["audio_params"]["sample_rate"] == 16000
        assert resp["audio_params"]["frame_duration"] == 60

        session_id = resp["session_id"]
        print(f"[Test] session_id = {session_id}")
        print(f"[Test] Hello handshake ✓")

        # Step 3: 模拟发送 IoT descriptors（设备端在收到 hello 后自动发送）
        iot_desc = {
            "session_id": session_id,
            "type": "iot",
            "update": True,
            "descriptors": [
                {
                    "name": "Speaker",
                    "description": "Speaker controls",
                    "properties": {"volume": {"type": "number", "min": 0, "max": 100}},
                    "methods": ["SetVolume", "GetVolume"],
                },
                {
                    "name": "Led",
                    "description": "LED control",
                    "methods": ["SetLed"],
                },
            ],
        }
        await ws.send(json.dumps(iot_desc))
        print("[Test] Sent IoT descriptors ✓")

        # Step 4: 模拟发送 IoT states
        iot_states = {
            "session_id": session_id,
            "type": "iot",
            "update": True,
            "states": [
                {"name": "Speaker", "state": {"volume": 70}},
                {"name": "Led", "state": {}},
            ],
        }
        await ws.send(json.dumps(iot_states))
        print("[Test] Sent IoT states ✓")

        # Step 5: 模拟 listen start（按键唤醒后的行为）
        listen_start = {
            "session_id": session_id,
            "type": "listen",
            "state": "start",
            "mode": "auto_stop",
        }
        await ws.send(json.dumps(listen_start))
        print("[Test] Sent listen:start ✓")

        # 等一会儿再断开，模拟对话
        await asyncio.sleep(1)

        # Step 6: 模拟 listen stop
        listen_stop = {
            "session_id": session_id,
            "type": "listen",
            "state": "stop",
        }
        await ws.send(json.dumps(listen_stop))
        print("[Test] Sent listen:stop ✓")

    print("\n[Test] All tests passed! ✓✓✓")


async def test_auth_failure(uri: str = "ws://localhost:8000/xiaozhi/v1/"):
    """测试鉴权失败"""
    print(f"\n[Test] Testing auth failure...")
    headers = {
        "Authorization": "Bearer wrong_token",
        "Device-Id": "aa:bb:cc:dd:ee:ff",
    }
    try:
        async with websockets.connect(uri, additional_headers=headers) as ws:
            await ws.recv()
            print("[Test] FAIL — should have been rejected")
    except websockets.exceptions.ConnectionClosed as e:
        if e.code == 4001:
            print(f"[Test] Auth rejection ✓ (code={e.code})")
        else:
            print(f"[Test] Unexpected close code: {e.code}")
    except Exception as e:
        print(f"[Test] Connection rejected ✓ ({type(e).__name__})")


async def main():
    uri = sys.argv[1] if len(sys.argv) > 1 else "ws://localhost:8000/xiaozhi/v1/"
    await test_hello_handshake(uri)
    await test_auth_failure(uri)


if __name__ == "__main__":
    asyncio.run(main())
