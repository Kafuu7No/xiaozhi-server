<template>
  <div class="mx-auto max-w-6xl space-y-4">
    <template v-if="uiStore.isControlMode">
      <div class="app-card">
        <div class="app-card-body space-y-4">
          <div>
            <div class="section-label">手动控泵</div>
            <div class="mt-1 text-sm text-slate-400">立即开泵 N 秒，并将记录写入历史</div>
          </div>

          <div class="flex flex-wrap items-end gap-3">
            <label class="w-full max-w-xs text-sm text-slate-500">
              运行时长
              <div class="mt-2 flex items-center gap-2">
                <input
                  v-model.number="manualDuration"
                  type="number"
                  min="1"
                  max="120"
                  class="input input-bordered w-full"
                />
                <span class="text-slate-400">秒</span>
              </div>
            </label>
            <button class="btn btn-primary" @click="startPump">立即开泵</button>
            <button class="btn btn-outline" @click="stopPump">停止</button>
          </div>

          <div class="rounded-xl bg-slate-50 px-4 py-3 text-sm text-slate-500">
            最近一次出水：
            <span class="font-medium text-slate-900">{{ latestRecordSummary }}</span>
          </div>

          <div class="border-t border-slate-100 pt-4">
            <div class="flex items-center justify-between gap-4">
              <div>
                <div class="text-sm font-medium text-slate-900">猫叫联动放水</div>
                <div class="mt-1 text-xs text-slate-400">
                  开启后由猫窝主板检测，10 秒内 3 次猫叫即通知放水板放水，60 秒内不重复触发。
                </div>
              </div>
              <input
                :checked="waterSettings.autoOnMeow"
                type="checkbox"
                class="toggle toggle-primary"
                @change="toggleAutoOnMeow"
              />
            </div>
            <label
              v-if="waterSettings.autoOnMeow"
              class="mt-3 flex max-w-xs items-center gap-2 text-sm text-slate-500"
            >
              联动放水时长
              <input
                v-model.number="waterSettings.delaySeconds"
                type="number"
                min="1"
                max="120"
                class="input input-bordered input-sm w-24"
                @change="saveAutoWaterSettings"
              />
              <span class="text-slate-400">秒</span>
            </label>
          </div>
        </div>
      </div>

      <div class="grid grid-cols-1 gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <div class="app-card">
          <div class="app-card-body">
            <div class="mb-4">
              <div class="section-label">定时计划</div>
              <div class="mt-1 text-sm text-slate-400">支持新增、编辑、启停与删除</div>
            </div>

            <div class="grid grid-cols-1 gap-3 rounded-xl bg-slate-50 p-4 md:grid-cols-[1fr_140px_140px_auto]">
              <input
                v-model="scheduleForm.label"
                type="text"
                class="input input-bordered w-full"
                placeholder="计划名称"
              />
              <input v-model="scheduleForm.time" type="time" class="input input-bordered w-full" />
              <input
                v-model.number="scheduleForm.duration_seconds"
                type="number"
                min="1"
                max="120"
                class="input input-bordered w-full"
                placeholder="时长"
              />
              <button class="btn btn-primary" @click="saveSchedule">
                {{ scheduleForm.id ? '更新计划' : '新增计划' }}
              </button>
            </div>

            <div v-if="!schedules.length" class="py-10 text-center text-sm text-slate-400">
              暂无计划
            </div>

            <div v-else class="mt-4 overflow-x-auto">
              <table class="table">
                <thead>
                  <tr class="text-slate-400">
                    <th>名称</th>
                    <th>时间</th>
                    <th>时长</th>
                    <th>状态</th>
                    <th class="text-right">操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="schedule in schedules" :key="schedule.id">
                    <td class="font-medium text-slate-900">{{ schedule.label }}</td>
                    <td class="text-slate-500">{{ schedule.time }}</td>
                    <td class="text-slate-500">{{ schedule.duration_seconds }} 秒</td>
                    <td>
                      <input
                        :checked="schedule.enabled"
                        type="checkbox"
                        class="toggle toggle-primary toggle-sm"
                        @change="toggleSchedule(schedule)"
                      />
                    </td>
                    <td>
                      <div class="flex justify-end gap-2">
                        <button class="btn btn-ghost btn-sm" @click="editSchedule(schedule)">编辑</button>
                        <button class="btn btn-ghost btn-sm text-red-500" @click="removeSchedule(schedule.id)">
                          删除
                        </button>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div class="app-card">
          <div class="app-card-body">
            <div class="section-label">最近记录</div>
            <div class="mt-3 space-y-3">
              <div v-if="!records.length" class="py-10 text-center text-sm text-slate-400">暂无出水记录</div>
              <template v-else>
                <div
                  v-for="record in records.slice(0, 5)"
                  :key="record.id"
                  class="rounded-xl border border-slate-100 px-3 py-2 text-sm"
                >
                  <div class="font-medium text-slate-900">{{ formatDateTime(record.started_at) }}</div>
                  <div class="mt-1 text-slate-500">
                    {{ triggerLabelMap[record.trigger_type] || record.trigger_type }} · {{ record.duration_seconds }} 秒 ·
                    {{ record.volume_ml ?? record.duration_seconds * 3 }} ml
                  </div>
                </div>
              </template>
            </div>
          </div>
        </div>
      </div>
    </template>

    <template v-else>
      <div class="app-card">
        <div class="app-card-body">
          <div class="mb-4 flex items-center justify-between gap-3">
            <div>
              <div class="section-label">饮水量</div>
              <div class="mt-1 text-sm text-slate-400">
                {{ usageGranularity === 'hour' ? '最近 24 小时每小时出水量' : '最近 7 天每日出水量' }}
              </div>
            </div>
            <div class="tabs tabs-boxed bg-slate-100 p-1">
              <button
                class="tab h-8 min-h-8 rounded-md px-3 text-xs"
                :class="usageGranularity === 'hour' ? 'tab-active bg-white text-slate-900 shadow-sm' : 'text-slate-500'"
                @click="setGranularity('hour')"
              >按小时</button>
              <button
                class="tab h-8 min-h-8 rounded-md px-3 text-xs"
                :class="usageGranularity === 'day' ? 'tab-active bg-white text-slate-900 shadow-sm' : 'text-slate-500'"
                @click="setGranularity('day')"
              >按天</button>
            </div>
          </div>
          <div ref="waterChartEl" class="h-72 w-full" />
        </div>
      </div>

      <div class="app-card">
        <div class="app-card-body">
          <div class="mb-4 flex items-center justify-between">
            <div>
              <div class="section-label">出水记录</div>
              <div class="mt-1 text-sm text-slate-400">每页 20 条，按时间倒序</div>
            </div>
            <span class="text-sm text-slate-400">共 {{ recordsTotal }} 条</span>
          </div>

          <div v-if="!pagedRecords.length" class="py-10 text-center text-sm text-slate-400">
            暂无出水记录
          </div>

          <div v-else class="overflow-x-auto">
            <table class="table">
              <thead>
                <tr class="text-slate-400">
                  <th>开始时间</th>
                  <th>触发方式</th>
                  <th>时长</th>
                  <th>估算水量</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="record in pagedRecords" :key="record.id">
                  <td class="text-sm text-slate-500">{{ formatDateTime(record.started_at) }}</td>
                  <td class="font-medium text-slate-900">{{ triggerLabelMap[record.trigger_type] || record.trigger_type }}</td>
                  <td class="text-slate-500">{{ record.duration_seconds }} 秒</td>
                  <td class="text-slate-500">{{ record.volume_ml ?? record.duration_seconds * 3 }} ml</td>
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
    </template>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import * as echarts from 'echarts/core'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { BarChart } from 'echarts/charts'
