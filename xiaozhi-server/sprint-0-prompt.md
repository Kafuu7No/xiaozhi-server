# Sprint 0：基础框架搭建

## 项目背景

这是一个 AIoT 猫咪自动饮水控制系统的云端服务。硬件设备是 Infineon PSoC Edge M55，运行 RT-Thread RTOS，基于开源小智项目。设备通过 WebSocket 连接云端，上报传感器数据、猫叫检测事件、IoT 设备状态。

当前已有代码：FastAPI WebSocket 服务端，已实现设备握手（`/xiaozhi/v1/`）、会话管理、IoT 数据接收。代码在 `xiaozhi-server/` 目录。

本次任务：在现有代码基础上，搭建数据库、REST API、前端 WebSocket 推送通道，以及 Vue 3 前端项目。

---

## 任务一：后端 — 数据库模型 + REST API

### 1.1 安装依赖

在 `requirements.txt` 中追加：

```
aiosqlite==0.20.0
sqlalchemy[asyncio]==2.0.32
```

### 1.2 数据库配置

新建 `app/core/database.py`：

```python
"""SQLite async database setup using SQLAlchemy 2.0."""

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = "sqlite+aiosqlite:///./xiaozhi.db"

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session
```

### 1.3 数据模型

新建 `app/models/database.py`，定义以下 SQLAlchemy 模型：

```python
"""Database models for persistent storage."""

from datetime import datetime
from sqlalchemy import String, Float, Integer, Boolean, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from ..core.database import Base


class SensorRecord(Base):
    """温湿度传感器记录 — 设备定期上报"""
    __tablename__ = "sensor_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(20), index=True)
    temperature: Mapped[float] = mapped_column(Float)        # 摄氏度
    humidity: Mapped[float] = mapped_column(Float)            # 百分比
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MeowEvent(Base):
    """猫叫检测事件 — 设备检测到猫叫时上报"""
    __tablename__ = "meow_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(20), index=True)
    confidence: Mapped[float] = mapped_column(Float)          # 检测置信度 0.0-1.0
    is_cat: Mapped[bool] = mapped_column(Boolean, default=False)  # confidence >= 0.8
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WaterRecord(Base):
    """饮水记录 — 水泵启动/停止时记录（预留，水泵到货后启用）"""
    __tablename__ = "water_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(20), index=True)
    trigger_type: Mapped[str] = mapped_column(String(20))     # "manual" | "scheduled" | "meow_triggered"
    duration_seconds: Mapped[float] = mapped_column(Float)    # 出水时长
    started_at: Mapped[datetime] = mapped_column(DateTime)
    ended_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)


class ConversationLog(Base):
    """对话记录 — STT/TTS 文本"""
    __tablename__ = "conversation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(20), index=True)
    role: Mapped[str] = mapped_column(String(10))             # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text)
    emotion: Mapped[str] = mapped_column(String(20), nullable=True)  # LLM emotion tag
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

### 1.4 REST API 路由

新建 `app/routers/api.py`，实现以下接口：

| 方法 | 路径 | 功能 | 请求/响应 |
|------|------|------|-----------|
| GET | `/api/device/status` | 获取设备实时状态 | 返回 `{device_id, state, iot_states, connected: bool}` |
| GET | `/api/sensor/latest` | 最新一条温湿度 | 返回 `{temperature, humidity, recorded_at}` |
| GET | `/api/sensor/history?hours=24` | 温湿度历史 | 返回 `[{temperature, humidity, recorded_at}, ...]` |
| GET | `/api/meow/events?hours=24` | 猫叫事件列表 | 返回 `[{id, confidence, is_cat, recorded_at}, ...]` |
| GET | `/api/meow/stats` | 猫叫统计 | 返回 `{count_24h, count_48h, count_week}` |
| POST | `/api/iot/command` | 下发 IoT 指令 | 请求 `{device_name, method, parameters}` |
| GET | `/api/conversations?limit=50` | 对话历史 | 返回 `[{role, content, emotion, recorded_at}, ...]` |

**IoT 指令下发的实现要点：**

`POST /api/iot/command` 接收前端请求后，需要通过 `session_manager` 找到设备的 WebSocket 连接，然后发送：

```json
{
  "type": "iot",
  "commands": [
    {
      "name": "Speaker",
      "method": "SetVolume",
      "parameters": {"volume": 75}
    }
  ]
}
```

设备端 `Message_handle()` 的 `"iot"` 分支会解析 commands 数组并执行。

### 1.5 前端 WebSocket 推送通道

新建 `app/routers/ws_dashboard.py`，实现 `/ws/dashboard` 端点。

这是给前端（网页/手机）用的 WebSocket，和设备端的 `/xiaozhi/v1/` 是两个独立通道。

前端连接后，服务端推送以下事件：

```json
{"event": "device_status", "data": {"device_id": "xx:xx:xx", "state": "idle", "connected": true}}
{"event": "sensor_update", "data": {"temperature": 25.3, "humidity": 60.1, "recorded_at": "..."}}
{"event": "meow_detected", "data": {"confidence": 0.92, "is_cat": true, "recorded_at": "..."}}
{"event": "iot_state_changed", "data": {"states": [{"name": "Speaker", "state": {"volume": 70}}]}}
{"event": "conversation", "data": {"role": "user", "content": "给猫咪喂水", "recorded_at": "..."}}
```

实现思路：维护一个 `dashboard_clients: set[WebSocket]` 集合。设备端 WebSocket 收到数据后，同时广播给所有 dashboard 客户端。

### 1.6 在 main.py 中注册

```python
from .routers import ws_device, api, ws_dashboard

