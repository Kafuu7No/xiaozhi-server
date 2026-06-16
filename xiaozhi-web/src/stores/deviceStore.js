import { defineStore } from 'pinia'
import { ref, shallowRef } from 'vue'

export const useDeviceStore = defineStore('device', () => {
  const connected = ref(false)
  const deviceId = ref(null)
  const state = ref('disconnected')
  const iotStates = shallowRef([])

  const latestSensor = shallowRef(null)
  const recentMeowEvents = shallowRef([])
  const meowStatus = shallowRef({
    desired_enabled: false,
    device_enabled: false,
    status: 'stopped',
    message: '',
    result: null,
    updated_at: null,
  })
  const conversations = shallowRef([])

  function setDeviceStatus(data) {
    deviceId.value = data.device_id
    state.value = data.state
    connected.value = data.connected
    if (data.iot_states) iotStates.value = data.iot_states
  }

  function setSensorUpdate(data) {
    latestSensor.value = data
  }

  function addMeowEvent(data) {
    const arr = [data, ...recentMeowEvents.value]
    recentMeowEvents.value = arr.length > 100 ? arr.slice(0, 100) : arr
  }

  function setMeowStatus(data) {
    meowStatus.value = { ...meowStatus.value, ...data }
  }

  function setIotStates(data) {
    if (data.states) iotStates.value = data.states
  }

  function addConversation(data) {
    const arr = [...conversations.value, data]
    conversations.value = arr.length > 200 ? arr.slice(-200) : arr
  }

  return {
    connected, deviceId, state, iotStates,
    latestSensor, recentMeowEvents, meowStatus, conversations,
    setDeviceStatus, setSensorUpdate, addMeowEvent, setMeowStatus, setIotStates, addConversation,
  }
})
