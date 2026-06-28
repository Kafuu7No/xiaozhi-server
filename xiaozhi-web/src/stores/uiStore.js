import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { MODE_STORAGE_KEY, normalizeMode, VIEW_MODE } from '../router/modeRouting'

function readInitialMode() {
  if (typeof localStorage === 'undefined') return VIEW_MODE
  return normalizeMode(localStorage.getItem(MODE_STORAGE_KEY))
}

export const useUiStore = defineStore('ui', () => {
  const mode = ref(readInitialMode())

  const isViewMode = computed(() => mode.value === VIEW_MODE)
  const isControlMode = computed(() => !isViewMode.value)

  function setMode(nextMode) {
    mode.value = normalizeMode(nextMode)
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(MODE_STORAGE_KEY, mode.value)
    }
  }

  return {
    mode,
    isViewMode,
    isControlMode,
    setMode,
  }
})
