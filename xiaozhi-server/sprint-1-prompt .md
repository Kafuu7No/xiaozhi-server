# Sprint 1：UI 重构 + 设备监控 + IoT 控制

## 概述

对 xiaozhi-web 前端进行完整的 UI 重构。当前 UI 质量差（emoji 图标廉价、顶部导航手机端不适配、整体 AI 味蓝紫渐变）。

**目标风格：** 专业级 IoT 后台管理界面。参考你安装的 frontend-design skill 中的设计规范。风格要求：干净、克制、数据驱动。不要蓝紫渐变，不要 AI 味。

**不要修改后端代码，只改前端。**

---

## 第一步：安装依赖 + 配置 DaisyUI

```bash
cd xiaozhi-web
npm install lucide-vue-next daisyui@latest
```

修改 `src/style.css`，在 tailwind import 之后添加 DaisyUI 引入和主题配置：

```css
@import "tailwindcss";
@plugin "daisyui" {
  themes: corporate --default;
}
```

**使用 `corporate` 主题。** 这是一个商务风格主题，配色沉稳不花哨，适合 IoT 后台。不要使用 cyberpunk、retro、cupcake 等花哨主题。

DaisyUI 可用的组件类名参考（只列出本项目会用到的）：
- `btn btn-primary` / `btn btn-ghost` / `btn btn-sm` — 按钮
- `card` / `card-body` — 卡片容器
- `badge badge-success` / `badge-warning` / `badge-error` — 小标签
- `range range-primary range-sm` — 滑块
- `stat` / `stat-title` / `stat-value` / `stat-desc` — 统计数值
- `menu` / `menu-item` — 侧边栏菜单
- `navbar` — 顶栏
- `toggle` — 开关
- `tooltip` — 提示
- `alert` — 提示横幅
- `table` — 表格

**重要：DaisyUI 的类名和 Tailwind 原子类可以混合使用。** 例如 `<div class="card bg-base-100 border border-base-300 p-5">` 完全合法。

---

## 第二步：布局重构 — 侧边栏导航

### 2.1 删除现有的 NavBar.vue 和 BottomNav.vue

### 2.2 新建 `src/layout/AppLayout.vue`

全局布局结构：

```
桌面端 (lg+)：
┌──────────┬──────────────────────────────────┐
│  侧边栏   │  顶栏：页面标题 + 设备状态徽标     │
│  240px   ├──────────────────────────────────┤
│  固定     │                                  │
│          │    <router-view /> 主内容           │
│  Logo    │                                  │
│  菜单     │                                  │
│  设备状态  │                                  │
└──────────┴──────────────────────────────────┘

手机端 (<lg)：
┌──────────────────────────────────────────────┐
│  顶栏：汉堡按钮 + 页面标题 + 设备状态          │
├──────────────────────────────────────────────┤
│                                              │
│    <router-view /> 主内容                      │
│                                              │
└──────────────────────────────────────────────┘
点击汉堡按钮 → DaisyUI drawer 从左侧滑出侧边栏
```

**侧边栏实现：用 DaisyUI 的 `drawer` 组件。** 桌面端自动常驻（`lg:drawer-open`），手机端变成抽屉。

```html
<div class="drawer lg:drawer-open">
  <input id="sidebar" type="checkbox" class="drawer-toggle" />
  <div class="drawer-content flex flex-col">
    <!-- 顶栏 -->
    <div class="navbar bg-base-100 border-b border-base-300 px-6">
      <label for="sidebar" class="btn btn-ghost btn-sm lg:hidden">
        <Menu :size="20" />
      </label>
      <div class="flex-1">
        <h1 class="text-lg font-semibold">{{ route.meta.title }}</h1>
      </div>
      <div class="hidden lg:flex items-center gap-2 text-sm text-base-content/60">
        <span class="w-2 h-2 rounded-full" :class="connected ? 'bg-success' : 'bg-base-300'"></span>
        {{ connected ? '设备在线' : '设备离线' }}
      </div>
    </div>
    <!-- 主内容 -->
    <main class="flex-1 p-4 lg:p-6 bg-base-200 min-h-screen">
      <slot />
    </main>
  </div>
  <div class="drawer-side z-40">
    <label for="sidebar" class="drawer-overlay"></label>
    <!-- 侧边栏 -->
    <aside class="w-60 min-h-full bg-base-100 border-r border-base-300 flex flex-col">
      <!-- Logo -->
      <!-- 菜单 -->
      <!-- 设备状态 -->
    </aside>
  </div>
</div>
```

### 2.3 侧边栏内容

Logo 区域 + 菜单 + 底部设备状态。

菜单项列表：

| lucide 图标名 | 文字 | 路由 |
|---|---|---|
| LayoutDashboard | 主控台 | / |
| Thermometer | 温湿度 | /sensor |
| Cat | 猫叫检测 | /meow |
| Sliders | IoT 控制 | /iot |
| Droplets | 饮水管理 | /water |
| Settings | 系统设置 | /settings |

用 DaisyUI `menu` 组件。当前路由菜单项高亮用 `active` 类。

侧边栏底部固定设备状态：绿色/灰色小圆点 + "设备在线/离线" 文字。

---

## 第三步：全局样式规范