import { SVGRenderer } from 'echarts/renderers'
import { useApi } from '../composables/useApi'
import { useUiStore } from '../stores/uiStore'

echarts.use([BarChart, GridComponent, TooltipComponent, SVGRenderer])

const api = useApi()
const uiStore = useUiStore()

const records = ref([])
const schedules = ref([])
const waterSettings = ref({ autoOnMeow: false, delaySeconds: 15 })
const manualDuration = ref(15)
const usageGranularity = ref('day')
const usageSeries = ref([])
const pagedRecords = ref([])
const recordsPage = ref(1)
const recordsPages = ref(1)
const recordsTotal = ref(0)
const scheduleForm = ref({
  id: null,
  label: '',
  time: '08:30',
  duration_seconds: 15,
  enabled: true,
})

const triggerLabelMap = {
  manual: '手动',
  schedule: '定时计划',
  meow_linkage: '猫叫联动',
}

const latestRecordSummary = computed(() => {
  const latest = records.value[0]
  if (!latest) return '暂无记录'
  return `${formatDateTime(latest.started_at)} · ${latest.duration_seconds} 秒 · ${latest.volume_ml ?? latest.duration_seconds * 3} ml`
})

const waterChartEl = ref(null)
let waterChart = null

function refreshChart() {
  if (!waterChartEl.value) return
  waterChart =
    echarts.getInstanceByDom(waterChartEl.value) ??
    echarts.init(waterChartEl.value, null, { renderer: 'svg' })

  waterChart.setOption({
    animation: false,
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#ffffff',
      borderColor: '#E2E8F0',
      borderWidth: 1,
      textStyle: { color: '#334155', fontSize: 12 },
    },
    grid: { left: 36, right: 12, top: 16, bottom: 28 },
    xAxis: {
      type: 'category',
      data: usageSeries.value.map((bucket) => bucket.label),
      axisLine: { lineStyle: { color: '#E2E8F0' } },
      axisTick: { show: false },
      axisLabel: { color: '#94A3B8', fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#94A3B8', fontSize: 11 },
      splitLine: { lineStyle: { color: '#E2E8F0', type: 'dashed' } },
    },
    series: [
      {
        type: 'bar',
        data: usageSeries.value.map((bucket) => bucket.volume_ml),
        barWidth: '48%',
        itemStyle: { color: '#3B82F6', borderRadius: [6, 6, 0, 0] },
      },
    ],
  }, { notMerge: true })
}

