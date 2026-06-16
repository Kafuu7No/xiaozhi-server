<template>
  <AppLayout>
    <RouterView />
  </AppLayout>
</template>

<script setup>
import { onMounted } from 'vue'
import AppLayout from './layout/AppLayout.vue'
import { useWebSocket } from './composables/useWebSocket'
import { useApi } from './composables/useApi'
import { useDeviceStore } from './stores/deviceStore'

const { connect } = useWebSocket()
const api = useApi()
const store = useDeviceStore()

onMounted(async () => {
  connect()
  try { store.setDeviceStatus(await api.getDeviceStatus()) } catch {}
  try { store.setSensorUpdate(await api.getSensorLatest()) } catch {}
  try {
    const conversations = await api.getConversations(20)
    conversations.forEach((item) => store.addConversation(item))
  } catch {}
})
</script>
