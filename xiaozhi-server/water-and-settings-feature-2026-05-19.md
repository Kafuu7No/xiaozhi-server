# 饮水管理后端 + 全局设置 改动记录

**日期**：2026-05-19
**涉及仓库**：`xiaozhi-server`（后端）、`xiaozhi-web`（前端）
**说明**：本文记录 2026-05-19 两轮改动——①补齐饮水管理后端；②设置页接后端并让阈值真正生效。供下次对话或交接参考。

---

## 一、饮水管理后端

### 背景

此前「饮水管理」只有前端页面，靠浏览器 localStorage 假数据演示，后端 8 个接口完全不存在。本轮补齐后端。

### 数据流（水泵控制）

```
网页「立即开泵」按钮
  → POST /api/water/pump/control {action:"start", duration, trigger_type}
  → 后端经设备 WebSocket 下发 {"type":"water_pump","action":"start","duration":N}
  → 后端写一条出水记录入库
  → 网页刷新记录列表 / 图表
停泵：action:"stop" → 下发 stop 指令 + 把仍在运行的记录结束时间截到当前
```

### 后端改动

| 文件 | 改动 |
|---|---|
| `app/services/water_service.py` | **新建**。纯函数 `estimate_volume_ml`/`serialize_record`/`serialize_schedule`/`build_pump_command`；异步：出水记录 `list_records`/`create_pump_record`/`stop_active_pump`、定时计划 `list_schedules`/`create_schedule`/`update_schedule`/`delete_schedule`；`get_settings`/`save_settings` 委托给 `settings_service`（见第二部分） |
| `app/models/database.py` | 复用原有 `WaterRecord` 表；**新增** `WaterSchedule` 表（`id/label/time/duration_seconds/enabled/created_at`） |
| `app/routers/water.py` | **新建**。8 个接口（见下表） |
| `app/main.py` | 挂载 water 路由（`prefix="/api"`） |
| `tests/test_water_service.py` | **新建**。6 个单元测试（TDD：先写测试看失败再实现） |

### 新增 API 端点

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/water/records` | 出水记录列表（倒序） |
| POST | `/api/water/pump/control` | 启停水泵；body `{action:"start"/"stop", duration, trigger_type}` |
| GET | `/api/water/schedule` | 定时计划列表 |
| POST | `/api/water/schedule` | 新建定时计划 |
| PUT | `/api/water/schedule/{id}` | 修改定时计划（部分字段；不存在→404） |
| DELETE | `/api/water/schedule/{id}` | 删除定时计划（不存在→404） |
| GET/PUT | `/api/water/settings` | 猫叫联动设置（读写，底层是共享的 `app_settings`） |

水泵估算水量按 3 ml/秒。

### 前端改动

| 文件 | 改动 |
|---|---|
| `src/composables/useApi.js` | 饮水相关函数改为调真实接口，**但保留 localStorage 兜底**（`requestWithFallback`）：后端可用走真实接口，后端不可用回退 mock。这是为演示稳妥而**特意保留**的，不是遗漏 |
| `src/views/WaterView.vue` | 仅文案，提示水泵硬件未接入 |

> 注：曾一度删除前端 mock 兜底，后因「演示需要」按要求恢复，所以现在 mock 仍在。

---

## 二、全局设置（设置页接后端 + 阈值生效）

### 背景

设置页（猫叫阈值 / 温湿度告警阈值）原本只存浏览器 localStorage，改了不影响真实检测。本轮：①设置存到后端；②阈值改动**实时影响**猫叫判定与温湿度告警；③把原本散在饮水页的「猫叫联动」设置并入设置页，与饮水页共用同一份存储。

### 数据模型

新增 `app_settings` 单行表（`id` 恒为 1），**取代**了饮水那轮临时建的 `WaterSetting` 表：

| 列 | 默认 | 用途 |
|---|---|---|
| `meow_threshold` | 0.8 | 猫叫判定得分阈值 |
| `temp_max` | 35.0 | 温度告警上限 |
| `humid_min` | 30.0 | 湿度告警下限 |
| `humid_max` | 80.0 | 湿度告警上限 |
| `auto_on_meow` | false | 猫叫联动补水开关 |
| `delay_seconds` | 15 | 联动延时秒数 |

默认值与原 `config.py` 配置一致，所以设置为默认值时行为与改造前完全相同。

### 后端改动

| 文件 | 改动 |
|---|---|
| `app/models/database.py` | 新增 `AppSetting` 表；移除 `WaterSetting` |
| `app/services/settings_service.py` | **新建**。纯函数 `serialize_settings`（camelCase）/`to_db_fields`（camel→snake、过滤）；异步 `get_or_create`/`get_settings`/`save_settings`/`get_thresholds`/`get_meow_threshold` |
| `app/routers/api.py` | 新增 `GET/PUT /api/settings` |
| `app/services/water_service.py` | `get_settings`/`save_settings` 改为委托 `settings_service`，只返回水联动子集 |
| `app/services/meow_service.py` | `parse_meow_payload(message, threshold=0.8)` 新增阈值参数 |
| `app/services/sensor_service.py` | `build_alerts`/`serialize_record` 新增 `thresholds` 参数；`save_record`/`get_history` 取存储阈值传入 |
| `app/routers/ws_device.py` | `_handle_meow` 取存储的猫叫阈值传给 `parse_meow_payload` |
| `app/routers/mock.py` | `mock_meow` 用存储阈值判定 is_cat |
| `app/routers/sensor.py` | `/sensor/thresholds` 改读存储值；`get_sensor_latest` 传入存储阈值 |
| `tests/test_settings_service.py` | **新建**，3 个测试 |
| `tests/test_sensor_service.py` | **新建**，2 个测试（阈值参数） |
| `tests/test_meow_service.py` | 新增 2 个测试（自定义阈值） |
| `tests/test_water_service.py` | 移除 `serialize_settings` 相关测试（该函数已并入 settings） |

### 新增 API 端点

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/settings` | 读取全局设置，返回 `{meowThreshold,tempMax,humidMin,humidMax,autoOnMeow,delaySeconds}` |
| PUT | `/api/settings` | 部分更新（任意字段子集），返回更新后的全部设置 |