app.include_router(ws_device.router)
app.include_router(api.router)
app.include_router(ws_dashboard.router)

@app.on_event("startup")
async def startup():
    from .core.database import init_db
    await init_db()
```

### 1.7 测试数据接口

新建 `app/routers/mock.py`，提供模拟数据接口（前端开发用，设备不在手边时也能调试）：

| 方法 | 路径 | 功能 |
|------|------|------|
| POST | `/api/mock/sensor` | 模拟一条温湿度数据并广播 |
| POST | `/api/mock/meow` | 模拟一条猫叫事件并广播 |

这些接口内部直接调用数据库写入 + dashboard 推送逻辑，用 random 生成模拟数据。

---

## 任务二：前端 Vue 3 项目

### 2.1 项目初始化

在 `xiaozhi-server/` 同级目录创建前端项目：

```bash
npm create vite@latest xiaozhi-web -- --template vue
cd xiaozhi-web
npm install
npm install axios echarts tailwindcss @tailwindcss/vite
```

配置 Tailwind CSS 4.x（Vite 插件方式）：

`vite.config.js` 中添加 tailwindcss plugin：
```js
import tailwindcss from '@tailwindcss/vite'
export default defineConfig({
  plugins: [vue(), tailwindcss()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws': { target: 'ws://localhost:8000', ws: true }
    }
  }
})
```

`src/style.css` 顶部添加：
```css
@import "tailwindcss";
```

### 2.2 页面路由结构

使用 `vue-router`，规划以下页面：

```
/                    → Dashboard（主控台，设备状态 + 快捷操作）
/sensor              → 温湿度监控（实时数值 + 历史趋势图）
/meow                → 猫叫检测（事件列表 + 统计图表）
/iot                 → IoT 控制（Speaker/Screen/Led 控制卡片）
/water               → 饮水管理（预留页面，显示"水泵暂未接入"）
/settings            → 设置（报警阈值等配置）
```

### 2.3 关键组件

```
src/
├── views/
│   ├── DashboardView.vue      # 主控台
│   ├── SensorView.vue         # 温湿度
│   ├── MeowView.vue           # 猫叫检测
│   ├── IotControlView.vue     # IoT 控制
│   ├── WaterView.vue          # 饮水管理（预留）
│   └── SettingsView.vue       # 设置
├── components/
│   ├── DeviceStatus.vue       # 设备在线/离线状态指示
│   ├── SensorCard.vue         # 温度/湿度实时数值卡片
│   ├── SensorChart.vue        # ECharts 温湿度趋势图
│   ├── MeowEventList.vue      # 猫叫事件日志表格
│   ├── MeowStatsChart.vue     # 猫叫统计图（折线+饼图）
│   ├── IotDeviceCard.vue      # 单个 IoT 设备控制卡片
│   ├── NavBar.vue             # 顶部导航（含汉堡菜单适配手机）
│   └── BottomNav.vue          # 底部 Tab 导航（手机端）
├── composables/
│   ├── useWebSocket.js        # WebSocket 连接管理 composable
│   └── useApi.js              # Axios 封装
├── stores/
│   └── deviceStore.js         # Pinia store，存储设备实时状态
└── App.vue
```

### 2.4 WebSocket Composable

`src/composables/useWebSocket.js` 核心逻辑：

```javascript
// 连接 ws://host/ws/dashboard
// 自动重连（断开后 3 秒重试）
// 收到消息后按 event 类型分发：
//   device_status → 更新 deviceStore
//   sensor_update → 更新 deviceStore.latestSensor
//   meow_detected → 添加到 deviceStore.recentMeowEvents
//   iot_state_changed → 更新 deviceStore.iotStates
//   conversation → 添加到 deviceStore.conversations
```

### 2.5 响应式设计要求

- 使用 Tailwind CSS 的响应式前缀 `md:` `lg:` 做断点适配
- 手机端（< 768px）：底部 Tab 导航，卡片单列堆叠
- 桌面端（>= 768px）：侧边导航或顶部导航，卡片网格布局
- 所有图表使用 ECharts 的 `resize` 监听器适配容器大小

### 2.6 配色方案建议

- 主色：蓝色系（科技感）
- 强调色：绿色（在线/正常）、红色（告警/异常）、琥珀色（猫叫检测）
- 背景：浅灰 `#f8fafc`，卡片白色

