<template>
  <div class="flex items-center gap-2 text-sm">
    <span
      class="inline-block w-2 h-2 rounded-full"
      :class="store.connected ? 'bg-success' : 'bg-base-300'"
    />
    <span class="text-base-content/60">
      {{ store.connected ? `在线 · ${store.state}` : '离线' }}
    </span>
  </div>
</template>

<script setup>
import { useDeviceStore } from '../stores/deviceStore'
const store = useDeviceStore()
</script>
