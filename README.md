# 智能猫窝 (Smart Cat-Care / XiaoZhi)

一个基于「小智 AI」生态的智能猫窝系统：**两块嵌入式开发板 + 云端服务 + Web 控制台**。
支持猫叫声检测、自动喂水（猫叫触发 / 定时 / 手动）、拍照、温湿度监测，以及与官方小智语音云的实时语音对话。

> 这是一个 **monorepo**，同时包含嵌入式固件源码和云端/前端源码。

---

## 1. 系统架构

```
                 ┌─────────────────────────────────────────────┐
                 │              PC (Windows 热点 AP)             │
                 │            热点 IP: 192.168.137.1            │
                 │                                             │
   WebSocket     │   ┌───────────────┐    ┌────────────────┐   │
 (语音/猫叫/温湿度) │   │ xiaozhi-server │←──→│  xiaozhi-web   │   │
 ┌──────────┐    │   │ FastAPI :8000  │    │  Vue3  :5173   │   │
 │  board1  │←───┼──→│  (云端)        │    │  (控制台)       │   │
 │ E84/M55  │    │   └──────┬────────┘    └────────────────┘   │
 │ 猫叫+温湿度 │   │          │ UDP:8848 命令 / TCP:8849 照片      │
 └────┬─────┘    │   ┌──────┴────────┐                         │
      │ UDP 直连  │   │    board2      │                         │
      └──────────┼──→│   PSoC6        │  水泵(继电器) + PTC06摄像头  │
      (猫叫→喂水+拍照)│   └───────────────┘                         │
                 └─────────────────────────────────────────────┘
                                  │ WebSocket 代理
                                  ▼
                    官方小智语音云 wss://api.tenclass.net
```

- **board1**（猫叫检测 + 温湿度）通过 **WebSocket** 连云端；语音对话由云端**代理转发**到官方小智云。
- **board2**（水泵 + 摄像头）通过 **UDP 收命令、TCP 传照片**。
- **猫叫→喂水+拍照** 联动在**嵌入式侧**完成：board1 检测到「10 秒内 3 次猫叫」后**直接经 UDP 通知 board2** 喂水并拍照，同时上报云端记录。云端**不会**自动喂水。

---

## 2. 仓库目录结构

| 目录 | 组件 | 说明 |
|------|------|------|
| `xiaozhi-server/` | **云端** | FastAPI + uvicorn，SQLite 持久化。语音 / 猫叫 / 温湿度 / 喂水 / 照片 / 定时任务。 |
| `xiaozhi-web/` | **前端控制台** | Vue 3 + Vite + Tailwind/daisyUI + ECharts。 |
| `Edgi_Talk_M55_XiaoZhi_2/Edgi_Talk_M55_XiaoZhi/` | **board1 固件** | Infineon PSoC Edge **E84 / Cortex-M55**，RT-Thread，LVGL UI + edge-impulse 猫叫模型。 |
| `UDP/UDP/key_camera/` | **board2 固件** | Infineon PSoC6 (CY8C624A)，RT-Thread，继电器水泵 + PTC06 串口摄像头。 |
| `docs/` | 设计文档 | 语音接入、猫叫喂水板间联动、联调说明等中文设计文档。 |
| `tools/` | 辅助脚本 | 构建/烧录/连热点的 PowerShell 脚本（OpenOCD 二进制本身未入库）。 |

> **注意已被 `.gitignore` 排除、需自行准备的内容：**
> - 云端 `.env`（含 API Key）、SQLite 数据库 `*.db`、运行时照片 `photos/`、**848MB 语音模型 `models/`**；
> - 前端 `node_modules/`、`dist/`；
> - 嵌入式构建产物（`build/`、`Debug/`、`*.elf`、`*.hex`）和工具链（`tools/` 下的 GCC/OpenOCD/Infineon 工具）。
>   这些请按官方渠道或下文说明自行获取。

---

## 3. 快速开始（组员拉取后如何跑起来）

### 3.0 前置条件

**硬件 / 网络**
- 一台 Windows PC 开启 **2.4GHz 热点**（board2 的 CYW43012 只能识别 2.4GHz）。
  - 默认 SSID/密码：`XiaoZhiLab` / `xiaozhi204`，PC 热点 IP **`192.168.137.1`**。
  - 若你的热点 IP / SSID 不同，需同步修改**两块板固件里硬编码的 WiFi 和服务器 IP**（见 §3.3 / §3.4）后重新烧录。
