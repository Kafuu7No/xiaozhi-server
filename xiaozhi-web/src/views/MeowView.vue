<template>
  <div class="mx-auto max-w-6xl space-y-4">
    <div class="grid grid-cols-1 gap-4 xl:grid-cols-[1.7fr_1fr]">
      <div class="app-card">
        <div class="app-card-body">
          <div class="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div class="section-label">检测控制</div>
              <div class="mt-2 text-lg font-semibold text-slate-900">猫叫检测开关</div>
              <div class="mt-1 text-sm text-slate-400">
                当前状态：
                <span :class="detectionEnabled ? 'text-emerald-600' : 'text-slate-500'">
                  {{ detectionEnabled ? '运行中' : '已停止' }}
                </span>
                <span v-if="controlStatusText" class="ml-2 text-slate-400">{{ controlStatusText }}</span>
              </div>
            </div>

            <div class="flex flex-wrap gap-2">
              <button class="btn btn-primary btn-sm" :disabled="detectionEnabled" @click="setDetection(true)">
                启动检测
              </button>
              <button class="btn btn-outline btn-sm" :disabled="!detectionEnabled" @click="setDetection(false)">
                停止检测
              </button>
              <button class="btn btn-ghost btn-sm" @click="injectMock">插入模拟事件</button>
            </div>
          </div>
        </div>
      </div>

      <div class="app-card">
        <div class="app-card-body">
          <div class="section-label">今日统计</div>
          <div class="mt-3 text-4xl font-semibold text-slate-900">{{ stats.today_total ?? 0 }}</div>
          <div class="mt-2 text-sm text-slate-400">猫叫 {{ stats.today_cat ?? 0 }} · 噪声 {{ stats.today_noise ?? 0 }}</div>
          <div class="mt-4 flex gap-2 text-xs">
            <span class="rounded-full bg-blue-50 px-3 py-1 text-blue-600">猫叫 {{ stats.today_cat ?? 0 }}</span>
            <span class="rounded-full bg-emerald-50 px-3 py-1 text-emerald-600">噪声 {{ stats.today_noise ?? 0 }}</span>
          </div>
        </div>
      </div>
    </div>

    <div
      v-if="controlWarning"
      class="rounded-xl border border-amber-100 bg-amber-50 px-4 py-3 text-sm text-amber-700"
    >
      {{ controlWarning }}
    </div>

    <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <div class="app-card">
        <div class="app-card-body">
          <div class="mb-4">
            <div class="section-label">24 小时频率</div>
            <div class="mt-1 text-sm text-slate-400">按小时聚合最近 24 小时事件数</div>
          </div>
          <div ref="frequencyEl" class="h-72 w-full" />
        </div>
      </div>

      <div class="app-card">
        <div class="app-card-body">
          <div class="mb-4">
            <div class="section-label">置信度分布</div>
            <div class="mt-1 text-sm text-slate-400">只统计 {{ minConfidenceText }} 及以上事件，低分噪声已过滤</div>
          </div>
          <div ref="confidenceEl" class="h-72 w-full" />
        </div>
      </div>
    </div>

    <div class="app-card">
      <div class="app-card-body space-y-4">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div class="section-label">摄像头照片</div>
            <div class="mt-1 text-sm text-slate-400">点击「拍照」，设备会拍一张照片并上传。</div>
          </div>

          <div class="flex flex-wrap items-center gap-2">
            <button class="btn btn-primary btn-sm" :disabled="capturing" @click="capturePhoto">
              {{ capturing ? '拍照中…' : '拍照' }}
            </button>
          </div>
        </div>

        <div v-if="captureError" class="text-sm text-rose-500">{{ captureError }}</div>

        <div class="grid grid-cols-1 gap-4 xl:grid-cols-[1.5fr_1fr]">
          <div class="relative aspect-video overflow-hidden rounded-2xl bg-slate-950">
            <img
              v-if="latestPhoto"
              :src="latestPhoto.url"
              alt="Latest camera photo"
              class="h-full w-full object-contain"
            />
            <div
              v-else
              class="absolute inset-0 flex items-center justify-center bg-[radial-gradient(circle_at_top,_rgba(59,130,246,0.45),_transparent_38%),linear-gradient(135deg,_#0f172a,_#1e293b_55%,_#0b1120)] text-sm text-slate-300"
            >
              暂无照片，点击「拍照」获取
            </div>
          </div>

          <div class="rounded-2xl border border-slate-100 bg-slate-50 p-4">
            <div class="section-label">照片信息</div>
            <div class="mt-3 space-y-3 text-sm">
              <div class="flex items-center justify-between">
                <span class="text-slate-400">设备连接</span>
                <span :class="cameraDeviceConnected ? 'text-emerald-600' : 'text-slate-500'">
                  {{ cameraDeviceConnected ? '已连接' : '未连接' }}
                </span>
              </div>
              <div class="flex items-center justify-between">
                <span class="text-slate-400">拍摄时间</span>
                <span class="text-slate-900">{{ latestPhotoTime }}</span>
              </div>
              <div class="flex items-center justify-between">
                <span class="text-slate-400">设备 ID</span>
                <span class="text-slate-900">{{ latestPhoto?.device_id || '--' }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="app-card">
      <div class="app-card-body space-y-4">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div class="section-label">历史照片</div>
            <div class="mt-1 text-sm text-slate-400">共 {{ photosTotal }} 张 · 每页 15 张 · 点击查看大图 · 悬停右上角可删除</div>
          </div>
        </div>

        <div v-if="!photos.length" class="py-10 text-center text-sm text-slate-400">
          暂无历史照片
        </div>

        <div
          v-else
          class="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5"
        >
          <div
            v-for="photo in photos"
            :key="photo.id"
            class="group relative aspect-[4/3] cursor-pointer overflow-hidden rounded-xl border bg-slate-950 shadow-sm transition"
            :class="latestPhoto && latestPhoto.id === photo.id ? 'border-blue-500 ring-2 ring-blue-400' : 'border-slate-200 hover:border-blue-300 hover:shadow-md'"
            @click="selectPhoto(photo)"
          >
            <img :src="photo.url" :alt="photo.filename" class="h-full w-full object-cover" loading="lazy" />
            <span
              class="pointer-events-none absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/70 to-transparent px-2 py-1 text-[11px] leading-tight text-white"
            >
              {{ photo.captured_at?.replace('T', ' ').slice(5, 19) }}
            </span>
            <button
              type="button"
              class="absolute right-1.5 top-1.5 flex h-6 w-6 items-center justify-center rounded-full bg-black/55 text-white opacity-0 transition hover:bg-rose-500 group-hover:opacity-100"
              title="删除这张照片"
              @click.stop="removePhoto(photo)"
            >
              ✕
            </button>
          </div>
        </div>

        <div v-if="photosPages > 1" class="flex items-center justify-end gap-2 text-sm">
          <button class="btn btn-ghost btn-sm" :disabled="photosPage <= 1" @click="gotoPhotosPage(photosPage - 1)">上一页</button>
          <span class="text-slate-500">第 {{ photosPage }} / {{ photosPages }} 页</span>
          <button class="btn btn-ghost btn-sm" :disabled="photosPage >= photosPages" @click="gotoPhotosPage(photosPage + 1)">下一页</button>
        </div>
      </div>
    </div>

    <!-- 删除照片确认弹窗 -->
    <div
      v-if="pendingDeletePhoto"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      @click.self="cancelDelete"
    >
      <div class="w-full max-w-sm overflow-hidden rounded-2xl bg-white shadow-xl">
        <div class="aspect-[4/3] w-full bg-slate-950">
          <img :src="pendingDeletePhoto.url" :alt="pendingDeletePhoto.filename" class="h-full w-full object-contain" />
        </div>
        <div class="space-y-3 p-5">
          <div class="text-base font-semibold text-slate-900">删除这张照片？</div>
          <div class="text-sm text-slate-500">
            拍摄于 {{ pendingDeletePhoto.captured_at?.replace('T', ' ').slice(0, 19) }}，删除后不可恢复。
          </div>
          <div class="flex justify-end gap-2 pt-1">
            <button class="btn btn-ghost btn-sm" @click="cancelDelete">取消</button>
            <button class="btn btn-error btn-sm text-white" @click="confirmDelete">删除</button>
          </div>
        </div>
      </div>
    </div>

    <div class="app-card">
      <div class="app-card-body">
        <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <div class="section-label">事件列表</div>
            <div class="mt-1 text-sm text-slate-400">云端按阈值重新判定猫叫，低于 {{ minConfidenceText }} 不进入统计</div>
          </div>

          <div class="flex flex-wrap items-center gap-2">
            <div class="tabs tabs-boxed bg-slate-100 p-1">
              <button
                v-for="tab in eventTabs"
                :key="tab.value"
                class="tab h-8 min-h-8 gap-2 rounded-md px-3 text-xs"
                :class="filterType === tab.value ? 'tab-active bg-white text-slate-900 shadow-sm' : 'text-slate-500'"
                @click="filterType = tab.value"
              >
                {{ tab.label }}
                <span class="rounded-full bg-slate-200 px-1.5 py-0.5 text-[11px] leading-none text-slate-600">
                  {{ tab.count }}
                </span>
              </button>
            </div>
            <select v-model="filterHours" class="select select-bordered select-sm" @change="load">
              <option :value="24">近 24 小时</option>
              <option :value="48">近 48 小时</option>
              <option :value="168">近 7 天</option>
            </select>
          </div>
        </div>

        <div v-if="!filteredEvents.length" class="py-12 text-center text-sm text-slate-400">
          暂无检测事件，可先插入一条 mock 数据。
        </div>

        <div v-else class="max-h-[28rem] overflow-auto rounded-xl border border-slate-100">
          <table class="table">
            <thead class="sticky top-0 z-10 bg-white">
              <tr class="text-slate-400">
                <th>时间</th>
                <th>score</th>
                <th>判定</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="event in filteredEvents" :key="event.id ?? event.ts ?? event.recorded_at">
                <td class="text-sm text-slate-500">{{ formatEventTime(event) }}</td>
                <td>
                  <div class="flex items-center gap-3">
                    <div class="h-2 w-28 overflow-hidden rounded-full bg-slate-100">
                      <div
                        class="h-full rounded-full"
                        :class="event.is_cat ? 'bg-[#3B82F6]' : 'bg-[#10B981]'"
                        :style="{ width: `${Math.min(100, event.score * 100)}%` }"
                      />
                    </div>
                    <span class="text-sm text-slate-500">{{ (event.score * 100).toFixed(0) }}%</span>
                  </div>
                </td>
                <td>
                  <span
                    class="badge border-0"
                    :class="event.is_cat ? 'bg-blue-50 text-blue-600' : 'bg-emerald-50 text-emerald-600'"
                  >
                    {{ event.is_cat ? '猫叫' : '噪声' }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import * as echarts from 'echarts/core'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { BarChart } from 'echarts/charts'
import { SVGRenderer } from 'echarts/renderers'
import { useApi } from '../composables/useApi'
import { useDeviceStore } from '../stores/deviceStore'

echarts.use([BarChart, GridComponent, TooltipComponent, SVGRenderer])

const api = useApi()
const store = useDeviceStore()

const events = ref([])
const chartEvents = ref([])
const stats = ref({
  today_total: 0,
  today_cat: 0,
  today_noise: 0,
  detection_enabled: false,
  desired_enabled: false,
  device_enabled: false,
  control_status: 'stopped',
  control_message: '',
  control_result: null,
  control_updated_at: null,
  min_confidence: 0.4,
})
const filterType = ref('all')
const filterHours = ref(24)
const latestPhoto = ref(null)
const photos = ref([])
const photosPage = ref(1)
const photosPages = ref(1)
const photosTotal = ref(0)
const pendingDeletePhoto = ref(null)
const cameraDeviceConnected = ref(false)
const capturing = ref(false)
const captureError = ref('')
const seenMeowEventKeys = new Set()
let refreshTimer = null

const detectionEnabled = computed(() => stats.value.detection_enabled)
const controlStatusText = computed(() => {
  if (stats.value.control_status === 'command_sent') return '等待板端确认'
  if (stats.value.control_status === 'running') return '板端已确认'
  if (stats.value.control_status === 'device_offline') return '设备离线'
  if (stats.value.control_result && stats.value.control_result !== 0) return `错误 ${stats.value.control_result}`
  return ''
})
const controlWarning = computed(() => {
  if (stats.value.control_status === 'device_offline') return '设备当前离线，猫叫检测指令没有发送到板端。'
  if (stats.value.desired_enabled && !stats.value.device_enabled && stats.value.control_status !== 'command_sent') {
    const message = stats.value.control_message || 'start_failed'
    return `板端没有成功启动猫叫检测：${message}`
  }
  return ''
})
const latestPhotoTime = computed(() => {
  if (!latestPhoto.value?.captured_at) return '--'
  return latestPhoto.value.captured_at.replace('T', ' ').slice(0, 19)
})
const minConfidence = computed(() => stats.value.min_confidence ?? 0.4)
const minConfidenceText = computed(() => `${(minConfidence.value * 100).toFixed(0)}%`)
const visibleEvents = computed(() => events.value.filter((event) => Number(event.score) >= minConfidence.value))
const filteredEvents = computed(() => {
  if (filterType.value === 'cat') return visibleEvents.value.filter((event) => event.is_cat)
  if (filterType.value === 'noise') return visibleEvents.value.filter((event) => !event.is_cat)
  return visibleEvents.value
})
const eventTabs = computed(() => [
  { value: 'all', label: '全部', count: visibleEvents.value.length },
  { value: 'cat', label: '猫叫', count: visibleEvents.value.filter((event) => event.is_cat).length },
  { value: 'noise', label: '噪声', count: visibleEvents.value.filter((event) => !event.is_cat).length },
])
const chartVisibleEvents = computed(() => chartEvents.value.filter((event) => Number(event.score) >= minConfidence.value))
const minConfidenceBucketLabel = computed(() => `${Math.round(minConfidence.value * 100)}-60%`)

function isAcceptedEvent(event) {
  return Number(event?.score) >= minConfidence.value
}

watch(
  () => store.recentMeowEvents,
  (recentEvents) => {
    if (!recentEvents.length) return
    const knownList = new Set(events.value.map(eventKey))
    const incoming = uniqueByEventKey(recentEvents.filter((event) => isAcceptedEvent(event) && !knownList.has(eventKey(event))))
    if (incoming.length) {
      events.value = [...incoming, ...events.value]
        .sort((left, right) => eventTime(left) - eventTime(right))
        .reverse()
        .slice(0, 200)
      for (const event of incoming) {
        applyMeowStatsEvent(event)
      }
    }

    const knownCharts = new Set(chartEvents.value.map(eventKey))
    const incomingCharts = uniqueByEventKey(recentEvents.filter((event) => isAcceptedEvent(event) && !knownCharts.has(eventKey(event))))
    if (incomingCharts.length) {
      chartEvents.value = [...incomingCharts, ...chartEvents.value]
        .sort((left, right) => eventTime(left) - eventTime(right))
        .reverse()
        .slice(0, 200)
    }
  },
  { deep: true },
)

watch(
  () => store.meowStatus,
  (status) => {
    if (!status) return
    stats.value = { ...stats.value, ...status, detection_enabled: !!status.device_enabled }
  },
  { deep: true },
)

const frequencyEl = ref(null)
const confidenceEl = ref(null)
let frequencyChart = null
let confidenceChart = null

function eventKey(event) {
  return event.id ?? event.ts ?? event.recorded_at
}

function uniqueByEventKey(events) {
  const seen = new Set()
  return events.filter((event) => {
    const key = eventKey(event)
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

function eventTime(event) {
  if (typeof event?.ts === 'number') return event.ts
  if (event?.recorded_at) return Date.parse(event.recorded_at)
  return 0
}

function isToday(value) {
  if (!value) return false
  const date = new Date(value)
  const today = new Date()
  return date.getFullYear() === today.getFullYear()
    && date.getMonth() === today.getMonth()
    && date.getDate() === today.getDate()
}

function applyMeowStatsEvent(event) {
  if (!isToday(eventTime(event))) return
  stats.value = {
    ...stats.value,
    today_total: (stats.value.today_total ?? 0) + 1,
    today_cat: (stats.value.today_cat ?? 0) + (event.is_cat ? 1 : 0),
    today_noise: (stats.value.today_noise ?? 0) + (event.is_cat ? 0 : 1),
  }
}

function buildHourlySeries() {
  const buckets = []
  const now = Date.now()
  for (let offset = 23; offset >= 0; offset -= 1) {
    const start = new Date(now - offset * 3600_000)
    start.setMinutes(0, 0, 0)
    buckets.push({ label: `${String(start.getHours()).padStart(2, '0')}:00`, start: start.getTime(), count: 0 })
  }

  for (const event of chartVisibleEvents.value) {
    const value = eventTime(event)
    for (const bucket of buckets) {
      if (value >= bucket.start && value < bucket.start + 3600_000) {
        bucket.count += 1
        break
      }
    }
  }

  return {
    labels: buckets.map((bucket) => bucket.label),
    values: buckets.map((bucket) => bucket.count),
  }
}

function buildConfidenceSeries() {
  const buckets = [
    { label: minConfidenceBucketLabel.value, count: 0, min: minConfidence.value, max: 0.6 },
    { label: '60-70%', count: 0, min: 0.6, max: 0.7 },
    { label: '70-80%', count: 0, min: 0.7, max: 0.8 },
    { label: '80-90%', count: 0, min: 0.8, max: 0.9 },
    { label: '90-100%', count: 0, min: 0.9, max: 1.01 },
  ]

  for (const event of chartVisibleEvents.value) {
    const target = buckets.find((bucket) => event.score >= bucket.min && event.score < bucket.max)
    if (target) target.count += 1
  }

  return {
    labels: buckets.map((bucket) => bucket.label),
    values: buckets.map((bucket) => bucket.count),
  }
}

function buildChartOption({ labels, values }, color) {
  return {
    animation: false,
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#ffffff',
      borderColor: '#E2E8F0',
      borderWidth: 1,
      textStyle: { color: '#334155', fontSize: 12 },
    },
    grid: { left: 36, right: 16, top: 16, bottom: 28 },
    xAxis: {
      type: 'category',
      data: labels,
      axisLine: { lineStyle: { color: '#E2E8F0' } },
      axisTick: { show: false },
      axisLabel: { color: '#94A3B8', fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#94A3B8', fontSize: 11 },
      splitLine: { lineStyle: { color: '#E2E8F0', type: 'dashed' } },
    },
    series: [
      {
        type: 'bar',
        barWidth: '46%',
        data: values,
        itemStyle: {
          color,
          borderRadius: [6, 6, 0, 0],
        },
      },
    ],
  }
}

function ensureCharts() {
  if (frequencyEl.value && !frequencyChart) {
    frequencyChart = echarts.getInstanceByDom(frequencyEl.value) ?? echarts.init(frequencyEl.value, null, { renderer: 'svg' })
  }
  if (confidenceEl.value && !confidenceChart) {
    confidenceChart = echarts.getInstanceByDom(confidenceEl.value) ?? echarts.init(confidenceEl.value, null, { renderer: 'svg' })
  }
}

function refreshCharts() {
  ensureCharts()
  frequencyChart?.setOption(buildChartOption(buildHourlySeries(), '#3B82F6'), { notMerge: true })
  confidenceChart?.setOption(buildChartOption(buildConfidenceSeries(), '#10B981'), { notMerge: true })
}

async function load() {
  try {
    const [nextEvents, nextChartEvents, nextStats, cameraResult] = await Promise.all([
      api.getMeowEvents(filterHours.value),
      api.getMeowEvents(24),
      api.getMeowStats(),
      api.getLatestPhoto(),
      loadPhotos(),
    ])
    events.value = nextEvents
    chartEvents.value = nextChartEvents
    seenMeowEventKeys.clear()
    nextEvents.forEach((event) => seenMeowEventKeys.add(eventKey(event)))
    nextChartEvents.forEach((event) => seenMeowEventKeys.add(eventKey(event)))
    stats.value = nextStats
    store.setMeowStatus(nextStats)
    // 优先显示用户点选的照片；否则跟随最新一张
    latestPhoto.value = cameraResult.photo ?? photos.value[0] ?? null
    cameraDeviceConnected.value = cameraResult.device_connected
    await nextTick()
    refreshCharts()
  } catch (error) {
    console.error('Failed to load meow data', error)
  }
}

async function setDetection(enabled) {
  try {
    const result = await api.setMeowControl(enabled ? 'start' : 'stop')
    stats.value = { ...stats.value, ...result }
    store.setMeowStatus(result)
  } catch (error) {
    console.error('Failed to set meow detection state', error)
  }
}

async function loadPhotos(page = photosPage.value) {
  const result = await api.getPhotos(page, 15)
  photos.value = result.photos ?? []
  photosPage.value = result.page ?? 1
  photosPages.value = result.pages ?? 1
  photosTotal.value = result.total ?? 0
}

function gotoPhotosPage(page) {
  loadPhotos(Math.max(1, Math.min(page, photosPages.value)))
}

async function pollForNewPhoto(timeoutMs = 50000, intervalMs = 2000) {
  const previousId = latestPhoto.value?.id ?? null
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, intervalMs))
    const result = await api.getLatestPhoto()
    cameraDeviceConnected.value = result.device_connected
    if (result.photo && result.photo.id !== previousId) {
      latestPhoto.value = result.photo
      await loadPhotos(1)
      return
    }
  }
  captureError.value = '已发送拍照指令，摄像头上传较慢（约40秒），稍后会自动出现在下方相册'
}

function selectPhoto(photo) {
  latestPhoto.value = photo
}

function removePhoto(photo) {
  pendingDeletePhoto.value = photo
}

function cancelDelete() {
  pendingDeletePhoto.value = null
}

async function confirmDelete() {
  const photo = pendingDeletePhoto.value
  if (!photo) return
  try {
    await api.deletePhoto(photo.id)
    if (latestPhoto.value && latestPhoto.value.id === photo.id) {
      latestPhoto.value = null
    }
    await loadPhotos()
    if (!photos.value.length && photosPage.value > 1) {
      await loadPhotos(photosPage.value - 1)
    }
    if (!latestPhoto.value) {
      latestPhoto.value = photos.value[0] ?? null
    }
  } catch (error) {
    console.error('Failed to delete photo', error)
  } finally {
    pendingDeletePhoto.value = null
  }
}

async function capturePhoto() {
  capturing.value = true
  captureError.value = ''
  try {
    await api.triggerCapture()
    await pollForNewPhoto()
  } catch (error) {
    captureError.value = error?.response?.data?.detail || '拍照失败，请检查设备是否在线'
    console.error('Failed to capture photo', error)
  } finally {
    capturing.value = false
  }
}

async function injectMock() {
  const event = await api.mockMeow()
  store.addMeowEvent(event)
  await load()
}

function formatEventTime(event) {
  const p = (n) => String(n).padStart(2, '0')
  if (typeof event?.ts === 'number') {
    const d = new Date(event.ts)
    if (Number.isNaN(d.getTime())) return '--'
    return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
  }
  if (event?.recorded_at) {
    return event.recorded_at.replace('T', ' ').slice(5, 19)
  }
  return '--'
}

const onResize = () => {
  frequencyChart?.resize()
  confidenceChart?.resize()
}

watch(chartEvents, async () => {
  await nextTick()
  refreshCharts()
}, { deep: true })

onMounted(async () => {
  await load()
  refreshTimer = window.setInterval(load, 10_000)
  window.addEventListener('resize', onResize)
})

onUnmounted(() => {
  if (refreshTimer) window.clearInterval(refreshTimer)
  window.removeEventListener('resize', onResize)
  try {
    frequencyChart?.dispose()
  } catch {}
  try {
    confidenceChart?.dispose()
  } catch {}
  frequencyChart = null
  confidenceChart = null
})
</script>
