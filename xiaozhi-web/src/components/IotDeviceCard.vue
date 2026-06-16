<template>
  <div class="app-card">
    <div class="app-card-body space-y-5">
      <div class="flex items-center gap-3">
        <div class="flex h-10 w-10 items-center justify-center rounded-2xl bg-slate-100 text-slate-500">
          <component :is="icon" :size="18" />
        </div>
        <div>
          <div class="text-sm font-semibold text-slate-900">{{ name }}</div>
          <div class="text-xs text-slate-400">{{ subtitle }}</div>
        </div>
      </div>

      <template v-if="name === 'Speaker'">
        <div>
          <div class="mb-2 flex items-center justify-between text-sm">
            <span class="text-slate-500">音量</span>
            <span class="font-medium text-slate-900">{{ volume }}%</span>
          </div>
          <input
            v-model.number="volume"
            type="range"
            min="0"
            max="100"
            class="range range-primary range-sm w-full"
            :disabled="disabled"
            @change="send('SetVolume', { volume })"
          />
        </div>
      </template>

      <template v-else-if="name === 'Screen'">
        <div>
          <div class="mb-2 flex items-center justify-between text-sm">
            <span class="text-slate-500">亮度</span>
            <span class="font-medium text-slate-900">{{ brightness }}%</span>
          </div>
          <input
            v-model.number="brightness"
            type="range"
            min="0"
            max="100"
            class="range range-primary range-sm w-full"
            :disabled="disabled"
            @change="send('SetBrightness', { brightness })"
          />
        </div>
      </template>

      <template v-else-if="name === 'Led'">
        <div>
          <div class="mb-3 text-sm text-slate-500">颜色</div>
          <div class="flex flex-wrap gap-3">
            <button
              v-for="color in ledColors"
              :key="color.value"
              class="flex flex-col items-center gap-2"
              :disabled="disabled"
              @click="setLed(color.value)"
            >
              <span
                class="flex h-11 w-11 items-center justify-center rounded-2xl border transition-colors"
                :class="activeLed === color.value
                  ? 'border-slate-900 ring-2 ring-slate-200'
                  : 'border-slate-200'"
                :style="color.hex ? { backgroundColor: color.hex } : null"
              >
                <span v-if="!color.hex" class="text-xs font-semibold text-slate-500">ALL</span>
              </span>
              <span class="text-xs text-slate-400">{{ color.label }}</span>
            </button>
          </div>
        </div>
      </template>

      <div class="min-h-5 text-xs" :class="statusClass">
        {{ statusText }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Lightbulb, Monitor, Volume2 } from 'lucide-vue-next'
import { useApi } from '../composables/useApi'

const props = defineProps({
  name: String,
  currentState: { type: Object, default: () => ({}) },
  connected: { type: Boolean, default: false },
})

const api = useApi()
const volume = ref(props.currentState?.volume ?? 70)
const brightness = ref(props.currentState?.brightness ?? 50)
const activeLed = ref(props.currentState?.color ?? '')
const sending = ref(false)
const feedback = ref('')
let feedbackTimer = null

watch(
  () => props.currentState,
  (nextState) => {
    volume.value = nextState?.volume ?? 70
    brightness.value = nextState?.brightness ?? 50
    activeLed.value = nextState?.color ?? ''
  },
  { deep: true },
)

const icon = computed(() => {
  if (props.name === 'Speaker') return Volume2
  if (props.name === 'Screen') return Monitor
  return Lightbulb
})

const subtitle = computed(() => {
  if (props.name === 'Speaker') return '音量控制'
  if (props.name === 'Screen') return '亮度控制'
  return '灯光颜色切换'
})
const disabled = computed(() => sending.value || !props.connected)
const statusText = computed(() => {
  if (!props.connected) return '设备离线，控制指令不会下发'
  if (sending.value) return '正在发送指令…'
  return feedback.value
})
const statusClass = computed(() => {
  if (!props.connected) return 'text-amber-600'
  if (feedback.value.includes('失败')) return 'text-rose-500'
  if (feedback.value) return 'text-emerald-600'
  return 'text-slate-400'
})

const ledColors = [
  { value: 'red', label: '红', hex: '#ef4444' },
  { value: 'green', label: '绿', hex: '#22c55e' },
  { value: 'blue', label: '蓝', hex: '#3b82f6' },
  { value: 'off', label: '关', hex: '#e2e8f0' },
  { value: 'all', label: '全亮', hex: null },
]

async function send(method, parameters) {
  if (disabled.value) {
    feedback.value = props.connected ? '正在发送上一条指令' : '设备离线，无法发送'
    return
  }
  sending.value = true
  feedback.value = ''
  try {
    await api.sendIotCommand(props.name, method, parameters)
    feedback.value = method === 'SetVolume' ? '音量指令已下发到板端' : '指令已下发到板端'
    clearFeedbackLater()
  } catch (error) {
    feedback.value = error?.response?.data?.detail || '指令发送失败'
    console.error('IoT command failed', error)
  } finally {
    sending.value = false
  }
}

async function setLed(value) {
  if (disabled.value) return
  activeLed.value = value
  await send('SetLed', { color: value })
}

function clearFeedbackLater() {
  if (feedbackTimer) window.clearTimeout(feedbackTimer)
  feedbackTimer = window.setTimeout(() => {
    feedback.value = ''
    feedbackTimer = null
  }, 2500)
}
</script>
