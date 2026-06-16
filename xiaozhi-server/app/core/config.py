"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True
    discovery_enabled: bool = True
    discovery_port: int = 58123

    # Auth
    device_token: str = "12345678"

    # Audio params matching device firmware expectations
    audio_sample_rate: int = 16000
    audio_frame_duration: int = 60  # ms
    audio_tts_sample_rate: int = 24000

    # Sensor alert thresholds
    sensor_temp_max: float = 35.0
    sensor_humid_min: float = 30.0
    sensor_humid_max: float = 80.0

    # Voice / LLM (DeepSeek, OpenAI-compatible)
    deepseek_api_key: str = ""
    llm_base_url: str = "https://token.memoh.net/v1"
    llm_model: str = "deepseek-chat"
    llm_system_prompt: str = (
        "你是一个智能猫窝的语音助手，负责陪伴和照看主人的猫。"
        "回答简洁、亲切、口语化，一般不超过两句话。"
    )
    llm_history_turns: int = 6

    # STT / TTS
    voice_upstream: str = "local"
    official_voice_ws_url: str = "wss://api.tenclass.net/xiaozhi/v1/"
    official_voice_token: str = ""
    stt_provider: str = "funasr"
    tts_provider: str = "edgetts"
    tts_voice: str = "zh-CN-XiaoxiaoNeural"

    # UDP bridge for the standalone key_camera firmware
    udp_hardware_enabled: bool = True
    # 兜底下发地址（同子网；DHCP 变了也只是兜底）。固件 lwIP 不收子网广播，
    # 必须单播；桥会优先用 last_sender(照片源IP) + ARP 按 MAC 解析的所有候选IP，
    # 多目标下发，换网/重启后无需手动激活。
    udp_device_host: str = "192.168.137.203"
    udp_device_port: int = 8848
    # board2(继电器+摄像头) 的 WiFi MAC，用于按 MAC 反查当前 IP
    udp_device_mac: str = "CC:47:40:11:19:BB"
    udp_listen_host: str = "0.0.0.0"
    udp_listen_port: int = 8848
    udp_photo_max_bytes: int = 100 * 1024
    udp_photo_idle_timeout: float = 5.0

    # TCP photo upload (reliable, replaces lossy UDP photo path)
    tcp_photo_enabled: bool = True
    tcp_listen_host: str = "0.0.0.0"
    tcp_listen_port: int = 8849

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
