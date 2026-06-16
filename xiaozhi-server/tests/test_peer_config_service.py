from app.services.peer_config_service import build_peer_config


def test_build_peer_config_shapes_payload():
    payload = build_peer_config(
        {"autoOnMeow": True, "delaySeconds": 8},
        ["192.168.137.5", "192.168.137.9"],
        8848,
    )
    assert payload == {
        "type": "peer_config",
        "board2_ips": ["192.168.137.5", "192.168.137.9"],
        "port": 8848,
        "autoOnMeow": True,
        "delaySeconds": 8,
    }


def test_build_peer_config_defaults_when_missing():
    payload = build_peer_config({"autoOnMeow": False, "delaySeconds": None}, [], 8848)
    assert payload["autoOnMeow"] is False
    assert payload["delaySeconds"] == 15
    assert payload["board2_ips"] == []
