# 摄像头：视频流 → 拍照上传 改造记录

**日期**：2026-05-18
**涉及仓库**：`xiaozhi-server`（后端）、`xiaozhi-web`（前端）

## 背景与目标

原方案是摄像头**实时视频流**（MJPEG），但只是 mock，协议一直未确认。
学姐要求改成：**没有视频功能，改成拍静态照片上传云端，网页显示图片，并加一个"拍照"按钮触发。**

确认的需求细节：
- "按键" = **网页上的按钮**（不是设备物理键）
- "云端" = 外部云存储，但**目前还没做**，先**存服务器本地**

## 数据流

```
网页点「拍照」按钮
  → POST /api/camera/capture
  → 后端经设备 WebSocket 下发 {"type":"camera","action":"capture"}
  → 设备拍一张 JPEG
  → 设备 HTTP POST 原始字节到 /api/camera/upload
  → 后端存盘到 photos/ + 写入 camera_photos 表
  → 网页轮询 GET /api/camera/latest（点完拍照后轮询，最多 8 秒）拿到新照片并显示
```

## 后端改动（xiaozhi-server）

| 文件 | 改动 |
|---|---|
| `app/services/camera_service.py` | **新建**。纯函数：`build_photo_filename`（生成文件名，MAC 地址里的 `:` 等非法字符转 `_`）、`serialize_photo`、`build_capture_command`；异步函数：`save_photo`（写盘+入库）、`get_latest_photo`。常量 `PHOTOS_DIR = xiaozhi-server/photos/`、`PHOTO_URL_PREFIX = "/photos"` |
| `app/models/database.py` | **新增** `CameraPhoto` 表：`id / device_id / filename / captured_at`。`init_db()` 启动时自动建表 |
| `app/routers/api.py` | **删除** `camera_state` 字典、`CameraControlRequest`、`GET /camera/status`、`POST /camera/control`（含 `transport`/`stream_url`/`protocol_confirmed` 等视频流字段）。**新增** 3 个端点（见下） |
| `app/main.py` | 挂载静态目录：`app.mount("/photos", StaticFiles(directory=PHOTOS_DIR))`，启动时自动建 `photos/` 目录 |
| `tests/test_camera_service.py` | **新建**。6 个单元测试，TDD 流程（先写测试看失败再实现） |

> `ws_device.py` **未改动**：拍照指令走 `api.py` 里已有的 `_send_device_payload()` 发出；设备不通过 WS 回传，而是用 HTTP 上传，所以接收循环不需要新分支。

### 新增 API 端点

| 方法 | 路径 | 说明 | 返回 |
|---|---|---|---|
| `POST` | `/api/camera/capture` | 给已连接设备下发拍照指令 | `{"status":"capture_requested"}`；无设备连接 → `503` |
| `POST` | `/api/camera/upload` | 设备上传照片。**请求体 = 原始 JPEG 字节**（非 multipart）。`device_id` 取自 query 参数或 `Device-Id` 请求头 | 照片信息 dict；空 body → `400` |
| `GET` | `/api/camera/latest` | 取最新一张照片 | `{"photo": {...} 或 null, "device_connected": bool}` |

照片信息 dict 结构：
```json
{"id": 1, "device_id": "cat-01", "filename": "cat-01_20260518_134408_836777.jpg",
 "url": "/photos/cat-01_20260518_134408_836777.jpg", "captured_at": "2026-05-18T13:44:08.836777"}
```

## 前端改动（xiaozhi-web）

| 文件 | 改动 |
|---|---|
| `src/views/MeowView.vue` | 「摄像头区域」→「摄像头照片」。删除视频流 `<img>`、流地址输入框、传输协议确认 UI。改成：单个「拍照」按钮 + 最新照片显示 + 照片信息面板（设备连接 / 拍摄时间 / 设备ID）。新增 `latestPhoto`/`cameraDeviceConnected`/`capturing`/`captureError` 状态、`capturePhoto()` 与 `pollForNewPhoto()` 函数 |
| `src/composables/useApi.js` | 删除 `getCameraStatus`/`setCameraControl` 及 `STORAGE_KEYS.camera`、`DEFAULT_CAMERA_STATUS`。新增 `triggerCapture()`（POST /camera/capture）、`getLatestPhoto()`（GET /camera/latest，失败时优雅降级返回空照片） |
| `vite.config.js` | proxy 新增 `'/photos': 'http://localhost:8000'`，让图片 `<img src="/photos/...">` 能代理到后端 |

## 验证结果（2026-05-18 全部通过）

- 后端 15 个单元测试全过（`.venv/Scripts/python.exe -m unittest discover tests`）
- `app.main` 导入正常，24 条路由
- 接口实测：无设备 `/capture`→503；空 body `/upload`→400；上传 JPEG→200 并入库；`/camera/latest` 取回照片；`/photos/xxx.jpg` 返回原始字节一致
- 前端 `npm run build` 构建成功，无旧引用残留
- 验证用的测试照片和 DB 行已清理

## 待办（下一步）

1. **设备固件**（不在这两个仓库内）：需支持收到 `{"type":"camera","action":"capture"}` 后拍 JPEG，用 HTTP `POST` 把**原始图片字节**发到 `/api/camera/upload?device_id=<设备ID>`，`Content-Type: image/jpeg`。**需通知做固件的同学。**
2. **接外部云存储**（OSS 等）：目前存本地 `photos/`。迁移时**只需改 `camera_service.py` 的 `save_photo` 和 `serialize_photo` 两个函数**，路由和前端无需改动。
3. 可选：`photos/` 目录是否加入 `.gitignore`，避免照片进版本库。

## 运行方式备忘

- 后端：`xiaozhi-server` 目录下用 `.venv` 的 Python，跑 `run.py`（默认端口见 `app/core/config.py`，开发期前端 proxy 指向 `localhost:8000`）
- 前端：`xiaozhi-web` 目录 `npm run dev`
- 后端测试：`xiaozhi-server` 目录 `.venv/Scripts/python.exe -m unittest discover tests`
