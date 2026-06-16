import { onUnmounted, ref } from 'vue'
import { useDeviceStore } from '../stores/deviceStore'

export function useWebSocket() {
  const store = useDeviceStore()
  const wsStatus = ref('disconnected')

  let ws = null
  let retryTimer = null
  let destroyed = false

  function connect() {
    if (destroyed) return
    if (ws && (ws.readyState === WebSocket.CONNECTING || ws.readyState === WebSocket.OPEN)) return

    const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
    const url = `${protocol}://${location.host}/ws/dashboard`

    wsStatus.value = 'connecting'
    try {
      ws = new WebSocket(url)
    } catch (error) {
      console.warn('[WS] Failed to create WebSocket:', error)
      scheduleRetry()
      return
    }

    ws.onopen = () => {
      wsStatus.value = 'connected'
      clearRetry()
    }

    ws.onmessage = (event) => {
      try {
        const { event: eventName, data } = JSON.parse(event.data)
        switch (eventName) {
          case 'device_status':
            store.setDeviceStatus(data)
            break
          case 'sensor_update':
            store.setSensorUpdate(data)
            break
          case 'sensor_alert':
            store.setSensorUpdate(data)
            break
          case 'meow_event':
            store.addMeowEvent(data)
            break
          case 'meow_status':
            store.setMeowStatus(data)
            break
          case 'iot_state_changed':
            store.setIotStates(data)
            break
          case 'conversation':
            store.addConversation(data)
            break
        }
      } catch (error) {
        console.warn('[WS] Parse error:', error)
      }
    }

    ws.onclose = () => {
      wsStatus.value = 'disconnected'
      ws = null
      scheduleRetry()
    }

    ws.onerror = (error) => {
      console.warn('[WS] Connection error:', error)
    }
  }

  function scheduleRetry() {
    if (destroyed || retryTimer) return
    retryTimer = setTimeout(() => {
      retryTimer = null
      connect()
    }, 3000)
  }

  function clearRetry() {
    if (!retryTimer) return
    clearTimeout(retryTimer)
    retryTimer = null
  }

  function disconnect() {
    destroyed = true
    clearRetry()
    if (ws) {
      ws.onclose = null
      ws.onerror = null
      ws.onmessage = null
      ws.close()
      ws = null
    }
    wsStatus.value = 'disconnected'
  }

  onUnmounted(disconnect)

  return { wsStatus, connect, disconnect }
}
