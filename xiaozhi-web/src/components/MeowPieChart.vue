<template>
  <div class="w-full flex items-center justify-center" :style="{ height }">
    <div v-if="isEmpty" class="text-sm text-base-content/30">暂无数据</div>
    <div v-else ref="chartEl" class="w-full h-full" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import * as echarts from 'echarts/core'
import { PieChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent } from 'echarts/components'
import { SVGRenderer } from 'echarts/renderers'

echarts.use([PieChart, TooltipComponent, LegendComponent, SVGRenderer])

const props = defineProps({
  events: { type: Array, default: () => [] },
  height: { type: String, default: '220px' },
})

const C = { grid: '#e2e8f0', text: '#94a3b8' }
const chartEl = ref(null)
let chart = null

const catCount   = computed(() => props.events.filter(e => e.is_cat).length)
const noiseCount = computed(() => props.events.length - catCount.value)
const isEmpty    = computed(() => catCount.value === 0 && noiseCount.value === 0)

function buildOption() {
  return {
    animation: false,
    tooltip: {
      trigger: 'item',
      backgroundColor: '#fff',
      borderColor: C.grid,
      borderWidth: 1,
      textStyle: { color: '#334155', fontSize: 12 },
      formatter: '{b}: {c} ({d}%)',
    },
    legend: { bottom: 0, textStyle: { color: C.text, fontSize: 12 } },
    series: [{
      type: 'pie',
      radius: ['40%', '65%'],
      center: ['50%', '44%'],
      itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 2 },
      label: { show: false },
      data: [
        { value: catCount.value,   name: '猫叫', itemStyle: { color: '#3b82f6' } },
        { value: noiseCount.value, name: '噪声', itemStyle: { color: '#e2e8f0' } },
      ],
    }],
  }
}

function initChart() {
  if (!chartEl.value || chart) return
  chart = echarts.getInstanceByDom(chartEl.value)
        ?? echarts.init(chartEl.value, null, { renderer: 'svg' })
  chart.setOption(buildOption())
}

function destroyChart() {
  try { chart?.dispose() } catch {}
  chart = null
}

const onResize = () => chart?.resize()

onMounted(() => {
  if (!isEmpty.value) initChart()
  window.addEventListener('resize', onResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  destroyChart()
})

watch(
  () => props.events,
  async () => {
    if (isEmpty.value) {
      destroyChart()
      return
    }
    await nextTick()
    if (!chart) {
      initChart()
    } else {
      chart.setOption(buildOption(), { notMerge: true })
    }
  },
  { deep: true }
)
</script>
