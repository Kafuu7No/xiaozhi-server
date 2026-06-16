<template>
  <div class="w-full" :style="{ height }">
    <div
      v-if="!history.length"
      class="flex h-full items-center justify-center rounded-xl border border-dashed border-slate-200 text-sm text-slate-400"
    >
      暂无温湿度数据
    </div>
    <div v-else ref="chartEl" class="h-full w-full" />
  </div>
</template>

<script setup>
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import * as echarts from 'echarts/core'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { LineChart } from 'echarts/charts'
import { SVGRenderer } from 'echarts/renderers'

echarts.use([LineChart, GridComponent, TooltipComponent, LegendComponent, SVGRenderer])

const props = defineProps({
  history: { type: Array, default: () => [] },
  height: { type: String, default: '300px' },
})

const colors = {
  temp: '#3B82F6',
  humi: '#10B981',
  grid: '#E2E8F0',
  text: '#94A3B8',
}

const chartEl = ref(null)
let chart = null

function formatXAxis(sample) {
  if (typeof sample?.ts === 'number') {
    return new Date(sample.ts).toTimeString().slice(0, 5)
  }
  if (sample?.recorded_at) {
    return sample.recorded_at.slice(11, 16)
  }
  return '--:--'
}

function buildOption(rows) {
  return {
    animation: false,
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#ffffff',
      borderColor: colors.grid,
      borderWidth: 1,
      textStyle: { color: '#334155', fontSize: 12 },
    },
    legend: {
      top: 0,
      textStyle: { color: colors.text, fontSize: 12 },
      data: ['温度 °C', '湿度 %'],
    },
    grid: { left: 42, right: 48, top: 38, bottom: 24 },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: rows.map(formatXAxis),
      axisLine: { lineStyle: { color: colors.grid } },
      axisTick: { show: false },
      axisLabel: { color: colors.text, fontSize: 11 },
    },
    yAxis: [
      {
        type: 'value',
        name: '°C',
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: colors.text, fontSize: 11 },
        nameTextStyle: { color: colors.text, fontSize: 11 },
        splitLine: { lineStyle: { color: colors.grid, type: 'dashed' } },
      },
      {
        type: 'value',
        name: '%',
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: colors.text, fontSize: 11 },
        nameTextStyle: { color: colors.text, fontSize: 11 },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: '温度 °C',
        type: 'line',
        smooth: true,
        symbol: 'none',
        yAxisIndex: 0,
        data: rows.map((row) => row.temp_c),
        lineStyle: { color: colors.temp, width: 2.5 },
        itemStyle: { color: colors.temp },
        areaStyle: { color: 'rgba(59,130,246,0.08)' },
      },
      {
        name: '湿度 %',
        type: 'line',
        smooth: true,
        symbol: 'none',
        yAxisIndex: 1,
        data: rows.map((row) => row.humi_rh),
        lineStyle: { color: colors.humi, width: 2.5 },
        itemStyle: { color: colors.humi },
        areaStyle: { color: 'rgba(16,185,129,0.08)' },
      },
    ],
  }
}

function ensureChart() {
  if (!chartEl.value) return
  chart = echarts.getInstanceByDom(chartEl.value) ?? echarts.init(chartEl.value, null, { renderer: 'svg' })
}

function destroyChart() {
  try {
    chart?.dispose()
  } catch {}
  chart = null
}

const onResize = () => chart?.resize()

onMounted(async () => {
  if (props.history.length) {
    await nextTick()
    ensureChart()
    chart?.setOption(buildOption(props.history))
  }
  window.addEventListener('resize', onResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  destroyChart()
})

watch(
  () => props.history,
  async (rows) => {
    if (!rows.length) {
      destroyChart()
      return
    }
    await nextTick()
    ensureChart()
    chart?.setOption(buildOption(rows), { notMerge: true })
  },
  { deep: true },
)
</script>
