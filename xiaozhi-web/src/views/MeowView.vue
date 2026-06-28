<template>
  <div class="page-shell">
    <template v-if="uiStore.isControlMode">
      <div class="grid grid-cols-1 gap-4 xl:grid-cols-[1.4fr_1fr]">
        <div class="app-card">
          <div class="app-card-body">
            <div class="flex flex-wrap items-start justify-between gap-4">
              <div>
                <div class="section-label">猫叫记录开关</div>
                <div class="mt-2 text-lg font-semibold text-[#17211b]">是否记录猫叫</div>
                <div class="mt-1 text-sm text-[#789083]">
                  当前状态：
                  <span :class="detectionEnabled ? 'text-emerald-600' : 'text-[#66756d]'">
                    {{ detectionEnabled ? '运行中' : '已停止' }}
                  </span>
                  <span v-if="controlStatusText" class="ml-2 text-[#789083]">{{ controlStatusText }}</span>
                </div>
                <div class="mt-1 text-sm text-[#789083]">停止后不会记录猫叫，也不会触发猫叫相关联动。</div>
              </div>

              <div class="flex flex-wrap gap-2">
                <button class="btn btn-primary btn-sm" :disabled="detectionEnabled" @click="setDetection(true)">
                  开始记录
                </button>
                <button class="btn btn-outline btn-sm" :disabled="!detectionEnabled" @click="setDetection(false)">
                  暂停记录
                </button>
                <button v-if="isDev" class="btn btn-ghost btn-sm" @click="injectMock">调试：添加模拟记录</button>
              </div>
            </div>
          </div>
        </div>

        <div class="app-card">
          <div class="app-card-body">
            <div class="section-label">今日统计</div>
            <div class="mt-3 text-4xl font-semibold text-[#17211b]">{{ stats.today_total ?? 0 }}</div>
            <div class="mt-2 text-sm text-[#789083]">
              猫叫 {{ stats.today_cat ?? 0 }} · 噪声 {{ stats.today_noise ?? 0 }}
            </div>
          </div>
        </div>
      </div>

      <div
        v-if="controlWarning"
        class="rounded-lg border border-amber-100 bg-amber-50 px-4 py-3 text-sm text-amber-700"
      >
        {{ controlWarning }}
      </div>

      <div class="app-card">
        <div class="app-card-body space-y-4">
          <div class="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div class="section-label">摄像头照片</div>
              <div class="mt-1 text-sm text-[#789083]">拍照后显示最新上传结果，可删除当前照片。</div>
            </div>

            <div class="flex flex-wrap items-center gap-2">
              <button class="btn btn-primary btn-sm" :disabled="capturing" @click="capturePhoto">
                {{ capturing ? '拍照中...' : '拍照' }}
              </button>
              <button
                class="btn btn-ghost btn-sm text-red-500"
                :disabled="!latestPhoto"
                @click="removePhoto(latestPhoto)"
              >
                删除当前照片
              </button>
            </div>
          </div>

          <div v-if="captureError" class="text-sm text-rose-500">{{ captureError }}</div>

          <div class="grid grid-cols-1 gap-4 xl:grid-cols-[1.5fr_1fr]">
            <div class="relative aspect-video overflow-hidden rounded-lg bg-slate-950">
              <img
                v-if="latestPhoto"
                :src="latestPhoto.url"
                alt="Latest camera photo"
                class="h-full w-full object-contain"
              />
              <div
                v-else
                class="absolute inset-0 flex items-center justify-center bg-slate-900 text-sm text-slate-300"
              >
                暂无照片，点击“拍照”获取
              </div>
            </div>

            <div class="rounded-lg border border-[#dce8de] bg-[#f7fbf7] p-4">
              <div class="section-label">照片信息</div>
              <div class="mt-3 space-y-3 text-sm">
                <div class="flex items-center justify-between">
                  <span class="text-[#789083]">设备连接</span>
                  <span :class="cameraDeviceConnected ? 'text-emerald-600' : 'text-[#66756d]'">
                    {{ cameraDeviceConnected ? '已连接' : '未连接' }}
                  </span>
                </div>
                <div class="flex items-center justify-between">
                  <span class="text-[#789083]">拍摄时间</span>
                  <span class="text-[#17211b]">{{ latestPhotoTime }}</span>
                </div>
                <div class="flex items-center justify-between">
                  <span class="text-[#789083]">设备 ID</span>
                  <span class="text-[#17211b]">{{ latestPhoto?.device_id || '--' }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <template v-else>
      <section class="product-panel p-5 lg:p-6">
        <div class="grid gap-5 lg:grid-cols-[1.15fr_0.85fr] lg:items-center">
          <div>
            <div class="status-chip">
              <span
                class="h-2.5 w-2.5 rounded-full"
                :class="stats.today_cat ? 'bg-[#2f80b7]' : 'bg-[#2f8f6b]'"
              />
              声音观察
            </div>
            <h1 class="mt-4 text-2xl font-semibold text-[#17211b] lg:text-3xl">{{ meowSummaryTitle }}</h1>
            <p class="mt-2 max-w-2xl text-sm leading-6 text-[#66756d]">{{ meowSummaryText }}</p>
          </div>
          <div class="grid grid-cols-3 gap-3">
            <div class="soft-panel px-3 py-4">
              <div class="section-label">总事件</div>
              <div class="mt-2 text-2xl font-semibold text-[#17211b]">{{ stats.today_total ?? 0 }}</div>
            </div>
            <div class="soft-panel px-3 py-4">
              <div class="section-label">猫叫</div>
              <div class="mt-2 text-2xl font-semibold text-[#2f80b7]">{{ stats.today_cat ?? 0 }}</div>
            </div>
            <div class="soft-panel px-3 py-4">
              <div class="section-label">噪声</div>
              <div class="mt-2 text-2xl font-semibold text-[#2f8f6b]">{{ stats.today_noise ?? 0 }}</div>
            </div>
          </div>
        </div>
      </section>

      <div class="grid grid-cols-1 gap-4 xl:grid-cols-[1.7fr_1fr]">
        <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div class="app-card">
            <div class="app-card-body">
              <div class="mb-4">
                <div class="section-label">24 小时频率</div>
                <div class="mt-1 text-sm text-[#789083]">按小时聚合最近 24 小时事件数</div>
              </div>
              <div class="relative h-72 w-full">
                <div ref="frequencyEl" class="h-full w-full" />
                <div
                  v-if="!chartVisibleEvents.length"
                  class="absolute inset-0 flex items-center justify-center text-sm text-[#789083]"
                >
                  暂无声音频率数据
                </div>
              </div>
            </div>
          </div>

          <div class="app-card">
            <div class="app-card-body">
              <div class="mb-4">
                <div class="section-label">识别把握度</div>
                <div class="mt-1 text-sm text-[#789083]">
                  越高越像真实猫叫，只统计 {{ minConfidenceText }} 及以上记录。
                </div>
              </div>
              <div class="relative h-72 w-full">
                <div ref="confidenceEl" class="h-full w-full" />
                <div
                  v-if="!chartVisibleEvents.length"
                  class="absolute inset-0 flex items-center justify-center text-sm text-[#789083]"
                >
                  暂无识别把握度数据
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="app-card">
          <div class="app-card-body">
            <div class="section-label">今日统计</div>
            <div class="mt-3 text-4xl font-semibold text-[#17211b]">{{ stats.today_total ?? 0 }}</div>
            <div class="mt-2 text-sm text-[#789083]">
              猫叫 {{ stats.today_cat ?? 0 }} · 噪声 {{ stats.today_noise ?? 0 }}
            </div>
            <div class="mt-4 flex gap-2 text-xs">
              <span class="rounded-full bg-blue-50 px-3 py-1 text-blue-600">猫叫 {{ stats.today_cat ?? 0 }}</span>
              <span class="rounded-full bg-emerald-50 px-3 py-1 text-emerald-600">噪声 {{ stats.today_noise ?? 0 }}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="app-card">
        <div class="app-card-body space-y-4">
          <div>
            <div class="section-label">最新照片</div>
            <div class="mt-1 text-sm text-[#789083]">查看设备最近上传的画面</div>
          </div>

          <div class="grid grid-cols-1 gap-4 xl:grid-cols-[1.5fr_1fr]">
            <div class="relative aspect-video overflow-hidden rounded-lg bg-slate-950">
              <img
                v-if="latestPhoto"
                :src="latestPhoto.url"
                alt="Latest camera photo"
                class="h-full w-full object-contain"
              />
              <div
                v-else
                class="absolute inset-0 flex items-center justify-center bg-slate-900 text-sm text-slate-300"
              >
                暂无照片
              </div>
            </div>

            <div class="rounded-lg border border-[#dce8de] bg-[#f7fbf7] p-4">
              <div class="section-label">照片信息</div>
              <div class="mt-3 space-y-3 text-sm">
                <div class="flex items-center justify-between">
                  <span class="text-[#789083]">设备连接</span>
                  <span :class="cameraDeviceConnected ? 'text-emerald-600' : 'text-[#66756d]'">
                    {{ cameraDeviceConnected ? '已连接' : '未连接' }}
                  </span>
                </div>
                <div class="flex items-center justify-between">
                  <span class="text-[#789083]">拍摄时间</span>
                  <span class="text-[#17211b]">{{ latestPhotoTime }}</span>
                </div>
                <div class="flex items-center justify-between">
                  <span class="text-[#789083]">设备 ID</span>
                  <span class="text-[#17211b]">{{ latestPhoto?.device_id || '--' }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="app-card">
        <div class="app-card-body space-y-4">
          <div>
            <div class="section-label">历史照片</div>
            <div class="mt-1 text-sm text-[#789083]">共 {{ photosTotal }} 张 · 每页 15 张 · 点击查看大图</div>
          </div>

          <div v-if="!photos.length" class="py-10 text-center text-sm text-[#789083]">
            暂无历史照片
          </div>

          <div
            v-else
            class="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5"
          >
            <div
              v-for="photo in photos"
              :key="photo.id"
              class="group relative aspect-[4/3] cursor-pointer overflow-hidden rounded-lg border bg-slate-950 shadow-sm transition"
              :class="latestPhoto && latestPhoto.id === photo.id ? 'border-blue-500 ring-2 ring-blue-400' : 'border-[#dce8de] hover:border-blue-300 hover:shadow-md'"
              @click="selectPhoto(photo)"
            >
              <img :src="photo.url" :alt="photo.filename" class="h-full w-full object-cover" loading="lazy" />
              <span
                class="pointer-events-none absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/70 to-transparent px-2 py-1 text-[11px] leading-tight text-white"
              >
                {{ photo.captured_at?.replace('T', ' ').slice(5, 19) }}
              </span>
            </div>
          </div>

          <div v-if="photosPages > 1" class="flex items-center justify-end gap-2 text-sm">
            <button class="btn btn-ghost btn-sm" :disabled="photosPage <= 1" @click="gotoPhotosPage(photosPage - 1)">上一页</button>
            <span class="text-[#66756d]">第 {{ photosPage }} / {{ photosPages }} 页</span>
            <button class="btn btn-ghost btn-sm" :disabled="photosPage >= photosPages" @click="gotoPhotosPage(photosPage + 1)">下一页</button>
          </div>
        </div>
      </div>

      <div class="app-card">
        <div class="app-card-body">
          <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <div class="section-label">声音记录</div>
              <div class="mt-1 text-sm text-[#789083]">
                识别把握度越高，越像真实猫叫；低于 {{ minConfidenceText }} 的声音不会进入统计。
              </div>
            </div>

            <div class="flex flex-wrap items-center gap-2">
              <div class="tabs tabs-boxed bg-[#eef6f0] p-1">
                <button
                  v-for="tab in eventTabs"
                  :key="tab.value"
                  class="tab h-8 min-h-8 gap-2 rounded-md px-3 text-xs"
                  :class="filterType === tab.value ? 'tab-active bg-[#fffefa] text-[#17211b] shadow-sm' : 'text-[#66756d]'"
                  @click="filterType = tab.value"
                >
                  {{ tab.label }}
                  <span class="rounded-full bg-slate-200 px-1.5 py-0.5 text-[11px] leading-none text-slate-600">
                    {{ tab.count }}
                  </span>
                </button>
              </div>
              <select v-model="filterHours" class="select select-bordered select-sm" @change="loadViewData">
                <option :value="24">最近 24 小时</option>
                <option :value="48">最近 48 小时</option>
                <option :value="168">最近 7 天</option>
              </select>
            </div>
          </div>

          <div v-if="!filteredEvents.length" class="py-12 text-center text-sm text-[#789083]">
            暂无检测事件
          </div>

          <div v-else class="max-h-[28rem] overflow-auto rounded-lg border border-[#dce8de]">
            <table class="table">
              <thead class="sticky top-0 z-10 bg-[#fffefa]">
                <tr class="text-[#789083]">
                  <th>时间</th>
                  <th>识别把握度</th>
                  <th>识别结果</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="event in filteredEvents" :key="event.id ?? event.ts ?? event.recorded_at">
                  <td class="text-sm text-[#66756d]">{{ formatEventTime(event) }}</td>
                  <td>
                    <div class="flex items-center gap-3">
                      <div class="h-2 w-28 overflow-hidden rounded-full bg-[#eef6f0]">
                        <div
                          class="h-full rounded-full"
                          :class="event.is_cat ? 'bg-[#2f80b7]' : 'bg-[#2f8f6b]'"
                          :style="{ width: `${Math.min(100, event.score * 100)}%` }"
                        />
                      </div>
                      <span class="text-sm text-[#66756d]">{{ (event.score * 100).toFixed(0) }}%</span>
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
    </template>

    <div
      v-if="uiStore.isControlMode && pendingDeletePhoto"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      @click.self="cancelDelete"
    >
      <div class="w-full max-w-sm overflow-hidden rounded-lg bg-[#fffefa] shadow-xl">
        <div class="aspect-[4/3] w-full bg-slate-950">
          <img :src="pendingDeletePhoto.url" :alt="pendingDeletePhoto.filename" class="h-full w-full object-contain" />
        </div>
        <div class="space-y-3 p-5">
          <div class="text-base font-semibold text-[#17211b]">删除这张照片？</div>
          <div class="text-sm text-[#66756d]">
            拍摄于 {{ pendingDeletePhoto.captured_at?.replace('T', ' ').slice(0, 19) }}，删除后不可恢复。
          </div>
          <div class="flex justify-end gap-2 pt-1">
            <button class="btn btn-ghost btn-sm" @click="cancelDelete">取消</button>
            <button class="btn btn-error btn-sm text-white" @click="confirmDelete">删除</button>
          </div>
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
import { useUiStore } from '../stores/uiStore'
import { isChartBoundToElement } from '../utils/chartInstance'

echarts.use([BarChart, GridComponent, TooltipComponent, SVGRenderer])

const api = useApi()
const store = useDeviceStore()
const uiStore = useUiStore()
const isDev = import.meta.env.DEV

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
const meowSummaryTitle = computed(() => {
  if (!stats.value.today_total) return '今天暂时很安静'
  if ((stats.value.today_cat ?? 0) > (stats.value.today_noise ?? 0)) return '今天猫叫活动比较明显'
  return '今天主要是环境噪声'
})
const meowSummaryText = computed(() => {
  if (!stats.value.today_total) return '还没有记录到有效声音事件，摄像头照片和历史事件会在设备上报后更新。'
  return `今天记录 ${stats.value.today_total ?? 0} 次事件，其中猫叫 ${stats.value.today_cat ?? 0} 次，噪声 ${stats.value.today_noise ?? 0} 次。`
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

watch(
  () => store.recentMeowEvents,
  (recentEvents) => {
    if (!uiStore.isViewMode || !recentEvents.length) return
    const knownList = new Set(events.value.map(eventKey))
    const incoming = uniqueByEventKey(recentEvents.filter((event) => isAcceptedEvent(event) && !knownList.has(eventKey(event))))
    if (incoming.length) {
      events.value = [...incoming, ...events.value]
        .sort((left, right) => eventTime(right) - eventTime(left))
        .slice(0, 200)
      for (const event of incoming) applyMeowStatsEvent(event)
    }

    const knownCharts = new Set(chartEvents.value.map(eventKey))
    const incomingCharts = uniqueByEventKey(recentEvents.filter((event) => isAcceptedEvent(event) && !knownCharts.has(eventKey(event))))
    if (incomingCharts.length) {
      chartEvents.value = [...incomingCharts, ...chartEvents.value]
        .sort((left, right) => eventTime(right) - eventTime(left))
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

function isAcceptedEvent(event) {
  return Number(event?.score) >= minConfidence.value
}

function eventKey(event) {
  return event.id ?? event.ts ?? event.recorded_at
}

function uniqueByEventKey(nextEvents) {
  const seen = new Set()
  return nextEvents.filter((event) => {
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
    { label: '可能是猫叫', count: 0, min: minConfidence.value, max: 0.7 },
    { label: '比较像猫叫', count: 0, min: Math.max(minConfidence.value, 0.7), max: 0.9 },
    { label: '很像猫叫', count: 0, min: Math.max(minConfidence.value, 0.9), max: 1.01 },
  ]

  for (const event of chartVisibleEvents.value) {
    const target = buckets.find((bucket) => bucket.min < bucket.max && event.score >= bucket.min && event.score < bucket.max)
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
      backgroundColor: '#fffefa',
      borderColor: '#dce8de',
      borderWidth: 1,
      textStyle: { color: '#17211b', fontSize: 12 },
    },
    grid: { left: 36, right: 16, top: 16, bottom: 28 },
    xAxis: {
      type: 'category',
      data: labels,
      axisLine: { lineStyle: { color: '#dce8de' } },
      axisTick: { show: false },
      axisLabel: { color: '#789083', fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#789083', fontSize: 11 },
      splitLine: { lineStyle: { color: '#dce8de', type: 'dashed' } },
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
  if (frequencyEl.value && !isChartBoundToElement(frequencyChart, frequencyEl.value)) {
    frequencyChart?.dispose()
    frequencyChart = echarts.init(frequencyEl.value, null, { renderer: 'svg' })
  }
  if (confidenceEl.value && !isChartBoundToElement(confidenceChart, confidenceEl.value)) {
    confidenceChart?.dispose()
    confidenceChart = echarts.init(confidenceEl.value, null, { renderer: 'svg' })
  }
}

function refreshCharts() {
  if (!uiStore.isViewMode) return
  ensureCharts()
  frequencyChart?.setOption(buildChartOption(buildHourlySeries(), '#2f80b7'), { notMerge: true })
  confidenceChart?.setOption(buildChartOption(buildConfidenceSeries(), '#2f8f6b'), { notMerge: true })
}

async function loadViewData() {
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
    latestPhoto.value = cameraResult.photo ?? photos.value[0] ?? null
    cameraDeviceConnected.value = cameraResult.device_connected
    await nextTick()
    refreshCharts()
  } catch (error) {
    console.error('Failed to load meow view data', error)
  }
}

async function loadControlData() {
  try {
    const [nextStats, cameraResult] = await Promise.all([
      api.getMeowStats(),
      api.getLatestPhoto(),
    ])
    stats.value = nextStats
    store.setMeowStatus(nextStats)
    latestPhoto.value = cameraResult.photo ?? latestPhoto.value
    cameraDeviceConnected.value = cameraResult.device_connected
  } catch (error) {
    console.error('Failed to load meow control data', error)
  }
}

async function loadActiveModeData() {
  if (uiStore.isControlMode) {
    await loadControlData()
  } else {
    await loadViewData()
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
      return
    }
  }
  captureError.value = '已发送拍照指令，摄像头上传较慢，稍后会自动出现在最新照片中'
}

function selectPhoto(photo) {
  latestPhoto.value = photo
}

function removePhoto(photo) {
  if (!photo) return
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
    await loadControlData()
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
  if (!isDev) return
  const event = await api.mockMeow()
  store.addMeowEvent(event)
  await loadControlData()
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

watch(
  () => uiStore.mode,
  async () => {
    pendingDeletePhoto.value = null
    captureError.value = ''
    await nextTick()
    await loadActiveModeData()
    if (uiStore.isViewMode) {
      await nextTick()
      refreshCharts()
    }
  },
)

onMounted(async () => {
  await loadActiveModeData()
  refreshTimer = window.setInterval(loadActiveModeData, 10_000)
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
