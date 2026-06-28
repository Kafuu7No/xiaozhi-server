<template>
  <div class="page-shell">
    <div
      v-if="store.connected"
      class="online-banner"
    >
      <Wifi :size="16" class="shrink-0" />
      <span>设备已连接 · {{ store.deviceId || '未命名设备' }}</span>
    </div>
    <div v-else class="offline-banner">
      <WifiOff :size="16" class="shrink-0" />
      <span>设备离线，控制指令暂时不会下发。</span>
    </div>

    <section class="product-panel p-5 lg:p-6">
      <div class="max-w-2xl">
        <div class="section-label">设备控制</div>
        <h1 class="mt-3 text-2xl font-semibold text-[#17211b] lg:text-3xl">调节猫窝设备的声音、屏幕和灯光</h1>
        <p class="mt-2 text-sm leading-6 text-[#66756d]">
          这里的设置会直接发送到已连接设备；设备离线时可以查看状态，但不会执行控制指令。
        </p>
      </div>
    </section>

    <div class="grid grid-cols-1 gap-4 lg:grid-cols-3">
      <IotDeviceCard
        v-for="device in devices"
        :key="device.name"
        :name="device.name"
        :current-state="deviceStates[device.name]"
        :connected="store.connected"
      />
    </div>

    <div v-if="false" class="app-card">
      <div class="app-card-body">
        <div class="mb-4 flex items-center justify-between">
          <div>
            <div class="section-label">最近对话</div>
            <div class="mt-1 text-sm text-[#789083]">最近 20 条语音对话记录</div>
          </div>
        </div>

        <div v-if="!store.conversations.length" class="py-10 text-center text-sm text-[#789083]">
          暂无对话记录
        </div>

        <div v-else class="max-h-[28rem] divide-y divide-slate-100 overflow-y-auto">
          <div
            v-for="(message, index) in store.conversations.slice(-20)"
            :key="index"
            class="flex gap-4 py-3"
          >
            <span
              class="mt-0.5 w-10 shrink-0 text-xs font-semibold"
              :class="message.role === 'user' ? 'text-blue-600' : 'text-emerald-600'"
            >
              {{ message.role === 'user' ? '用户' : 'AI' }}
            </span>
            <span class="flex-1 text-sm leading-6 text-slate-700">{{ message.content }}</span>
            <span class="shrink-0 text-xs text-[#789083]">{{ fmtTime(message.recorded_at) }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Wifi, WifiOff } from 'lucide-vue-next'
import IotDeviceCard from '../components/IotDeviceCard.vue'
import { useDeviceStore } from '../stores/deviceStore'

const store = useDeviceStore()
const devices = [{ name: 'Speaker' }, { name: 'Screen' }, { name: 'Led' }]

const deviceStates = computed(() => {
  const map = {}
  for (const device of devices) {
    const matched = store.iotStates.find((state) => state.name === device.name)
    map[device.name] = matched?.state ?? {}
  }
  return map
})

function fmtTime(isoString) {
  return isoString ? isoString.replace('T', ' ').slice(5, 16) : '--'
}
</script>
