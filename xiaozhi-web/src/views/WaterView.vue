<template>
  <div class="page-shell">
    <template v-if="uiStore.isControlMode">
      <div class="app-card">
        <div class="app-card-body space-y-4">
          <div>
            <div class="section-label">手动出水</div>
            <div class="mt-1 text-sm text-[#789083]">点击后水泵会马上出水指定秒数，并记录到历史中</div>
          </div>

          <div class="flex flex-wrap items-end gap-3">
            <label class="w-full max-w-xs text-sm text-[#66756d]">
              运行时长
              <div class="mt-2 flex items-center gap-2">
                <input
                  v-model.number="manualDuration"
                  type="number"
                  min="1"
                  max="120"
                  class="input input-bordered w-full"
                />
                <span class="text-[#789083]">秒</span>
              </div>
            </label>
            <button class="btn btn-primary" @click="startPump">立即出水</button>
            <button class="btn btn-outline" @click="stopPump">停止</button>
          </div>

          <div class="rounded-lg bg-[#f7fbf7] px-4 py-3 text-sm text-[#66756d]">
            最近一次出水：
            <span class="font-medium text-[#17211b]">{{ latestRecordSummary }}</span>
          </div>

          <div class="border-t border-[#dce8de] pt-4">
            <div class="flex items-center justify-between gap-4">
              <div>
                <div class="text-sm font-medium text-[#17211b]">听到猫叫后自动出水</div>
                <div class="mt-1 text-xs text-[#789083]">
                  开启后，设备在 10 秒内听到 3 次猫叫，会自动出水一次；60 秒内不会重复触发。
                </div>
              </div>
              <input
                :checked="waterSettings.autoOnMeow"
                type="checkbox"
                class="toggle toggle-primary"
                aria-label="听到猫叫后自动出水"
                @change="toggleAutoOnMeow"
              />
            </div>
            <label
              v-if="waterSettings.autoOnMeow"
              class="mt-3 flex max-w-xs items-center gap-2 text-sm text-[#66756d]"
            >
              自动出水时长
              <input
                v-model.number="waterSettings.delaySeconds"
                type="number"
                min="1"
                max="120"
                class="input input-bordered input-sm w-24"
                aria-label="自动出水时长"
                @change="saveAutoWaterSettings"
              />
              <span class="text-[#789083]">秒</span>
            </label>
          </div>
        </div>
      </div>

      <div class="grid grid-cols-1 gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <div class="app-card">
          <div class="app-card-body">
            <div class="mb-4">
              <div class="section-label">定时计划</div>
              <div class="mt-1 text-sm text-[#789083]">支持新增、编辑、启停与删除</div>
            </div>

            <div class="grid grid-cols-1 gap-3 rounded-lg bg-[#f7fbf7] p-4 md:grid-cols-[1fr_140px_140px_auto]">
              <input
                v-model="scheduleForm.label"
                type="text"
                class="input input-bordered w-full"
                placeholder="计划名称"
                aria-label="计划名称"
              />
              <input v-model="scheduleForm.time" type="time" class="input input-bordered w-full" aria-label="计划时间" />
              <input
                v-model.number="scheduleForm.duration_seconds"
                type="number"
                min="1"
                max="120"
                class="input input-bordered w-full"
                placeholder="时长"
                aria-label="计划出水时长"
              />
              <button class="btn btn-primary" @click="saveSchedule">
                {{ scheduleForm.id ? '更新计划' : '新增计划' }}
              </button>
            </div>

            <div v-if="!schedules.length" class="py-10 text-center text-sm text-[#789083]">
              暂无计划
            </div>

            <div v-else class="mt-4 overflow-x-auto">
              <table class="table">
                <thead>
                  <tr class="text-[#789083]">
                    <th>名称</th>
                    <th>时间</th>
                    <th>时长</th>
                    <th>状态</th>
                    <th class="text-right">操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="schedule in schedules" :key="schedule.id">
                    <td class="font-medium text-[#17211b]">{{ schedule.label }}</td>
                    <td class="text-[#66756d]">{{ schedule.time }}</td>
                    <td class="text-[#66756d]">{{ schedule.duration_seconds }} 秒</td>
                    <td>
                      <input
                        :checked="schedule.enabled"
                        type="checkbox"
                        class="toggle toggle-primary toggle-sm"
                        :aria-label="`${schedule.label} 是否启用`"
                        @change="toggleSchedule(schedule)"
                      />
                    </td>
                    <td>
                      <div class="flex justify-end gap-2">
                        <button class="btn btn-ghost btn-sm" @click="editSchedule(schedule)">编辑</button>
                        <button class="btn btn-ghost btn-sm text-red-500" @click="requestRemoveSchedule(schedule)">
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
              <div v-if="!records.length" class="py-10 text-center text-sm text-[#789083]">暂无出水记录</div>
              <template v-else>
                <div
                  v-for="record in records.slice(0, 5)"
                  :key="record.id"
                  class="rounded-lg border border-[#dce8de] px-3 py-2 text-sm"
                >
                  <div class="font-medium text-[#17211b]">{{ formatDateTime(record.started_at) }}</div>
                  <div class="mt-1 text-[#66756d]">
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
      <section class="product-panel p-5 lg:p-6">
        <div class="grid gap-5 lg:grid-cols-[1.1fr_0.9fr] lg:items-center">
          <div>
            <div class="status-chip">
              <span class="h-2.5 w-2.5 rounded-full bg-[#2f80b7]" />
              饮水观察
            </div>
            <h1 class="mt-4 text-2xl font-semibold text-[#17211b] lg:text-3xl">{{ waterSummaryTitle }}</h1>
            <p class="mt-2 max-w-2xl text-sm leading-6 text-[#66756d]">{{ waterSummaryText }}</p>
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div class="soft-panel px-4 py-4">
              <div class="section-label">最近出水</div>
              <div class="mt-2 text-2xl font-semibold text-[#2f80b7]">{{ latestViewVolume }}<span class="text-sm text-[#789083]"> ml</span></div>
            </div>
            <div class="soft-panel px-4 py-4">
              <div class="section-label">记录数</div>
              <div class="mt-2 text-2xl font-semibold text-[#17211b]">{{ recordsTotal }}</div>
            </div>
          </div>
        </div>
      </section>

      <div class="app-card">
        <div class="app-card-body">
          <div class="mb-4 flex items-center justify-between gap-3">
            <div>
              <div class="section-label">饮水量</div>
              <div class="mt-1 text-sm text-[#789083]">
                {{ usageGranularity === 'hour' ? '最近 24 小时每小时出水量' : '最近 7 天每日出水量' }}
              </div>
            </div>
            <div class="tabs tabs-boxed bg-[#eef6f0] p-1">
              <button
                class="tab h-8 min-h-8 rounded-md px-3 text-xs"
                :class="usageGranularity === 'hour' ? 'tab-active bg-[#fffefa] text-[#17211b] shadow-sm' : 'text-[#66756d]'"
                @click="setGranularity('hour')"
              >按小时</button>
              <button
                class="tab h-8 min-h-8 rounded-md px-3 text-xs"
                :class="usageGranularity === 'day' ? 'tab-active bg-[#fffefa] text-[#17211b] shadow-sm' : 'text-[#66756d]'"
                @click="setGranularity('day')"
              >按天</button>
            </div>
          </div>
          <div class="relative h-72 w-full">
            <div ref="waterChartEl" class="h-full w-full" />
            <div
              v-if="!usageSeries.length"
              class="absolute inset-0 flex items-center justify-center text-sm text-[#789083]"
            >
              暂无饮水趋势数据
            </div>
          </div>
        </div>
      </div>

      <div class="app-card">
        <div class="app-card-body">
          <div class="mb-4 flex items-center justify-between">
            <div>
              <div class="section-label">出水记录</div>
              <div class="mt-1 text-sm text-[#789083]">每页 20 条，按时间倒序</div>
            </div>
            <span class="text-sm text-[#789083]">共 {{ recordsTotal }} 条</span>
          </div>

          <div v-if="!pagedRecords.length" class="py-10 text-center text-sm text-[#789083]">
            暂无出水记录
          </div>

          <div v-else class="overflow-x-auto">
            <table class="table">
              <thead>
                <tr class="text-[#789083]">
                  <th>开始时间</th>
                  <th>触发方式</th>
                  <th>时长</th>
                  <th>估算水量</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="record in pagedRecords" :key="record.id">
                  <td class="text-sm text-[#66756d]">{{ formatDateTime(record.started_at) }}</td>
                  <td class="font-medium text-[#17211b]">{{ triggerLabelMap[record.trigger_type] || record.trigger_type }}</td>
                  <td class="text-[#66756d]">{{ record.duration_seconds }} 秒</td>
                  <td class="text-[#66756d]">{{ record.volume_ml ?? record.duration_seconds * 3 }} ml</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div v-if="recordsPages > 1" class="mt-4 flex items-center justify-end gap-2 text-sm">
            <button class="btn btn-ghost btn-sm" :disabled="recordsPage <= 1" @click="gotoRecordsPage(recordsPage - 1)">上一页</button>
            <span class="text-[#66756d]">第 {{ recordsPage }} / {{ recordsPages }} 页</span>
            <button class="btn btn-ghost btn-sm" :disabled="recordsPage >= recordsPages" @click="gotoRecordsPage(recordsPage + 1)">下一页</button>
          </div>
        </div>
      </div>
    </template>

    <div
      v-if="pendingDeleteSchedule"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="delete-schedule-title"
      @click.self="cancelRemoveSchedule"
    >
      <div class="w-full max-w-sm rounded-lg bg-[#fffefa] p-5 shadow-xl">
        <div id="delete-schedule-title" class="text-base font-semibold text-[#17211b]">确认删除计划</div>
        <div class="mt-2 text-sm leading-6 text-[#66756d]">
          删除“{{ pendingDeleteSchedule.label }}”后，设备不会再按 {{ pendingDeleteSchedule.time }} 自动出水。
        </div>
        <div class="mt-4 flex justify-end gap-2">
          <button class="btn btn-ghost btn-sm" @click="cancelRemoveSchedule">取消</button>
          <button class="btn btn-error btn-sm text-white" @click="confirmRemoveSchedule">删除计划</button>
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
const pendingDeleteSchedule = ref(null)

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
const latestViewRecord = computed(() => pagedRecords.value[0] ?? records.value[0] ?? null)
const latestViewVolume = computed(() => {
  const latest = latestViewRecord.value
  if (!latest) return '--'
  return latest.volume_ml ?? latest.duration_seconds * 3
})
const waterSummaryTitle = computed(() => {
  if (!latestViewRecord.value) return '还没有记录到出水'
  return '饮水记录正在持续更新'
})
const waterSummaryText = computed(() => {
  const latest = latestViewRecord.value
  if (!latest) return '当水泵被手动、定时或猫叫联动触发后，这里会展示最近一次出水和长期趋势。'
  return `最近一次出水在 ${formatDateTime(latest.started_at)}，由 ${triggerLabelMap[latest.trigger_type] || latest.trigger_type} 触发，估算 ${latestViewVolume.value} ml。`
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
      backgroundColor: '#fffefa',
      borderColor: '#dce8de',
      borderWidth: 1,
      textStyle: { color: '#17211b', fontSize: 12 },
    },
    grid: { left: 36, right: 12, top: 16, bottom: 28 },
    xAxis: {
      type: 'category',
      data: usageSeries.value.map((bucket) => bucket.label),
      axisLine: { lineStyle: { color: '#dce8de' } },
      axisTick: { show: false },
      axisLabel: { color: '#789083', fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#789083', fontSize: 11 },
      splitLine: { lineStyle: { color: '#dce8de', type: 'dashed' } },
    },
    series: [
      {
        type: 'bar',
        data: usageSeries.value.map((bucket) => bucket.volume_ml),
        barWidth: '48%',
        itemStyle: { color: '#2f80b7', borderRadius: [6, 6, 0, 0] },
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

function requestRemoveSchedule(schedule) {
  pendingDeleteSchedule.value = schedule
}

function cancelRemoveSchedule() {
  pendingDeleteSchedule.value = null
}

async function confirmRemoveSchedule() {
  const schedule = pendingDeleteSchedule.value
  if (!schedule) return
  await api.deleteWaterSchedule(schedule.id)
  if (scheduleForm.value.id === schedule.id) resetForm()
  pendingDeleteSchedule.value = null
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
