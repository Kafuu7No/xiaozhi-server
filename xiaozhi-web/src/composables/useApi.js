import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 6000,
})

const STORAGE_KEYS = {
  waterRecords: 'xiaozhi_mock_water_records',
  waterSchedules: 'xiaozhi_mock_water_schedules',
  waterSettings: 'xiaozhi_mock_water_settings',
}

const DEFAULT_WATER_SETTINGS = {
  autoOnMeow: false,
  delaySeconds: 15,
}

function readStored(key, fallback) {
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) : fallback
  } catch {
    return fallback
  }
}

function writeStored(key, value) {
  localStorage.setItem(key, JSON.stringify(value))
  return value
}

function uid(prefix) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

function buildMockWaterRecords() {
  const now = new Date()
  return Array.from({ length: 9 }, (_, index) => {
    const startedAt = new Date(now)
    startedAt.setDate(now.getDate() - index)
    startedAt.setHours(8 + (index % 3) * 4, 10, 0, 0)
    const duration = 10 + (index % 4) * 5
    const endedAt = new Date(startedAt.getTime() + duration * 1000)
    return {
      id: uid('record'),
      trigger_type: index % 3 === 0 ? 'meow_linkage' : index % 2 === 0 ? 'schedule' : 'manual',
      duration_seconds: duration,
      started_at: startedAt.toISOString(),
      ended_at: endedAt.toISOString(),
      volume_ml: duration * 3,
      is_mock: true,
    }
  }).sort((a, b) => b.started_at.localeCompare(a.started_at))
}

function ensureWaterRecords() {
  const records = readStored(STORAGE_KEYS.waterRecords, null)
  if (records && records.length) return records
  return writeStored(STORAGE_KEYS.waterRecords, buildMockWaterRecords())
}

function ensureWaterSchedules() {
  const schedules = readStored(STORAGE_KEYS.waterSchedules, null)
  if (schedules && schedules.length) return schedules
  return writeStored(STORAGE_KEYS.waterSchedules, [
    {
      id: uid('schedule'),
      label: '早晨补水',
      time: '08:30',
      duration_seconds: 15,
      enabled: true,
      is_mock: true,
    },
    {
      id: uid('schedule'),
      label: '晚间补水',
      time: '20:00',
      duration_seconds: 20,
      enabled: false,
      is_mock: true,
    },
  ])
}

function ensureWaterSettings() {
  return readStored(STORAGE_KEYS.waterSettings, DEFAULT_WATER_SETTINGS)
}

async function requestWithFallback(request, fallback) {
  try {
    const response = await request()
    return response.data
  } catch (error) {
    if (!fallback) throw error
    return fallback(error)
  }
}

