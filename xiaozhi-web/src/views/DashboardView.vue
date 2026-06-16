<template>
  <div class="mx-auto max-w-6xl space-y-4">
    <div class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
      <div class="app-card">
        <div class="app-card-body">
          <div class="section-label">设备状态</div>
          <div class="mt-3 flex items-center gap-3">
            <div
              class="flex h-11 w-11 items-center justify-center rounded-2xl"
              :class="store.connected ? 'bg-emerald-50 text-emerald-600' : 'bg-slate-100 text-slate-400'"
            >
              <component :is="store.connected ? Wifi : WifiOff" :size="20" />
            </div>
            <div>
              <div class="text-lg font-semibold text-slate-900">{{ store.connected ? '在线' : '离线' }}</div>
              <div class="text-sm text-slate-400">{{ store.deviceId || '等待设备连接' }}</div>
            </div>
          </div>
        </div>
      </div>

      <div class="app-card">
        <div class="app-card-body">
          <div class="section-label">当前温度</div>
          <div class="mt-3 text-3xl font-semibold text-[#3B82F6]">
            {{ store.latestSensor?.temp_c ?? '--' }}<span class="text-lg text-slate-400">°C</span>
          </div>
          <div class="mt-2 flex flex-wrap items-center gap-2 text-sm">
            <span class="text-slate-400">最新温湿度样本</span>
            <span class="rounded-full px-2 py-0.5 text-xs font-medium" :class="sensorSourceClass">
              {{ sensorSourceText }}
            </span>
          </div>
        </div>
      </div>

      <div class="app-card">
        <div class="app-card-body">
          <div class="section-label">当前湿度</div>
          <div class="mt-3 text-3xl font-semibold text-[#10B981]">
            {{ store.latestSensor?.humi_rh ?? '--' }}<span class="text-lg text-slate-400">%</span>
          </div>
          <div class="mt-2 text-sm text-slate-400">
            {{ store.latestSensor ? formatSensorTime(store.latestSensor) : '等待设备数据' }}
          </div>
        </div>
      </div>

      <div class="app-card">
        <div class="app-card-body">
          <div class="section-label">今日猫叫统计</div>
          <div class="mt-3 text-3xl font-semibold text-slate-900">{{ meowStats.today_total ?? 0 }}</div>
          <div class="mt-2 text-sm text-slate-400">猫叫 {{ meowStats.today_cat ?? 0 }} · 噪声 {{ meowStats.today_noise ?? 0 }}</div>
        </div>
      </div>
    </div>

    <div
      v-if="sensorAlertMessages.length"
      class="rounded-xl border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-600"
    >
      当前环境告警：{{ sensorAlertMessages.join('；') }}
    </div>

    <div
      v-if="isSensorFallback"
      class="rounded-xl border border-amber-100 bg-amber-50 px-4 py-3 text-sm text-amber-700"
    >
      当前温湿度是板端诊断回退数据，说明云端链路已通，但板端还没有读到 AHT20 真实传感器。
      <span v-if="store.latestSensor?.sensor_error">错误：{{ store.latestSensor.sensor_error }}</span>
    </div>

    <div class="grid grid-cols-1 gap-4 xl:grid-cols-[1.4fr_1fr]">
      <div class="app-card">
        <div class="app-card-body">
          <div class="mb-4 flex items-center justify-between">
            <div>
              <div class="section-label">温湿度趋势</div>
              <div class="mt-1 text-sm text-slate-400">最近 8 小时变化</div>
            </div>
            <button class="btn btn-ghost btn-sm" @click="load">刷新</button>
          </div>
          <SensorChart :history="sensorHistory" height="280px" />
        </div>
      </div>

      <div class="app-card">
        <div class="app-card-body space-y-4">
          <div class="rounded-2xl bg-slate-50 px-4 py-4">
            <div class="text-sm font-medium text-slate-900">最近猫叫事件</div>
            <div v-if="!recentEvents.length" class="mt-3 text-sm text-slate-400">暂无事件</div>
            <div v-else class="mt-3 space-y-3">
              <div
                v-for="event in recentEvents"
                :key="event.id ?? event.ts ?? event.recorded_at"
                class="flex items-center justify-between gap-3 rounded-xl border border-slate-100 bg-white px-3 py-2"
              >
                <div>
                  <div class="text-sm font-medium text-slate-900">{{ event.is_cat ? '猫叫' : '噪声' }}</div>
                  <div class="text-xs text-slate-400">{{ formatEventTime(event) }}</div>
                </div>
                <div class="text-sm text-slate-500">{{ (event.score * 100).toFixed(0) }}%</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { Wifi, WifiOff } from 'lucide-vue-next'
import SensorChart from '../components/SensorChart.vue'
import { useApi } from '../composables/useApi'
import { useDeviceStore } from '../stores/deviceStore'

const api = useApi()
const store = useDeviceStore()

const sensorHistory = ref([])
const meowStats = ref({ today_total: 0, today_cat: 0, today_noise: 0 })
const recentEvents = ref([])
const seenMeowEventKeys = new Set()
let refreshTimer = null

