# Sprint 2 + 3 · 任务文档

> 基于嵌入式源码分析结果编写，可直接交给 Claude Code 执行  
> 更新于 2026-04-27

---

## 关键发现（源码分析结论）

| 项目 | 实际情况 |
|------|---------|
| 温湿度 WS 消息 type | `"env"`（不是之前约定的 `"sensor"`） |
| 温湿度字段名 | `temp_c`（float）、`humi_rh`（float）、`ts`（uint，rt_tick） |
| 温湿度发送状态 | ✅ 学姐已实现，设备端代码已完成 |
| 猫叫检测结果变量 | `score`（float 0~1）、`confirmed_detected`（rt_bool_t） |
| 猫叫检测发送状态 | ❌ 未实现，需要新增 wsock_write |
| WS 发送函数 | `ws_send_text_locked(msg)` — 在 `env_ws_uploader.c` 已封装好 |
| g_app 访问方式 | `extern xiaozhi_app_t g_app;` 声明后直接用 |

---

## Task 1 · 后端接收温湿度数据

**文件：** `xiaozhi-server/app/routers/ws_device.py`  
**不需要改嵌入式代码，学姐已完成设备端**

### 实际 JSON 格式（设备发出的）

```json
{
  "session_id": "xxxxxxxx",
  "type": "env",
  "temp_c": 25.30,
  "humi_rh": 62.10,
  "ts": 123456
}
```

### 需要做的事

**1. `ws_device.py` 新增 `type == "env"` 分支**

```python
elif msg_type == "env":
    await _handle_env(ws, data, session_id or "")
```

**2. 新增 `_handle_env` 函数**

```python
async def _handle_env(ws, data, session_id):
    temp = data.get("temp_c")
    humi = data.get("humi_rh")
    ts   = data.get("ts")
    # 写入数据库 + 推送 dashboard
```

**3. 新建 `app/routers/sensor.py`，实现 REST API**

| 接口 | 说明 |
|------|------|
| `GET /api/sensor/latest` | 最新一条温湿度记录 |
| `GET /api/sensor/history?hours=24` | 时间序列，用于折线图 |
| `GET /api/sensor/stats?hours=24` | 最高/最低/平均值 |

**4. 新建 `app/services/sensor_service.py`**

- `save_record(temp_c, humi_rh, ts)` — 写入 SQLite `sensor_records` 表
- `get_latest()` — 查最新一条
- `get_history(hours)` — 查时间序列
- `get_stats(hours)` — 聚合统计

**5. `/ws/dashboard` 推送**

收到 env 消息后，向所有连接到 `/ws/dashboard` 的前端推送：

```json
{
  "event": "sensor_update",
  "data": { "temp_c": 25.3, "humi_rh": 62.1, "ts": 123456 }
}
```

**6. `app/main.py` 注册新路由**

```python
from .routers import sensor
app.include_router(sensor.router, prefix="/api")
```

---

## Task 2 · 后端接收猫叫检测数据

**文件：** `xiaozhi-server/app/routers/ws_device.py`

### 约定的 JSON 格式（嵌入式改完后发出的）

```json
{
  "session_id": "xxxxxxxx",
  "type": "meow",
  "score": 0.870,
  "is_cat": true,
  "ts": 123456
}
```

### 需要做的事

**1. `ws_device.py` 新增 `type == "meow"` 分支**

**2. 新建 `app/routers/meow.py`**

| 接口 | 说明 |
|------|------|
| `GET /api/meow/events?hours=24&is_cat=true` | 事件列表，支持筛选 |
| `GET /api/meow/stats` | 今日总数、猫叫数、噪声数 |
| `POST /api/meow/control` | 发送检测开关指令到设备 |

**3. 新建 `app/services/meow_service.py`**

- `save_event(score, is_cat, ts)` — 写入 `meow_events` 表
- `get_events(hours, is_cat)` — 查事件列表
- `get_stats()` — 统计今日数据

**4. `/ws/dashboard` 推送**

```json
{
  "event": "meow_event",
  "data": { "score": 0.87, "is_cat": true, "ts": 123456 }
}
```

---

## Task 3 · 嵌入式修改：猫叫检测结果上报

**文件：** `applications/xiaozhi/wake_word/meow_detect_once.cpp`  
**修改位置：** `meow_detect_thread_entry()` 函数，第 502 行附近

### 现有代码（第 502 行）

```cpp
xiaozhi_ui_set_meow_result(ui_detected ? true : false, score);
```

### 在这行下面插入

```cpp
// 上报猫叫检测结果到云端
{
    extern xiaozhi_app_t g_app;
    extern rt_bool_t ws_send_text_locked(const char *msg);
    char meow_msg[128];
    rt_snprintf(meow_msg, sizeof(meow_msg),
        "{\"session_id\":\"%s\",\"type\":\"meow\","
        "\"score\":%.3f,\"is_cat\":%s,\"ts\":%u}",
        g_app.ws.session_id,
        score,
        confirmed_detected ? "true" : "false",
        (unsigned)rt_tick_get());
    ws_send_text_locked(meow_msg);
}
```

### 注意事项

- `ws_send_text_locked` 已在 `env_ws_uploader.c` 中定义，需要确认能否跨文件调用（如果不能，在本文件顶部加 `extern` 声明）
- `confirmed_detected` 和 `score` 在 `meow_infer_from_pcm` 中是局部变量，需要确认 `meow_detect_thread_entry` 里能否直接访问，或者通过返回值/指针获取
- **改完后生成 patch 文件发给学姐烧录，不要自己尝试编译**

---

## Task 4 · 前端对接真实数据

**说明：** 前端 mock 数据结构需要和实际 API 字段名对齐

### 字段名对照表

| 前端目前 mock 用的字段 | 实际 API 返回字段 | 是否需要改 |
|----------------------|-----------------|-----------|
| `temperature` | `temp_c` | ⚠️ 需要改 |
| `humidity` | `humi_rh` | ⚠️ 需要改 |
| `timestamp` | `ts` | ⚠️ 需要改（注意 ts 是 rt_tick，不是 Unix 时间戳） |
| `confidence` | `score` | ⚠️ 需要改 |
| `is_cat` | `is_cat` | ✅ 一致 |

### ts 时间戳说明

`ts` 字段是 RT-Thread 的 `rt_tick_get()` 返回值，**不是 Unix 时间戳**，是设备启动后的 tick 计数（每毫秒加1）。后端收到后应该用服务器时间 `datetime.now()` 替代，存入数据库时存服务器时间，不要存设备 tick。

---

## 执行顺序建议

```
Task 1（后端温湿度）
    → 用测试脚本验证能收到数据
    → 前端温湿度页切换到真实 API

Task 2（后端猫叫）
    → 写完但先用 mock 数据测试

Task 3（嵌入式猫叫上报）
    → Claude Code 修改代码
    → 生成 diff 发给学姐烧录
    → 验证 Task 2 后端能收到真实数据

Task 4（前端字段名对齐）
    → Task 1/2 完成后统一修
```
