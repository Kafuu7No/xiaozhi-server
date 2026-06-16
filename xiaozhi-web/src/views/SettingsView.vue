<template>
  <div class="mx-auto max-w-3xl space-y-4">
    <div v-if="error" class="rounded-xl border border-rose-100 bg-rose-50 px-4 py-3 text-sm text-rose-600">
      {{ error }}
    </div>

    <div class="app-card">
      <div class="border-b border-slate-100 px-5 py-3">
        <div class="text-sm font-semibold text-slate-900">检测阈值</div>
        <div class="mt-0.5 text-xs text-slate-400">保存后由后端存储，并实时影响猫叫判定与温湿度告警</div>
      </div>
      <div class="divide-y divide-slate-100">
        <div class="flex items-center justify-between gap-4 px-5 py-4">
          <div>
            <div class="text-sm font-medium text-slate-900">事件保存下限</div>
            <div class="mt-1 text-xs text-slate-400">低于此置信度的声音事件不入库、不统计、不推送</div>
          </div>
          <span class="rounded-full bg-slate-100 px-3 py-1 text-sm font-semibold text-slate-700">
            {{ (settings.meowMinConfidence * 100).toFixed(0) }}%
          </span>
        </div>

        <div class="flex items-center justify-between gap-4 px-5 py-4">
          <div>
            <div class="text-sm font-medium text-slate-900">温度告警上限</div>
            <div class="mt-1 text-xs text-slate-400">高于此值时展示温度告警</div>
          </div>
          <div class="flex items-center gap-2">
            <input v-model.number="settings.tempMax" type="number" min="20" max="50" class="input input-bordered w-24" />
            <span class="text-sm text-slate-400">°C</span>
          </div>
        </div>

        <div class="flex items-center justify-between gap-4 px-5 py-4">
          <div>
            <div class="text-sm font-medium text-slate-900">湿度告警下限</div>
            <div class="mt-1 text-xs text-slate-400">低于此值时展示湿度偏低告警</div>
          </div>
          <div class="flex items-center gap-2">
            <input v-model.number="settings.humidMin" type="number" min="10" max="60" class="input input-bordered w-24" />
            <span class="text-sm text-slate-400">%</span>
          </div>
        </div>

        <div class="flex items-center justify-between gap-4 px-5 py-4">
          <div>
            <div class="text-sm font-medium text-slate-900">湿度告警上限</div>
            <div class="mt-1 text-xs text-slate-400">高于此值时展示湿度偏高告警</div>
          </div>
          <div class="flex items-center gap-2">
            <input v-model.number="settings.humidMax" type="number" min="40" max="95" class="input input-bordered w-24" />
            <span class="text-sm text-slate-400">%</span>
          </div>
        </div>
      </div>
    </div>

    <div class="flex items-center gap-3">
      <button class="btn btn-primary" :disabled="loading" @click="save">保存设置</button>
      <span v-if="saved" class="text-sm text-emerald-600">已保存</span>
      <span v-else-if="loading" class="text-sm text-slate-400">加载中…</span>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useApi } from '../composables/useApi'

const api = useApi()

const settings = ref({
  meowThreshold: 0.8,
  meowMinConfidence: 0.5,
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