const isSensorFallback = computed(() => store.latestSensor?.sensor_ok === false || store.latestSensor?.source === 'env_fallback')
const sensorSourceText = computed(() => {
  if (!store.latestSensor) return '等待数据'
  if (isSensorFallback.value) return '诊断回退'
  if (store.latestSensor.source === 'mock') return '模拟数据'
  if (store.latestSensor.sensor_ok === true || store.latestSensor.source === 'env') return '真实上报'
  return '设备上报'
})
const sensorSourceClass = computed(() => {
  if (!store.latestSensor) return 'bg-slate-100 text-slate-500'
  if (isSensorFallback.value) return 'bg-amber-100 text-amber-700'
  if (store.latestSensor.source === 'mock') return 'bg-slate-100 text-slate-500'
  return 'bg-emerald-100 text-emerald-700'
})
const sensorAlertMessages = computed(() => {
  const sample = store.latestSensor
  if (!sample?.has_alert) return []
  const alerts = sample.alerts ?? {}
  const thresholds = alerts.thresholds ?? {}
  const messages = []
  if (alerts.temp_high) {
    messages.push(`温度 ${sample.temp_c}°C 超过 ${thresholds.temp_max ?? '--'}°C`)
  }
  if (alerts.humi_low) {
    messages.push(`湿度 ${sample.humi_rh}% 低于 ${thresholds.humi_min ?? '--'}%`)
  }
  if (alerts.humi_high) {
    messages.push(`湿度 ${sample.humi_rh}% 超过 ${thresholds.humi_max ?? '--'}%`)
  }
  return messages
})

watch(
  () => store.latestSensor,
  (sample) => {
    appendSensorSample(sample)
  },
  { immediate: true },
)

watch(
  () => store.recentMeowEvents,
  (events) => {
    mergeMeowEvents(events)
  },
  { deep: true },
)

async function load() {
  try {
    const [history, stats, events] = await Promise.all([
      api.getSensorHistory(8),
      api.getMeowStats(),
      api.getMeowEvents(24),
    ])
    sensorHistory.value = history
    meowStats.value = stats
    seenMeowEventKeys.clear()
    events.forEach((event) => seenMeowEventKeys.add(eventKey(event)))
    recentEvents.value = events.slice(0, 4)
  } catch (error) {
    console.error('Failed to load dashboard data', error)
  }
}

function appendSensorSample(sample) {
  if (!sample) return
  const key = sampleKey(sample)
  const exists = sensorHistory.value.some((row) => sampleKey(row) === key)
  if (exists) return
  const cutoff = Date.now() - 8 * 3600_000
  sensorHistory.value = [...sensorHistory.value, sample]
    .filter((row) => sampleTime(row) >= cutoff || sampleTime(row) === 0)
    .sort((left, right) => sampleTime(left) - sampleTime(right))
}

function mergeMeowEvents(events) {
  if (!events?.length) return
  const incoming = uniqueByEventKey(events.filter((event) => !seenMeowEventKeys.has(eventKey(event))))
  if (!incoming.length) return
  incoming.forEach((event) => seenMeowEventKeys.add(eventKey(event)))
  recentEvents.value = [...incoming, ...recentEvents.value]
    .sort((left, right) => eventTime(right) - eventTime(left))
    .slice(0, 4)
  for (const event of incoming) {
    applyMeowStatsEvent(event)
  }
}

function applyMeowStatsEvent(event) {
  if (!isToday(eventTime(event))) return
  meowStats.value = {
    ...meowStats.value,
    today_total: (meowStats.value.today_total ?? 0) + 1,
    today_cat: (meowStats.value.today_cat ?? 0) + (event.is_cat ? 1 : 0),
    today_noise: (meowStats.value.today_noise ?? 0) + (event.is_cat ? 0 : 1),
  }
}

function sampleKey(sample) {
  return sample?.id ?? sample?.ts ?? sample?.recorded_at
}

function sampleTime(sample) {
  if (typeof sample?.ts === 'number') return sample.ts
  if (sample?.recorded_at) return Date.parse(sample.recorded_at)
  return 0
}

function eventKey(event) {
  return event?.id ?? event?.ts ?? event?.recorded_at
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

function formatClock(date) {
  if (Number.isNaN(date.getTime())) return '--'
  const p = (n) => String(n).padStart(2, '0')
  return `${p(date.getMonth() + 1)}-${p(date.getDate())} ${p(date.getHours())}:${p(date.getMinutes())}:${p(date.getSeconds())}`
}

function formatEventTime(event) {
  if (typeof event?.ts === 'number') {
    return formatClock(new Date(event.ts))
  }
  if (event?.recorded_at) {
    return event.recorded_at.replace('T', ' ').slice(5, 19)
  }
  return '--'
}

function formatSensorTime(sample) {
  if (typeof sample?.ts === 'number') {
    return formatClock(new Date(sample.ts))
  }
  if (sample?.recorded_at) {
    return sample.recorded_at.replace('T', ' ').slice(5, 19)
  }
  return '等待设备数据'
}

onMounted(() => {
  load()
  refreshTimer = window.setInterval(load, 10_000)
})

onUnmounted(() => {
  if (refreshTimer) window.clearInterval(refreshTimer)
})
</script>
