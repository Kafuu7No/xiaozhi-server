<template>
  <div class="mx-auto max-w-6xl space-y-4">
    <div
      v-if="hasAlert"
      class="rounded-xl border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-600"
    >
      当前环境已超出阈值：
      <span>{{ alertMessages.join('；') }}</span>
    </div>

    <div
      v-if="isCurrentFallback"
      class="rounded-xl border border-amber-100 bg-amber-50 px-4 py-3 text-sm text-amber-700"
    >
      当前温湿度来自板端诊断回退，云端通信已经打通，但板端没有检测到 AHT20 真实传感器。
      <span v-if="currentSensor?.sensor_error">错误：{{ currentSensor.sensor_error }}</span>
    </div>

    <div class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
      <div class="app-card">
        <div class="app-card-body">
          <div class="section-label">当前温度</div>
          <div class="mt-3 flex items-end gap-2">
            <span class="metric-value text-[#3B82F6]">{{ currentSensor?.temp_c ?? '--' }}</span>
            <span class="pb-1 text-lg text-slate-400">°C</span>
          </div>
          <div class="mt-3 text-sm text-slate-400">
            {{ currentSensor ? `采样时间 ${formatSensorTime(currentSensor)}` : '等待设备数据' }}
          </div>
          <div class="mt-2">
            <span class="rounded-full px-2 py-0.5 text-xs font-medium" :class="sensorSourceClass(currentSensor)">
              {{ sensorSourceText(currentSensor) }}
            </span>
          </div>
        </div>
      </div>

      <div class="app-card">
        <div class="app-card-body">
          <div class="section-label">当前湿度</div>
          <div class="mt-3 flex items-end gap-2">
            <span class="metric-value text-[#10B981]">{{ currentSensor?.humi_rh ?? '--' }}</span>
            <span class="pb-1 text-lg text-slate-400">%</span>
          </div>
          <div class="mt-3 text-sm text-slate-400">高阈值 {{ thresholds.humi_max }}%</div>
        </div>
      </div>

      <div class="app-card">
        <div class="app-card-body">
          <div class="section-label">24 小时温度</div>
          <div class="mt-3 text-2xl font-semibold text-slate-900">
            {{ stats.temp_c.max ?? '--' }}
            <span class="text-base font-normal text-slate-400">最高</span>
          </div>
          <div class="mt-2 text-sm text-slate-400">
            最低 {{ stats.temp_c.min ?? '--' }}°C · 平均 {{ stats.temp_c.avg ?? '--' }}°C
          </div>
        </div>
      </div>

      <div class="app-card">
        <div class="app-card-body">
          <div class="section-label">24 小时湿度</div>
          <div class="mt-3 text-2xl font-semibold text-slate-900">
            {{ stats.humi_rh.max ?? '--' }}
            <span class="text-base font-normal text-slate-400">最高</span>
          </div>
          <div class="mt-2 text-sm text-slate-400">
            最低 {{ stats.humi_rh.min ?? '--' }}% · 平均 {{ stats.humi_rh.avg ?? '--' }}%
          </div>
        </div>
      </div>
    </div>

    <div class="app-card">
      <div class="app-card-body">
        <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <div class="section-label">24 小时趋势</div>
            <div class="mt-1 text-sm text-slate-400">已对齐真实字段 temp_c / humi_rh / ts</div>
          </div>
          <div class="flex items-center gap-2">
            <button class="btn btn-ghost btn-sm" @click="load">刷新</button>
          </div>
        </div>
        <SensorChart :history="history" height="320px" />
      </div>
    </div>

    <div class="app-card">
      <div class="app-card-body">
        <div class="mb-4 flex items-center justify-between">
          <div>
            <div class="section-label">原始数据</div>
            <div class="mt-1 text-sm text-slate-400">每页 20 条，按落库时间倒序</div>
          </div>
          <span class="text-sm text-slate-400">共 {{ recordsTotal }} 条</span>
        </div>

        <div v-if="!pagedRows.length" class="py-12 text-center text-sm text-slate-400">
          暂无环境数据
        </div>

        <div v-else class="overflow-x-auto">
          <table class="table">
            <thead>
              <tr class="text-slate-400">
                <th>时间</th>
                <th>temp_c</th>
                <th>humi_rh</th>
                <th>来源</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in pagedRows" :key="row.id ?? row.ts ?? row.recorded_at">
                <td class="text-sm text-slate-500">{{ formatSensorTime(row) }}</td>
                <td class="font-medium text-slate-900">{{ row.temp_c }}°C</td>
                <td class="font-medium text-slate-900">{{ row.humi_rh }}%</td>
                <td>
                  <span
                    class="badge badge-sm border-0"
                    :class="sensorSourceClass(row)"
                    :title="row.sensor_error || ''"
                  >
                    {{ sensorSourceText(row) }}
                  </span>
                </td>
                <td>
                  <span
                    class="badge badge-sm border-0"
                    :class="row.has_alert ? 'bg-red-100 text-red-600' : 'bg-slate-100 text-slate-500'"
                  >
                    {{ row.has_alert ? '告警' : '正常' }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-if="recordsPages > 1" class="mt-4 flex items-center justify-end gap-2 text-sm">
          <button class="btn btn-ghost btn-sm" :disabled="recordsPage <= 1" @click="gotoRecordsPage(recordsPage - 1)">上一页</button>
          <span class="text-slate-500">第 {{ recordsPage }} / {{ recordsPages }} 页</span>
          <button class="btn btn-ghost btn-sm" :disabled="recordsPage >= recordsPages" @click="gotoRecordsPage(recordsPage + 1)">下一页</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import SensorChart from '../components/SensorChart.vue'
import { useApi } from '../composables/useApi'
import { useDeviceStore } from '../stores/deviceStore'

const api = useApi()
const store = useDeviceStore()

const history = ref([])
const stats = ref({
  sample_count: 0,
  temp_c: { min: null, max: null, avg: null },
  humi_rh: { min: null, max: null, avg: null },
})
const thresholds = ref({ temp_max: 35, humi_min: 30, humi_max: 80 })
let refreshTimer = null

const currentSensor = computed(() => store.latestSensor ?? history.value.at(-1) ?? null)
const pagedRows = ref([])
const recordsPage = ref(1)
const recordsPages = ref(1)
const recordsTotal = ref(0)
const currentAlerts = computed(() => currentSensor.value?.alerts ?? {})
const temperatureHigh = computed(() => currentAlerts.value.temp_high ?? (currentSensor.value && currentSensor.value.temp_c > thresholds.value.temp_max))
const humidityLow = computed(() => currentAlerts.value.humi_low ?? (currentSensor.value && currentSensor.value.humi_rh < thresholds.value.humi_min))
const humidityHigh = computed(() => currentAlerts.value.humi_high ?? (currentSensor.value && currentSensor.value.humi_rh > thresholds.value.humi_max))
const hasAlert = computed(() => currentSensor.value?.has_alert ?? (temperatureHigh.value || humidityLow.value || humidityHigh.value))
const alertThresholds = computed(() => currentAlerts.value.thresholds ?? thresholds.value)
const alertMessages = computed(() => {
  if (!currentSensor.value) return []
  const messages = []
  if (temperatureHigh.value) {
    messages.push(`温度 ${currentSensor.value.temp_c}°C 超过 ${alertThresholds.value.temp_max}°C`)
  }
  if (humidityLow.value) {
    messages.push(`湿度 ${currentSensor.value.humi_rh}% 低于 ${alertThresholds.value.humi_min}%`)
  }
  if (humidityHigh.value) {
    messages.push(`湿度 ${currentSensor.value.humi_rh}% 超过 ${alertThresholds.value.humi_max}%`)
  }
  return messages
})
const isCurrentFallback = computed(() => isSensorFallback(currentSensor.value))

watch(
  () => store.latestSensor,
  (sample) => {
    if (!sample) return
    const key = sample.id ?? sample.ts ?? sample.recorded_at
    const exists = history.value.some((row) => (row.id ?? row.ts ?? row.recorded_at) === key)
    if (exists) return
    const cutoff = Date.now() - 24 * 3600_000
    history.value = [...history.value, sample]
      .filter((row) => toTimeValue(row) >= cutoff || toTimeValue(row) === 0)
      .sort((left, right) => toTimeValue(left) - toTimeValue(right))
  },
)

async function loadRecords(page = recordsPage.value) {
  const result = await api.getSensorRecords(page, 20)
  pagedRows.value = result.items ?? []
  recordsPage.value = result.page ?? 1
  recordsPages.value = result.pages ?? 1
  recordsTotal.value = result.total ?? 0
}

function gotoRecordsPage(page) {
  loadRecords(Math.max(1, Math.min(page, recordsPages.value)))
}

async function load() {
  try {
    const [nextHistory, nextStats, nextThresholds] = await Promise.all([
      api.getSensorHistory(24),
      api.getSensorStats(24),
      api.getSensorThresholds(),
      loadRecords(),
    ])
    history.value = nextHistory
    stats.value = nextStats
    thresholds.value = nextThresholds
    if (!store.latestSensor && nextHistory.length) {
      store.setSensorUpdate(nextHistory.at(-1))
    }
  } catch (error) {
    console.error('Failed to load sensor data', error)
  }
}

function toTimeValue(sample) {
  if (typeof sample?.ts === 'number') return sample.ts
  if (sample?.recorded_at) return Date.parse(sample.recorded_at)
  return 0
}

function formatSensorTime(sample) {
  const p = (n) => String(n).padStart(2, '0')
  if (typeof sample?.ts === 'number') {
    const d = new Date(sample.ts)
    if (Number.isNaN(d.getTime())) return '--'
    return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
  }
  if (sample?.recorded_at) {
    return sample.recorded_at.replace('T', ' ').slice(5, 19)
  }
  return '--'
}

function isSensorFallback(sample) {
  return sample?.sensor_ok === false || sample?.source === 'env_fallback'
}

function sensorSourceText(sample) {
  if (!sample) return '等待数据'
  if (isSensorFallback(sample)) return '诊断回退'
  if (sample.source === 'mock') return '模拟数据'
  if (sample.sensor_ok === true || sample.source === 'env') return '真实上报'
  return '设备上报'
}

function sensorSourceClass(sample) {
  if (!sample) return 'bg-slate-100 text-slate-500'
  if (isSensorFallback(sample)) return 'bg-amber-100 text-amber-700'
  if (sample.source === 'mock') return 'bg-slate-100 text-slate-500'
  return 'bg-emerald-100 text-emerald-700'
}

onMounted(() => {
  load()
  refreshTimer = window.setInterval(load, 10_000)
})

onUnmounted(() => {
  if (refreshTimer) window.clearInterval(refreshTimer)
})
</script>