### 阈值如何「真正生效」

- **猫叫**：设备未显式给 `is_cat` 时，`is_cat = score >= meow_threshold`。阈值参数从默认 0.8 改为按需注入，调用点（`_handle_meow`、`mock_meow`）从 `app_settings` 取当前值。
- **温湿度告警**：`build_alerts` 原本读 `config.py` 固定值，现接受 `thresholds` 参数；`save_record`/`get_history`/`/sensor/latest`/`/sensor/thresholds` 都改为取 `app_settings` 的值。
- 设计上用「参数注入 + 默认值=原配置」，所以旧单元测试不改也全过。

### 前端改动

| 文件 | 改动 |
|---|---|
| `src/composables/useApi.js` | 新增 `getAppSettings`/`saveAppSettings`（走 `/api/settings`，**无** localStorage 兜底） |
| `src/views/SettingsView.vue` | 从 localStorage 改为读写 `/api/settings`；新增「湿度告警下限」和「猫叫联动」卡片（开关 + 延时） |

> 设置页现在依赖后端：后端没开会显示「加载设置失败」。猫叫联动设置在设置页和饮水页都能改，背后同一份 `app_settings`，自动同步。

---

## 三、验证结果（2026-05-19 全部通过）

- 后端 **28 个单元测试**全过（`.venv/Scripts/python.exe -m unittest discover tests`）
- `app.main` 导入正常，34 条路由
- 饮水接口实测 11 项：开/停泵、记录列表、计划增改删、删不存在→404、设置读写持久化
- 设置接口实测 8 项：设置增改查持久化；`/water/settings` 与 `/api/settings` 共用同一行；猫叫阈值调低→mock 事件全判猫叫；温度上限调 12→告警触发、调 99→不触发——**阈值确实实时生效**
- 前端 `npm run build` 构建成功
- 测试数据已清理

---

## 四、注意事项 / 待办

- 饮水前端保留 localStorage 兜底（演示用）；设置页无兜底，必须开后端。
- 水泵硬件未接入：`/water/pump/control` 会下发 WS 指令但无设备响应；需通知固件同学实现 `water_pump` 指令处理。
- `WaterSetting` 表已被 `app_settings` 取代；旧库里残留的 `water_settings` 空表无害，可忽略。
- 待办：确认语音助手（STT/LLM/TTS）是否做。

## 五、相关文档

- `项目现状-2026-05-19.md`（项目根目录）— 项目整体进度
- `camera-photo-feature-2026-05-18.md` — 摄像头拍照改造
- `tests/test_handshake.py` — 设备握手协议参考
