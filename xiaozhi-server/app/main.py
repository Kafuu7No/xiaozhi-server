"""XiaoZhi Cloud Server - FastAPI Application.

A replacement cloud backend for the XiaoZhi AI voice assistant
running on Infineon PSoC Edge M55 with RT-Thread RTOS.
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .core.config import get_settings
from .routers import api, meow, mock, ota, sensor, water, ws_dashboard, ws_device, ws_voice
from .services.camera_service import PHOTOS_DIR
from .services.discovery_service import start_discovery_service, stop_discovery_service
from .services.schedule_runner import schedule_runner
from .services.tcp_photo_receiver import tcp_photo_receiver
from .services.udp_hardware_bridge import udp_hardware_bridge

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(name)-12s] %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)

settings = get_settings()

app = FastAPI(
    title="XiaoZhi Cloud Server",
    version="0.1.0",
    description="Cloud backend for XiaoZhi AI voice assistant on PSoC Edge M55",
)

# CORS for future Vue frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(ws_device.router)
app.include_router(ota.router)
app.include_router(api.router)
app.include_router(sensor.router, prefix="/api")
app.include_router(meow.router, prefix="/api")
app.include_router(water.router, prefix="/api")
app.include_router(ws_dashboard.router)
app.include_router(ws_voice.router)
app.include_router(mock.router)

# Serve uploaded camera photos as static files
PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/photos", StaticFiles(directory=PHOTOS_DIR), name="photos")


@app.on_event("startup")
async def startup():
    import asyncio

    from .core.database import init_db
    await init_db()
    await start_discovery_service()

    log = logging.getLogger("xz.startup")

    # Warm up STT in the background so the first utterance doesn't hit the
    # provider-load timeout. Only when the model is already on disk -- never
    # trigger a download at startup.
    from .services.voice import stt as stt_module
    from .services.voice.factory import get_stt

    if stt_module.local_model_available():
        asyncio.create_task(asyncio.to_thread(get_stt))
        log.info("STT warmup started (local model found)")
    else:
        log.warning("Local STT model missing (%s); first voice turn may fail", stt_module.LOCAL_MODEL_DIR)
    try:
        await udp_hardware_bridge.start()
    except Exception as exc:
        log.error("UDP hardware bridge failed to start: %s", exc)

    try:
        await tcp_photo_receiver.start()
    except Exception as exc:
        log.error("TCP photo receiver failed to start: %s", exc)

    try:
        await schedule_runner.start()
    except Exception as exc:
        log.error("Schedule runner failed to start: %s", exc)


@app.on_event("shutdown")
async def shutdown():
    await udp_hardware_bridge.stop()
    await tcp_photo_receiver.stop()
    await schedule_runner.stop()
    await stop_discovery_service()


@app.get("/")
async def root():
    """Health check endpoint."""
    from .services.session_manager import session_manager
    return {
        "service": "xiaozhi-cloud",
        "version": "0.1.0",
        "active_sessions": session_manager.active_count,
    }


@app.get("/api/sessions")
async def list_sessions():
    """Debug endpoint: list active device sessions."""
    from .services.session_manager import session_manager
    sessions = []
    for sid, (session, _) in session_manager._sessions.items():
        sessions.append({
            "session_id": session.session_id,
            "device_id": session.device_id,
            "state": session.state.value,
            "iot_devices": len(session.iot_descriptors),
        })
    return {"sessions": sessions}