- **全部使用 DaisyUI 语义色名**，禁止硬编码颜色（如 `text-blue-600`）。用 `text-primary`、`bg-success`、`text-base-content/50` 等。
- 唯一例外：LED 颜色按钮（`bg-red-500` 等）和 ECharts 图表内部颜色值。
- 所有卡片：`card bg-base-100 border border-base-300`，不用 shadow。
- 所有图标来自 lucide-vue-next，禁止 emoji。
- 图标尺寸：菜单 18px，卡片标题 20px，统计面板 24px。

---

## 第四步：重构每个页面

### 4.1 主控台 DashboardView.vue

**顶部 4 个统计卡片（`grid grid-cols-2 lg:grid-cols-4 gap-4`）：**

每张卡片结构：左侧一个 40x40 圆角色块（内含白色 lucide 图标），右侧数值 + 标签。

| 卡片 | 图标 | 色块颜色 | 数值 | 标签 |
|---|---|---|---|---|
| 设备状态 | Wifi / WifiOff | 在线 `bg-success/10 text-success`，离线 `bg-base-200 text-base-content/30` | "在线"/"离线" | 设备状态 |
| 温度 | Thermometer | `bg-info/10 text-info` | 25.7°C | 当前温度 |
| 湿度 | Droplets | `bg-accent/10 text-accent` | 47.9% | 当前湿度 |
| 今日猫叫 | Cat | `bg-warning/10 text-warning` | 8 | 24h 检测 |

**中部 2 列图表（`grid grid-cols-1 lg:grid-cols-2 gap-4 mt-4`）：**
- 左：温湿度趋势折线图（ECharts，近 8 小时）
- 右：猫叫统计柱状图（24h / 48h / 周）

**底部：最近 5 条猫叫事件表格。** 用 DaisyUI `table table-sm`。置信度用 `progress` 组件。判定用 `badge badge-success`（猫叫）或 `badge badge-ghost`（噪声）。

**模拟按钮**放页面最底部，极淡样式：`btn btn-ghost btn-xs text-base-content/30`。

### 4.2 温湿度页面 SensorView.vue

**顶部报警横幅**（超阈值时显示）：`alert alert-error`。

**2 个大数值卡片**（md 2 列，手机 1 列）：当前温度 / 当前湿度。数值用 `text-4xl font-bold`。下方小字显示较 1 小时前的变化（↑+0.3°C / ↓-2.1%）。

**ECharts 折线图**：双 Y 轴，温度蓝色线 + 湿度绿色线。右上角下拉选择时间范围（6h / 24h / 7d）。

### 4.3 猫叫检测页面 MeowView.vue

**顶部 3 个统计卡片**（24h / 48h / 本周）。

**中部 2 列图表**：左趋势折线图，右置信度分布饼图。

**底部事件列表** + 右上角筛选下拉（全部 / 仅猫叫 / 仅噪声）。

### 4.4 IoT 控制页面 IotControlView.vue

**顶部设备状态横幅**：在线 `alert alert-success`，离线 `alert alert-warning`。

**3 个控制卡片（`grid grid-cols-1 lg:grid-cols-3 gap-4`）：**

**Speaker 卡片**：图标 Volume2 + 标题 "Speaker"。音量滑块 `range range-primary range-sm`，显示当前值。@change 调用 `POST /api/iot/command`，body: `{"device_name":"Speaker","method":"SetVolume","parameters":{"volume":70}}`。

**Screen 卡片**：图标 Monitor + 标题 "Screen"。亮度滑块 + 表情选择网格（6 个文字按钮：neutral / happy / sad / angry / laughing / sleepy）。选中态 `btn-primary`，未选 `btn-ghost border border-base-300`。@click 调用 API，body: `{"device_name":"Screen","method":"SetEmoji","parameters":{"emoji":"happy"}}`。

**Led 卡片**：图标 Lightbulb + 标题 "Led"。5 个 40x40 圆角色块按钮（红/绿/蓝/全亮/关）。选中态加 `ring-2 ring-offset-2`。下方小字标注颜色名。@click 调用 API，body: `{"device_name":"Led","method":"SetLed","parameters":{"color":"red"}}`。

### 4.5 饮水管理页面 WaterView.vue

居中空状态卡片：Droplets 图标 + "饮水管理" + "水泵硬件暂未接入" + 虚线边框区域列出未来功能。

### 4.6 设置页面 SettingsView.vue

每项设置一个卡片行。左侧标签+说明，右侧控件。保存按钮 `btn btn-primary`。

---

## 第五步：ECharts 配色

```javascript
const chartColors = {
  temperature: '#3b82f6',
  humidity: '#22c55e',
  meow: '#f59e0b',
  areaFill: 'rgba(59, 130, 246, 0.08)',
  grid: '#e2e8f0',
  text: '#64748b',
}
```

---

## 第六步：响应式验证

浏览器 DevTools 切 375px 宽，逐页检查侧边栏抽屉、卡片网格、图表自适应、表格滚动。

---

## 禁止事项

- 不要安装 Element Plus / Ant Design Vue / Naive UI
- 不要使用任何 emoji
- 不要修改后端代码
- 不要改 API 路径
- 不要用 shadow-lg / shadow-xl
- 不要硬编码颜色（LED 按钮和 ECharts 除外）
- 不要使用蓝紫渐变背景