- 两块开发板均使用 **KitProg3** 调试器烧录（板载）。

**软件**
- Python **3.10+**、Node.js **18+**、Git。
- 嵌入式构建需 **RT-Thread Studio**（含 env 工具）+ 对应 GCC 工具链 + Infineon OpenOCD（见 §3.3 / §3.4）。

> 克隆仓库：
> ```bash
> git clone https://github.com/Kafuu7No/xiaozhi-server.git
> cd xiaozhi-server
> ```

---

### 3.1 云端 xiaozhi-server

```powershell
cd xiaozhi-server

# 1) 创建虚拟环境并装依赖
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt          # 含 torch/funasr，较大，耐心等
# 如需跑测试： pip install -r requirements-dev.txt

# 2) 配置环境变量
copy .env.example .env
#   编辑 .env，填入 DeepSeek API Key（用于本地 LLM 兜底；留空则用占位回显）
#   DEEPSEEK_API_KEY=sk-xxxx
#   语音上游可选： VOICE_UPSTREAM=official (默认, 转发官方小智云) | local (本地离线管线)

# 3) （仅当用本地语音管线 VOICE_UPSTREAM=local 时）下载 848MB 语音模型
#    模型不入库，需自行下载到 models/paraformer-zh/
#    脚本里的目标路径是绝对路径，请先按你的克隆位置修改 download_model.ps1 的 $dest
powershell -ExecutionPolicy Bypass -File .\download_model.ps1

# 4) 启动（⚠️ 不要用 run.py / --reload，见下方“常见坑”）
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

服务起来后监听：
- `:8000` HTTP + WebSocket（设备连接地址 `/xiaozhi/v1/?token=12345678`）
- UDP `:8848`（向 board2 下发命令）、TCP `:8849`（接收 board2 照片）、UDP `:58123`（设备发现）

> **Windows 防火墙**：首次需放行入站 `UDP 8848` 和 `TCP 8849`（管理员权限），否则 board2 收不到命令 / 传不回照片。

---

### 3.2 前端 xiaozhi-web

```powershell
cd xiaozhi-web
npm install
npm run dev            # Vite 跑在 :5173，自动把 /api 和 /photos 代理到 :8000
```

浏览器打开 http://localhost:5173 。修改源码后 HMR 热更新；改完用 `npx vite build` 验证能编译通过。

---

### 3.3 board1 固件（E84/M55，猫叫 + 温湿度 + 语音）

路径：`Edgi_Talk_M55_XiaoZhi_2/Edgi_Talk_M55_XiaoZhi/`

- **工具链**：必须 **GCC 10.3.1**（工程用 `-std=c++17`，旧版 5.4.1 编不过）。
  通常在 `<RT-ThreadStudio>\platform\env_released\env\tools\gnu_gcc\arm_gcc\mingw\bin`。
- **配置工具链路径**：编辑 `rtconfig.py` 的 `EXEC_PATH`（出厂是占位 `C:\Users\XXYYZZ`），改成上面的 gcc `bin`，或设置环境变量 `RTT_EXEC_PATH`。
- **构建**（scons，非 makefile）：设好 `RTT_EXEC_PATH` 和 `PATH` 后，在工程目录运行
  `python scons -j16`（env 自带 Python 2.7 + scons 3.1.2）。约 3 分钟，输出 `Debug/rtthread.hex`（~16MB）。
- **烧录**（OpenOCD，E84 目标，KitProg3）：
  - 必须用 **OpenOCD-Infineon 2.0.0**（含 `flm/cypress/cat1d` 外部 SMIF flash loader，否则烧 `0x60xxxxxx` 区会静默失败、verify 报错）。
  - board1 的 KitProg3 探针序列号 **`16231111022F2400`**（两块板共用厂商，必须指定对的序列号）。
  - 命令（在 OpenOCD-Infineon `2.0.0\bin` 下）：
    ```
    openocd -s ../scripts -s ../flm/cypress/cat1d -f interface/kitprog3.cfg \
      -c "adapter serial 16231111022F2400" -f target/infineon/pse84xgxs2.cfg \
      -c "program C:/Temp/fw1.hex verify reset exit"
    ```
  - E84 acquire 偶发失败（"Failed to clear CPU_WAIT"）属正常，**重试**第 2 次一般成功；必要时加 `-c "set ENABLE_CM55 0"`。
- 若 WiFi/服务器 IP 与默认不同，改固件里硬编码值后重烧。

> 自研代码主要在 `applications/xiaozhi/xiaozhi.cpp`（猫叫→喂水联动、状态同步）和 `ui/xiaozhi_ui.c`（LVGL 界面）。语音参数在 `xiaozhi_audio.cpp`（解码 24k/1ch、编码 16k/2ch，**勿改**）。

---

### 3.4 board2 固件（PSoC6，水泵 + 摄像头）

路径：`UDP/UDP/key_camera/`（**真身在此**；顶层 `key_camera/` 是 4 月过期副本，已不入库）

- **工具链**：ARM GCC 5.4.1（`<RT-ThreadStudio>\repo\Extract\ToolChain_Support_Packages\ARM\...\5.4.1\bin`）+ env 的 `make.exe`。
- **构建**：把工具链和 make 加进 PATH，在 `key_camera\Debug` 下 `make all` → 产出 `rtthread.elf/.hex`。
- **烧录**（KitProg3 / OpenOCD）：
  - board2 探针序列号 **`1A0F0F6900062400`**。
  - ```
    openocd -s <OpenOCD-Infineon\2.0.0\scripts> -f interface/kitprog3.cfg -f target/psoc6_2m.cfg \
      -c "program C:/Temp/fw.hex verify reset exit"
    ```
  - 把 hex 拷到短路径（如 `C:\Temp\fw.hex`），OpenOCD 打不开过长的 Desktop 路径。
  - 烧录前关掉 RT-Thread Studio（它会占用 KitProg3 探针）。
- 固件硬编码 WiFi + 服务器 IP `192.168.137.1`，改了需重烧。
- 串口日志 COM 口（115200），finsh 命令：`cmd_status`、`cmd_take_photo`、`reboot`。

---

## 4. 端口 / 通信速查

| 端口 | 协议 | 方向 | 用途 |
|------|------|------|------|
| 8000 | HTTP/WS | 浏览器、board1 ↔ 云端 | API + WebSocket（`/xiaozhi/v1/?token=12345678`） |
| 5173 | HTTP | 浏览器 ↔ 前端 | Vite dev（代理 `/api`、`/photos` → 8000） |
| 8848 | UDP | 云端/board1 → board2 | 命令：`0x01`拍照 / `0x10`喂水(不拍照) / `0x12`喂水+拍照 / `0x11`停泵 |
| 8849 | TCP | board2 → 云端 | 照片上传（`[4字节LE长度][JPEG]` 分帧） |
| 58123 | UDP | — | 设备发现 |

---

## 5. 常见坑（务必看）

- **云端启动别用 `run.py` 或 `--reload`**：reload 不释放 UDP 8848 / TCP 8849 socket，留下僵尸进程导致服务卡死（表现为板子「卡在初始化」、水泵/摄像头命令静默失败）。
  干净重启：杀掉所有 `python` 进程 → 确认 8000/8848/8849 端口空闲 → 重新跑不带 reload 的命令。
- **必须 2.4GHz 热点**：board2 的 WiFi 模块只识别 2.4GHz。
- **板子 IP 是 DHCP 动态的**：云端靠 `last_sender` + 按 MAC 的 ARP 解析定位 board2，不要假设固定 IP。
- **两块板共用 KitProg3 厂商**：烧录必须用对的探针序列号（board1 `16231111022F2400`，board2 `1A0F0F6900062400`），否则会烧错板。
- **语音断断续续**：不要在转发代理里对音频帧做「每帧 sleep 重定时」——会触发欠载。帧要立即转发。
- **照片不会自动清理**：`photos/` 里的图片只能在画廊里手动删，磁盘涨了需自行清理。

---

## 6. 技术栈

- **云端**：Python · FastAPI · uvicorn · SQLAlchemy(async) · aiosqlite · websockets · FunASR · OpenAI SDK · edge-tts
- **前端**：Vue 3 · Vite · Tailwind CSS 4 · daisyUI · Pinia · Vue Router · ECharts · axios
- **嵌入式**：RT-Thread · C/C++ · LVGL · edge-impulse(猫叫模型) · Infineon PSoC Edge E84 / PSoC6
