<template>
  <div class="page-shell">
    <section class="product-panel overflow-hidden">
      <div class="grid gap-6 p-5 lg:grid-cols-[1.35fr_0.65fr] lg:p-7">
        <div>
          <div class="status-chip">
            <span
              class="h-2.5 w-2.5 rounded-full"
              :class="store.connected ? 'bg-[#2f8f6b]' : 'bg-[#c4ccc7]'"
            />
            {{ store.connected ? '设备在线' : '设备离线' }}
          </div>
          <h1 class="mt-5 max-w-2xl text-3xl font-semibold leading-tight text-[#17211b] lg:text-4xl">
            {{ homeSummaryTitle }}
          </h1>
          <p class="mt-3 max-w-xl text-sm leading-6 text-[#66756d]">
            {{ homeSummaryText }}
          </p>

          <div class="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div class="soft-panel px-3 py-3">
              <div class="text-xs text-[#789083]">温度</div>
              <div class="mt-1 text-xl font-semibold text-[#2f80b7]">
                {{ store.latestSensor?.temp_c ?? '--' }}<span class="text-sm text-[#789083]">°C</span>
              </div>
            </div>
            <div class="soft-panel px-3 py-3">
              <div class="text-xs text-[#789083]">湿度</div>
              <div class="mt-1 text-xl font-semibold text-[#2f8f6b]">
                {{ store.latestSensor?.humi_rh ?? '--' }}<span class="text-sm text-[#789083]">%</span>
              </div>
            </div>
            <div class="soft-panel px-3 py-3">
              <div class="text-xs text-[#789083]">今日猫叫</div>
              <div class="mt-1 text-xl font-semibold text-[#17211b]">{{ meowStats.today_cat ?? 0 }}</div>
            </div>
            <div class="soft-panel px-3 py-3">
              <div class="text-xs text-[#789083]">噪声</div>
              <div class="mt-1 text-xl font-semibold text-[#d76f45]">{{ meowStats.today_noise ?? 0 }}</div>
            </div>
          </div>
        </div>

        <div class="relative min-h-56 overflow-hidden rounded-lg border border-white/70 bg-[#eef6f0]/72 p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.72),0_24px_44px_-30px_rgba(47,128,183,0.42)] backdrop-blur-xl">
          <div class="pointer-events-none absolute -right-12 top-10 h-32 w-32 rounded-full bg-[#2f80b7]/18 blur-3xl" />
          <div class="pointer-events-none absolute left-6 top-0 h-px w-2/3 bg-gradient-to-r from-transparent via-white/80 to-transparent" />
          <img
            src="../assets/hero.png"
            alt=""
            class="pointer-events-none absolute -right-10 -top-8 h-44 w-44 opacity-90"
          />
          <div class="relative z-10">
            <div class="section-label">猫窝状态</div>
            <div class="mt-3 text-2xl font-semibold text-[#17211b]">{{ store.connected ? '正在守护中' : '等待连接' }}</div>
            <div class="mt-2 max-w-[13rem] text-sm leading-6 text-[#66756d]">
              {{ store.connected ? `设备 ${store.deviceId || '未命名设备'} 已接入` : '设备恢复在线后会自动更新数据' }}
            </div>
            <div class="mt-8 inline-flex items-center gap-2 rounded-full bg-[#fffefa]/80 px-3 py-1.5 text-xs font-medium text-[#17674c]">
              <component :is="store.connected ? Wifi : WifiOff" :size="14" />
              {{ store.connected ? store.state : '离线' }}
            </div>
          </div>
        </div>
      </div>
    </section>

    <div class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
      <div class="metric-card p-5">
        <div class="flex items-start justify-between gap-3">
          <div>
            <div class="section-label">设备状态</div>
            <div class="mt-3 text-2xl font-semibold text-[#17211b]">{{ store.connected ? '在线' : '离线' }}</div>
            <div class="mt-2 text-sm text-[#66756d]">{{ store.deviceId || '等待设备连接' }}</div>
          </div>
          <div class="icon-tile" :class="store.connected ? 'bg-[#eefaf2] text-[#17674c]' : 'bg-[#eef1ef] text-[#8a9890]'">
            <component :is="store.connected ? Wifi : WifiOff" :size="20" />
          </div>
        </div>
      </div>

      <div class="metric-card p-5">
        <div class="section-label">当前温度</div>
        <div class="mt-3 text-3xl font-semibold text-[#2f80b7]">
          {{ store.latestSensor?.temp_c ?? '--' }}<span class="text-lg text-[#789083]">°C</span>
        </div>
        <div class="mt-2 flex flex-wrap items-center gap-2 text-sm">
          <span class="text-[#66756d]">最新样本</span>
          <span class="rounded-full px-2 py-0.5 text-xs font-medium" :class="sensorSourceClass">
            {{ sensorSourceText }}
          </span>
        </div>
      </div>

      <div class="metric-card p-5">
        <div class="section-label">当前湿度</div>
        <div class="mt-3 text-3xl font-semibold text-[#2f8f6b]">
          {{ store.latestSensor?.humi_rh ?? '--' }}<span class="text-lg text-[#789083]">%</span>
        </div>
        <div class="mt-2 text-sm text-[#66756d]">
          {{ store.latestSensor ? formatSensorTime(store.latestSensor) : '等待设备数据' }}
        </div>
      </div>

      <div class="metric-card p-5">
        <div class="section-label">今日猫叫统计</div>
        <div class="mt-3 text-3xl font-semibold text-[#17211b]">{{ meowStats.today_total ?? 0 }}</div>
        <div class="mt-2 text-sm text-[#66756d]">猫叫 {{ meowStats.today_cat ?? 0 }} · 噪声 {{ meowStats.today_noise ?? 0 }}</div>
      </div>
    </div>

    <div
      v-if="sensorAlertMessages.length"
      class="rounded-lg border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-600"
    >
      当前环境提醒：{{ sensorAlertMessages.join('；') }}
    </div>

    <div
      v-if="isSensorFallback"
      class="rounded-lg border border-amber-100 bg-amber-50 px-4 py-3 text-sm text-amber-700"
    >
      当前显示的是临时诊断数据：设备已连上云端，但真实温湿度传感器暂时没有读到。
      <span v-if="store.latestSensor?.sensor_error">错误：{{ store.latestSensor.sensor_error }}</span>
    </div>

    <div class="grid grid-cols-1 gap-4 xl:grid-cols-[1.4fr_1fr]">
      <div class="app-card">
        <div class="app-card-body">
          <div class="mb-4 flex items-center justify-between">
            <div>
              <div class="section-label">温湿度趋势</div>
              <div class="mt-1 text-sm text-[#66756d]">最近 8 小时变化</div>
            </div>
            <button class="btn btn-ghost btn-sm text-[#52645a]" @click="load">刷新</button>
          </div>
          <SensorChart :history="sensorHistory" height="280px" />
        </div>
      </div>

      <div class="app-card">
        <div class="app-card-body">
          <div class="soft-panel px-4 py-4">
            <div class="text-sm font-semibold text-[#17211b]">最近猫叫事件</div>
            <div v-if="!recentEvents.length" class="mt-3 text-sm text-[#789083]">暂无事件</div>
            <div v-else class="mt-3 space-y-3">
              <div
                v-for="event in recentEvents"
                :key="event.id ?? event.ts ?? event.recorded_at"
                class="flex items-center justify-between gap-3 rounded-lg border border-[#dce8de] bg-[#fffefa] px-3 py-2"
              >
                <div>
                  <div class="text-sm font-medium text-[#17211b]">{{ event.is_cat ? '猫叫' : '噪声' }}</div>
                  <div class="text-xs text-[#789083]">{{ formatEventTime(event) }}</div>
                </div>
                <div class="text-sm text-[#66756d]">把握度 {{ (event.score * 100).toFixed(0) }}%</div>
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
const homeSummaryTitle = computed(() => {
  if (!store.connected) return '小智正在等待设备回到猫窝'
  if (sensorAlertMessages.value.length) return '猫窝环境需要留意一下'
  if (isSensorFallback.value) return '设备已连接，传感器还在校准'
  return '猫窝状态稳定，饮水和环境都在看护中'
})
const homeSummaryText = computed(() => {
  if (!store.connected) return '设备离线时仍可查看历史记录；恢复连接后，环境、饮水和猫叫数据会继续更新。'
  if (sensorAlertMessages.value.length) return sensorAlertMessages.value.join('；')
  if (!store.latestSensor) return '已经连接设备，正在等待第一条环境数据上报。'
  return `最近一次更新 ${formatSensorTime(store.latestSensor)}，当前温度 ${store.latestSensor.temp_c ?? '--'}°C，湿度 ${store.latestSensor.humi_rh ?? '--'}%。`
})
const sensorSourceText = computed(() => {
  if (!store.latestSensor) return '等待数据'
  if (isSensorFallback.value) return '临时诊断数据'
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
