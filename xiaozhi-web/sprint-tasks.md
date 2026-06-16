# XiaoZhi 猫咪饮水控制系统 · Sprint 任务清单

> 更新于 2026-04-27  
> 后端：FastAPI + SQLite · 前端：Vue 3 + DaisyUI + ECharts  
> 学姐确认：温湿度/猫叫检测通过 WebSocket JSON 上报；前端去掉表情控制；加摄像头监控模块

---

## 已完成

- [x] Sprint 0 · 后端基础框架（FastAPI + SQLite + WebSocket 握手 + Session 管理）
- [x] Sprint 1 · 前端基础框架（Vue 3 + DaisyUI Corporate + 侧边栏导航 + 6 个页面骨架）
- [x] Bug 修复：`transition-all` 崩溃 → `transition-colors`
- [x] ECharts 稳定性修复（SVG 渲染器 + animation:false + dispose on unmount）

---

## Sprint 1.1 · 前端收尾（约 0.5 天）

**目标：** 清理已知问题，推进到可演示状态

### 任务

- [ ] **删除 IoT 控制页的表情（Screen Emoji）部分**
  - 移除 Screen 卡片里 neutral / happy / sad / angry / laughing / sleepy 六个按钮
  - Screen 卡片只保留亮度滑块（SetBrightness）

- [ ] **UI 精修**
  - 背景色改为 `#F5F6FA`（浅灰蓝，区别于纯白）
  - Card 统一：`bg-white border border-gray-100 rounded-xl shadow-sm`
  - 设备离线 Banner：灰底 + 灰色文字 + WifiOff 图标（不要黄色警告）
  - ECharts 颜色：主色 `#3B82F6`，辅色 `#10B981`

- [ ] **将前端代码推送到 GitHub（新建 `xiaozhi-web` 仓库）**

### 不需要后端改动

---

## Sprint 2 · 温湿度监控（约 3 天）

**目标：** AHT20 传感器数据流入云端，前端实时展示 + 历史趋势 + 超阈值报警

### 与学姐约定的上报协议

设备每 30 秒通过 WebSocket 发送：

```json
{
  "session_id": "xxxxxxxx",
  "type": "sensor",
  "data": {
    "temperature": 25.3,
    "humidity": 62.1,
    "timestamp": 1714200000
  }
}
```

> 💬 **需要学姐在设备端实现：** 定时采集 AHT20 数据后发送以上 JSON

### 后端任务

- [ ] `ws_device.py`：新增 `type == "sensor"` 分支
- [ ] `app/services/sensor_service.py`：数据写入 SQLite `sensor_records`
- [ ] REST API：
  - `GET /api/sensor/latest` — 最新一条
  - `GET /api/sensor/history?hours=24` — 时间序列
  - `GET /api/sensor/stats` — 最高/最低/平均值
- [ ] `/ws/dashboard` 推送：新数据到达时推送给前端

### 前端任务

- [ ] **温湿度页**（`SensorView.vue`）完整实现：
  - 顶部两张卡片：当前温度 / 当前湿度
  - 报警指示：温度 > 35°C 或湿度 > 80% 显示红色警告
  - 24 小时折线图（双 Y 轴）
  - 最近 20 条原始数据表格

---

## Sprint 3 · 猫叫检测完善（约 3 天）

**目标：** 云端可控制设备开关检测；检测事件上报并可视化

### 与学姐约定的协议

**① 设备上报猫叫事件（设备 → 云端）：**

```json
{
  "session_id": "xxxxxxxx",
  "type": "meow",
  "data": {
    "confidence": 0.87,
    "is_cat": true,
    "timestamp": 1714200000
  }
}
```

**② 云端发送检测开关指令（云端 → 设备）：**

```json
{
  "type": "meow_control",
  "action": "start"
}
```

> 💬 **需要学姐在设备端实现：**
> 1. 检测到猫叫后发送 `type: meow` 消息
> 2. 处理 `type: meow_control` 消息，根据 `action` 开启/关闭 TFLite 检测

### 后端任务

- [ ] `ws_device.py`：新增 `type == "meow"` 分支
- [ ] `app/services/meow_service.py`：写入 SQLite `meow_events`
- [ ] REST API：
  - `GET /api/meow/events?hours=24&is_cat=true` — 事件列表
  - `GET /api/meow/stats` — 今日/本周统计
  - `POST /api/meow/control` — 向设备发送开关指令