export function useApi() {
  const getDeviceStatus = () => api.get('/device/status').then((response) => response.data)
  const getSensorLatest = () => api.get('/sensor/latest').then((response) => response.data)
  const getSensorHistory = (hours = 24) =>
    api.get('/sensor/history', { params: { hours } }).then((response) => response.data)
  const getSensorStats = (hours = 24) =>
    api.get('/sensor/stats', { params: { hours } }).then((response) => response.data)
  const getSensorThresholds = () =>
    api.get('/sensor/thresholds').then((response) => response.data)
  const getMeowEvents = (hours = 24, is_cat) =>
    api.get('/meow/events', { params: { hours, is_cat } }).then((response) => response.data)
  const getMeowStats = () => api.get('/meow/stats').then((response) => response.data)
  const setMeowControl = (action) =>
    api.post('/meow/control', { action }).then((response) => response.data)
  const getConversations = (limit = 50) =>
    api.get('/conversations', { params: { limit } }).then((response) => response.data)
  const getAppSettings = () => api.get('/settings').then((response) => response.data)
  const saveAppSettings = (payload) =>
    api.put('/settings', payload).then((response) => response.data)
  const sendIotCommand = (device_name, method, parameters = {}) =>
    api.post('/iot/command', { device_name, method, parameters }).then((response) => response.data)
  const mockSensor = () => api.post('/mock/sensor').then((response) => response.data)
  const mockMeow = () => api.post('/mock/meow').then((response) => response.data)

  const getLatestPhoto = () =>
    requestWithFallback(
      () => api.get('/camera/latest'),
      () => ({ photo: null, device_connected: false }),
    )

  const triggerCapture = () =>
    api.post('/camera/capture').then((response) => response.data)

  const getPhotos = (page = 1, pageSize = 15) =>
    requestWithFallback(
      () => api.get('/camera/photos', { params: { page, page_size: pageSize } }),
      () => ({ photos: [], total: 0, page: 1, page_size: pageSize, pages: 1 }),
    )

  const deletePhoto = (id) =>
    api.delete(`/camera/photos/${id}`).then((response) => response.data)

  const getSensorRecords = (page = 1, pageSize = 20) =>
    requestWithFallback(
      () => api.get('/sensor/records', { params: { page, page_size: pageSize } }),
      () => ({ items: [], total: 0, page: 1, page_size: pageSize, pages: 1 }),
    )

  const getWaterRecordsPaged = (page = 1, pageSize = 20) =>
    requestWithFallback(
      () => api.get('/water/records/paged', { params: { page, page_size: pageSize } }),
      () => ({ items: [], total: 0, page: 1, page_size: pageSize, pages: 1 }),
    )

  const getWaterUsage = (granularity = 'day') =>
    requestWithFallback(
      () => api.get('/water/usage', { params: { granularity } }),
      () => ({ granularity, series: [] }),
    )

  const getWaterRecords = () =>
    requestWithFallback(
      () => api.get('/water/records'),
      () => ensureWaterRecords(),
    )

  const controlWaterPump = ({ action = 'start', duration = 15, triggerType = 'manual' } = {}) =>
    requestWithFallback(
      () => api.post('/water/pump/control', { action, duration, trigger_type: triggerType }),
      () => {
        const records = ensureWaterRecords()
        if (action === 'stop') {
          const activeRecord = records.find((record) => !record.ended_at)
          if (!activeRecord) {
            return { status: 'mocked', stopped: false }
          }
          activeRecord.ended_at = new Date().toISOString()
          writeStored(STORAGE_KEYS.waterRecords, records)
          return { status: 'mocked', stopped: true, record: activeRecord }
        }

        const startedAt = new Date()
        const endedAt = new Date(startedAt.getTime() + duration * 1000)
        const record = {
          id: uid('record'),
          trigger_type: triggerType,
          duration_seconds: duration,
          started_at: startedAt.toISOString(),
          ended_at: endedAt.toISOString(),
          volume_ml: duration * 3,
          is_mock: true,
        }
        writeStored(STORAGE_KEYS.waterRecords, [record, ...records])
        return { status: 'mocked', record }
      },
    )

  const getWaterSchedules = () =>
    requestWithFallback(
      () => api.get('/water/schedule'),
      () => ensureWaterSchedules(),
    )

  const createWaterSchedule = (schedule) =>
    requestWithFallback(
      () => api.post('/water/schedule', schedule),
      () => {
        const schedules = ensureWaterSchedules()
        const nextSchedule = {
          id: uid('schedule'),
          enabled: true,
          is_mock: true,
          ...schedule,
        }
        writeStored(STORAGE_KEYS.waterSchedules, [...schedules, nextSchedule])
        return nextSchedule
      },
    )

  const updateWaterSchedule = (id, payload) =>
    requestWithFallback(
      () => api.put(`/water/schedule/${id}`, payload),
      () => {
        const schedules = ensureWaterSchedules().map((schedule) =>
          schedule.id === id ? { ...schedule, ...payload } : schedule,
        )
        writeStored(STORAGE_KEYS.waterSchedules, schedules)
        return schedules.find((schedule) => schedule.id === id)
      },
    )

  const deleteWaterSchedule = (id) =>
    requestWithFallback(
      () => api.delete(`/water/schedule/${id}`),
      () => {
        const schedules = ensureWaterSchedules().filter((schedule) => schedule.id !== id)
        writeStored(STORAGE_KEYS.waterSchedules, schedules)
        return { status: 'mocked', id }
      },
    )

  const getWaterSettings = () =>
    requestWithFallback(
      () => api.get('/water/settings'),
      () => ensureWaterSettings(),
    )

  const saveWaterSettings = (payload) =>
    requestWithFallback(
      () => api.put('/water/settings', payload),
      () => writeStored(STORAGE_KEYS.waterSettings, { ...ensureWaterSettings(), ...payload }),
    )

  return {
    getDeviceStatus,
    getSensorLatest,
    getSensorHistory,
    getSensorStats,
    getSensorThresholds,
    getMeowEvents,
    getMeowStats,
    setMeowControl,
    getConversations,
    getAppSettings,
    saveAppSettings,
    sendIotCommand,
    mockSensor,
    mockMeow,
    getLatestPhoto,
    triggerCapture,
    getPhotos,
    deletePhoto,
    getSensorRecords,
    getWaterRecordsPaged,
    getWaterUsage,
    getWaterRecords,
    controlWaterPump,
    getWaterSchedules,
    createWaterSchedule,
    updateWaterSchedule,
    deleteWaterSchedule,
    getWaterSettings,
    saveWaterSettings,
  }
}
