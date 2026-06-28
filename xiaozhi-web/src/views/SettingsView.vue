<template>
  <div class="mx-auto w-full max-w-3xl space-y-5">
    <div v-if="error" class="rounded-lg border border-rose-100 bg-rose-50 px-4 py-3 text-sm text-rose-600">
      {{ error }}
    </div>

    <div class="app-card">
      <div class="border-b border-[#dce8de] px-5 py-3">
        <div class="text-sm font-semibold text-[#17211b]">提醒与保存规则</div>
        <div class="mt-0.5 text-xs text-[#789083]">保存后会影响猫叫记录、饮水联动和温湿度提醒</div>
      </div>
      <div class="divide-y divide-slate-100">
        <div class="flex flex-wrap items-center justify-between gap-4 px-5 py-4">
          <div>
            <div class="text-sm font-medium text-[#17211b]">猫叫保存门槛</div>
            <div class="mt-1 text-xs text-[#789083]">
              识别把握度低于这个数值的声音不会保存、统计或触发提醒。门槛越高，误报越少，但可能漏掉轻微猫叫。
            </div>
          </div>
          <div class="flex min-w-56 items-center gap-3">
            <input
              v-model.number="settings.meowMinConfidence"
              type="range"
              min="0.1"
              max="0.95"
              step="0.05"
              class="range range-primary range-sm flex-1"
              aria-label="猫叫保存门槛"
            />
            <span class="w-14 rounded-full bg-[#eef6f0] px-3 py-1 text-center text-sm font-semibold text-slate-700">
              {{ (settings.meowMinConfidence * 100).toFixed(0) }}%
            </span>
          </div>
        </div>

        <div class="flex items-center justify-between gap-4 px-5 py-4">
          <div>
            <div class="text-sm font-medium text-[#17211b]">温度偏高提醒线</div>
            <div class="mt-1 text-xs text-[#789083]">高于这个温度时，页面会提醒你留意猫窝环境</div>
          </div>
          <div class="flex items-center gap-2">
            <input v-model.number="settings.tempMax" type="number" min="20" max="50" class="input input-bordered w-24" aria-label="温度偏高提醒线" />
            <span class="text-sm text-[#789083]">°C</span>
          </div>
        </div>

        <div class="flex items-center justify-between gap-4 px-5 py-4">
          <div>
            <div class="text-sm font-medium text-[#17211b]">湿度偏低提醒线</div>
            <div class="mt-1 text-xs text-[#789083]">低于这个湿度时，页面会提醒环境偏干</div>
          </div>
          <div class="flex items-center gap-2">
            <input v-model.number="settings.humidMin" type="number" min="10" max="60" class="input input-bordered w-24" aria-label="湿度偏低提醒线" />
            <span class="text-sm text-[#789083]">%</span>
          </div>
        </div>

        <div class="flex items-center justify-between gap-4 px-5 py-4">
          <div>
            <div class="text-sm font-medium text-[#17211b]">湿度偏高提醒线</div>
            <div class="mt-1 text-xs text-[#789083]">高于这个湿度时，页面会提醒环境偏潮</div>
          </div>
          <div class="flex items-center gap-2">
            <input v-model.number="settings.humidMax" type="number" min="40" max="95" class="input input-bordered w-24" aria-label="湿度偏高提醒线" />
            <span class="text-sm text-[#789083]">%</span>
          </div>
        </div>
      </div>
    </div>

    <div class="flex items-center gap-3">
      <button class="btn btn-primary" :disabled="loading" @click="save">保存设置</button>
      <span v-if="saved" class="text-sm text-emerald-600">已保存</span>
      <span v-else-if="loading" class="text-sm text-[#789083]">加载中…</span>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useApi } from '../composables/useApi'

const api = useApi()

const settings = ref({
  meowThreshold: 0.8,
  meowMinConfidence: 0.4,
  tempMax: 35,
  humidMin: 30,
  humidMax: 80,
  autoOnMeow: false,
  delaySeconds: 15,
})
const saved = ref(false)
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    settings.value = await api.getAppSettings()
  } catch (e) {
    error.value = '加载设置失败，请确认后端服务已启动'
    console.error('Failed to load settings', e)
  } finally {
    loading.value = false
  }
})

async function save() {
  error.value = ''
  try {
    settings.value = await api.saveAppSettings(settings.value)
    saved.value = true
    window.setTimeout(() => {
      saved.value = false
    }, 2000)
  } catch (e) {
    error.value = '保存失败，请确认后端服务已启动'
    console.error('Failed to save settings', e)
  }
}
</script>
