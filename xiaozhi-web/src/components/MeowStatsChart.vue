<template>
  <div ref="chartEl" class="w-full" :style="{ height }" />
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as echarts from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { SVGRenderer } from 'echarts/renderers'

echarts.use([BarChart, GridComponent, TooltipComponent, SVGRenderer])

const props = defineProps({
  stats:  { type: Object, default: () => ({ count_24h: 0, count_48h: 0, count_week: 0 }) },
  height: { type: String, default: '220px' },
})

const C = { grid: '#e2e8f0', text: '#94a3b8' }

const chartEl = ref(null)
let chart = null

function buildOption(s) {
  return {
    animation: false,
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#fff',
      borderColor: C.grid,
      borderWidth: 1,
      textStyle: { color: '#334155', fontSize: 12 },
    },
    grid: { left: 32, right: 16, bottom: 24, top: 16, containLabel: false },
    xAxis: {
      type: 'category',
      data: ['24 小时', '48 小时', '本周'],
      axisLine: { lineStyle: { color: C.grid } },
      axisTick: { show: false },
      axisLabel: { color: C.text, fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      axisLabel: { color: C.text, fontSize: 11 },
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: C.grid, type: 'dashed' } },
    },
    series: [{
      type: 'bar',
      barWidth: '40%',
      data: [s.count_24h, s.count_48h, s.count_week],
      itemStyle: {
        color: '#3b82f6',
        borderRadius: [4, 4, 0, 0],
      },
    }],
  }
}

const onResize = () => chart?.resize()

onMounted(() => {
  chart = echarts.getInstanceByDom(chartEl.value)
        ?? echarts.init(chartEl.value, null, { renderer: 'svg' })
  chart.setOption(buildOption(props.stats))
  window.addEventListener('resize', onResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  try { chart?.dispose() } catch {}
  chart = null
})

watch(() => props.stats, s => {
  chart?.setOption(buildOption(s), { notMerge: false })
})
</script>