async function loadUsage(granularity = usageGranularity.value) {
  const result = await api.getWaterUsage(granularity)
  usageSeries.value = result.series ?? []
  await nextTick()
  refreshChart()
}

function setGranularity(granularity) {
  usageGranularity.value = granularity
  loadUsage(granularity)
}

async function loadRecordsPage(page = recordsPage.value) {
  const result = await api.getWaterRecordsPaged(page, 20)
  pagedRecords.value = result.items ?? []
  recordsPage.value = result.page ?? 1
  recordsPages.value = result.pages ?? 1
  recordsTotal.value = result.total ?? 0
}

function gotoRecordsPage(page) {
  loadRecordsPage(Math.max(1, Math.min(page, recordsPages.value)))
}

async function loadViewData() {
  try {
    await Promise.all([
      loadUsage(),
      loadRecordsPage(),
    ])
  } catch (error) {
    console.error('Failed to load water view data', error)
  }
}

async function loadControlData() {
  try {
    const [nextRecords, nextSchedules, nextSettings] = await Promise.all([
      api.getWaterRecords(),
      api.getWaterSchedules(),
      api.getWaterSettings(),
    ])
    records.value = nextRecords
    schedules.value = nextSchedules
    waterSettings.value = nextSettings
  } catch (error) {
    console.error('Failed to load water control data', error)
  }
}

async function loadActiveModeData() {
  if (uiStore.isControlMode) {
    await loadControlData()
  } else {
    await loadViewData()
  }
}

async function saveAutoWaterSettings() {
  waterSettings.value = await api.saveWaterSettings({
    autoOnMeow: waterSettings.value.autoOnMeow,
    delaySeconds: waterSettings.value.delaySeconds,
  })
}

async function toggleAutoOnMeow(event) {
  waterSettings.value.autoOnMeow = event.target.checked
  await saveAutoWaterSettings()
}

async function startPump() {
  await api.controlWaterPump({ action: 'start', duration: manualDuration.value, triggerType: 'manual' })
  await loadControlData()
}

async function stopPump() {
  await api.controlWaterPump({ action: 'stop' })
  await loadControlData()
}

async function saveSchedule() {
  const payload = {
    label: scheduleForm.value.label || '未命名计划',
    time: scheduleForm.value.time,
    duration_seconds: scheduleForm.value.duration_seconds,
    enabled: scheduleForm.value.enabled,
  }

  if (scheduleForm.value.id) {
    await api.updateWaterSchedule(scheduleForm.value.id, payload)
  } else {
    await api.createWaterSchedule(payload)
  }

  resetForm()
  await loadControlData()
}

function editSchedule(schedule) {
  scheduleForm.value = {
    id: schedule.id,
    label: schedule.label,
    time: schedule.time,
    duration_seconds: schedule.duration_seconds,
    enabled: schedule.enabled,
  }
}

async function toggleSchedule(schedule) {
  await api.updateWaterSchedule(schedule.id, { enabled: !schedule.enabled })
  await loadControlData()
}

async function removeSchedule(id) {
  await api.deleteWaterSchedule(id)
  if (scheduleForm.value.id === id) resetForm()
  await loadControlData()
}

function resetForm() {
  scheduleForm.value = {
    id: null,
    label: '',
    time: '08:30',
    duration_seconds: 15,
    enabled: true,
  }
}

function formatDateTime(isoString) {
  return isoString ? isoString.replace('T', ' ').slice(0, 16) : '--'
}

const onResize = () => waterChart?.resize()

watch(usageSeries, async () => {
  if (uiStore.isViewMode) {
    await nextTick()
    refreshChart()
  }
}, { deep: true })

watch(
  () => uiStore.mode,
  async () => {
    if (uiStore.isViewMode) resetForm()
    await nextTick()
    await loadActiveModeData()
    if (uiStore.isViewMode) {
      await nextTick()
      refreshChart()
    }
  },
)

onMounted(async () => {
  await loadActiveModeData()
  window.addEventListener('resize', onResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  try {
    waterChart?.dispose()
  } catch {}
  waterChart = null
})
</script>