---

## 任务三：前后端联通验证

完成后运行以下验证：

1. 启动后端：`cd xiaozhi-server && python run.py`
2. 启动前端：`cd xiaozhi-web && npm run dev`
3. 打开浏览器 `http://localhost:5173`，确认页面加载
4. 调用 mock 接口模拟数据：
   ```bash
   curl -X POST http://localhost:8000/api/mock/sensor
   curl -X POST http://localhost:8000/api/mock/meow
   ```
5. 确认前端通过 WebSocket 收到推送并更新显示

---

## 嵌入式端关键约束（开发时必须遵守）

以下信息来自设备固件源码分析，不可更改：

1. **设备 WebSocket 路径**：`/xiaozhi/v1/`，鉴权 `Authorization: Bearer 12345678`
2. **session_id 限制**：固件 `strncpy(session_id, ..., 9)` 只保留前 8 字符
3. **IoT 指令格式**：必须是 `{"type":"iot","commands":[{name, method, parameters}]}`
4. **已注册 IoT 设备**：
   - Speaker: SetVolume(volume: number), GetVolume()
   - Screen: SetBrightness(brightness: number), SetEmoji(emoji: string)
   - Led: SetLed(color: "red"|"green"|"blue"|"all"|"off")
5. **音频参数**：上行 Opus 16kHz 单声道 60ms帧，下行解码 24kHz
6. **设备状态机**：Unknown → Idle → Listening → Speaking
7. **多轮对话**：tts:stop 后 500ms 自动重启 listening，sentence_end 后 6秒超时重启
8. **温湿度数据**：AHT20 传感器在板上，数据上报接口格式待学姐确认（Sprint 2 再对接）

---

## 文件结构总览（Sprint 0 完成后）

```
xiaozhi-server/                # 后端
├── app/
│   ├── core/
│   │   ├── config.py          # [已有] 配置
│   │   └── database.py        # [新增] SQLite 数据库
│   ├── models/
│   │   ├── protocol.py        # [已有] WebSocket 协议模型
│   │   └── database.py        # [新增] 数据库模型
│   ├── routers/
│   │   ├── ws_device.py       # [已有] 设备 WebSocket
│   │   ├── ws_dashboard.py    # [新增] 前端推送 WebSocket
│   │   ├── api.py             # [新增] REST API
│   │   └── mock.py            # [新增] 模拟数据
│   ├── services/
│   │   ├── session_manager.py # [已有] 会话管理
│   │   └── broadcast.py       # [新增] 广播服务
│   └── main.py                # [修改] 注册新路由
├── requirements.txt           # [修改] 追加依赖
├── run.py
└── xiaozhi.db                 # [自动生成]

xiaozhi-web/                   # 前端
├── src/
│   ├── views/                 # 6 个页面
│   ├── components/            # 8 个组件
│   ├── composables/           # WebSocket + API
│   ├── stores/                # Pinia store
│   ├── router/index.js
│   ├── App.vue
│   └── style.css
├── index.html
├── vite.config.js
└── package.json
```