### 前端任务

- [ ] **猫叫检测页**（`MeowView.vue`）完整实现：
  - **顶部控制区：** "启动检测" / "停止检测" 按钮，当前检测状态指示
  - 今日猫叫次数统计卡片
  - 24 小时频率柱状图
  - 置信度分布图
  - 事件列表（时间 + 置信度进度条 + 是否猫叫徽章）

---

## Sprint 4 · 摄像头监控（约 3 天）

**目标：** 前端展示摄像头画面 + 开关控制

> ⚠️ **前置确认（需要和学姐讨论传输方式）：**
>
> | 方案 | 说明 | 推荐度 |
> |------|------|--------|
> | A. MJPEG over HTTP | 设备起 HTTP 流，前端用 `<img src="http://设备IP/stream">` | ⭐⭐⭐ 最简单 |
> | B. WebSocket 传 JPEG 帧 | Binary 帧传图片，前端 Canvas 渲染 | ⭐⭐ 稍复杂 |
> | C. RTSP | 需要额外播放器，前端支持困难 | ⭐ 不推荐 |
>
> **建议方案 A**，请学姐确认。

### 后端任务

- [ ] `POST /api/camera/control`：向设备发送摄像头开关指令

### 前端任务

- [ ] 摄像头区域（放在猫叫检测页或单独一个标签页）：
  - 摄像头开关按钮
  - 监控画面展示（方案 A 直接 `<img>` 标签）
  - 连接状态指示

---

## Sprint 5 · 饮水控制（水泵到货后，约 3 天）

**目标：** 手动控泵 + 定时计划 + 饮水记录 + 猫叫自动联动

> ⚠️ **前置条件：** 水泵到货，学姐在设备端注册水泵为 IoT 设备（参考 Speaker/Led 格式）

### 请学姐注册的 IoT 设备描述

```json
{
  "name": "WaterPump",
  "description": "饮水泵",
  "properties": {
    "is_running": { "type": "boolean" }
  },
  "methods": {
    "Start": { "parameters": { "duration": { "type": "number", "unit": "seconds" } } },
    "Stop": {}
  }
}
```

### 后端任务

- [ ] `app/services/water_service.py`：饮水记录存入 SQLite
- [ ] REST API：
  - `POST /api/water/pump/control` — 手动开泵/关泵
  - `GET /api/water/records` — 历史记录
  - `POST /api/water/schedule` — 创建定时计划
  - `GET /api/water/schedule` — 获取计划列表
- [ ] APScheduler 定时任务：到点自动发 IoT 指令

### 前端任务

- [ ] **饮水管理页**（`WaterView.vue`）：
  - 手动控泵卡片（立即开泵 N 秒）
  - 定时计划列表（增删改查）
  - 每日饮水量柱状图
  - 猫叫联动开关 + 延时秒数设置

---

## Sprint 6 · 联调 + 部署（约 3 天）

**目标：** 三端打通，演示就绪

- [ ] 设备端 + 后端 + 前端联调
- [ ] 边缘情况：断线重连、网络超时、设备不在线时前端降级显示
- [ ] Docker Compose（后端 + 前端 Nginx）
- [ ] 云服务器部署
- [ ] 演示脚本 + PPT

---

## 协议对接清单（需要和学姐确认的部分）

| 功能 | 方向 | 消息 type | 状态 |
|------|------|-----------|------|
| Hello 握手 | 双向 | `hello` | ✅ 已实现 |
| IoT 指令（通用） | 云端→设备 | `iot` | ✅ 已实现 |
| 温湿度上报 | 设备→云端 | `sensor` | ⏳ 待学姐实现 |
| 猫叫事件上报 | 设备→云端 | `meow` | ⏳ 待学姐实现 |
| 开关猫叫检测 | 云端→设备 | `meow_control` | ⏳ 待学姐实现 |
| 摄像头开关 | 云端→设备 | 待定 | ⏳ 待方案确认 |
| 水泵控制 | 云端→设备 | `iot`（WaterPump） | ⏳ 待水泵到货 |
