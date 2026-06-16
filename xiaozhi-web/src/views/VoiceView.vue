<template>
  <div class="mx-auto flex max-w-3xl flex-col gap-5 p-4 pb-24 md:p-6">
    <header class="flex flex-col gap-1">
      <div class="flex items-center justify-between gap-3">
        <h1 class="text-xl font-semibold text-slate-900">语音助手</h1>
        <span
          class="rounded-full px-3 py-1 text-xs font-medium"
          :class="connected ? 'bg-emerald-50 text-emerald-700' : 'bg-rose-50 text-rose-700'"
        >
          {{ connected ? '已连接' : '未连接' }}
        </span>
      </div>
      <p class="text-sm text-slate-500">按住麦克风说话，松开后自动识别、回答并朗读。</p>
    </header>

    <section class="app-card">
      <div class="app-card-body flex flex-col items-center gap-4">
        <button
          class="btn btn-circle btn-lg text-2xl"
          :class="recording ? 'btn-error' : 'btn-primary'"
          :disabled="!connected || status === 'thinking'"
          aria-label="按住说话"
          @mousedown="startRecording"
          @mouseup="stopRecording"
          @mouseleave="stopRecording"
          @touchstart.prevent="startRecording"
          @touchend.prevent="stopRecording"
        >
          🎤
        </button>
        <span class="text-sm text-slate-500">{{ promptText }}</span>
        <p v-if="errorText" class="text-sm text-rose-600">{{ errorText }}</p>
      </div>
    </section>

    <section v-if="sttText || replyText" class="grid gap-3">
      <div v-if="sttText" class="rounded-lg border border-sky-100 bg-sky-50 p-3 text-sm text-sky-900">
        <span class="font-semibold">你说：</span>{{ sttText }}
      </div>
      <div v-if="replyText" class="rounded-lg border border-slate-100 bg-white p-3 text-sm text-slate-800">
        <span class="font-semibold">助手：</span>{{ replyText }}
      </div>
    </section>

    <section class="app-card">
      <div class="app-card-body">
        <div class="mb-3 flex items-center justify-between">
          <h2 class="text-base font-semibold text-slate-800">历史对话</h2>
          <button class="btn btn-ghost btn-sm" type="button" @click="loadHistory">刷新</button>
        </div>
        <div class="max-h-80 space-y-2 overflow-y-auto">
          <p v-if="!history.length" class="text-sm text-slate-400">暂无对话记录</p>
          <div
            v-for="(item, index) in history"
            :key="`${item.recorded_at}-${index}`"
            class="rounded-lg bg-slate-50 p-3 text-sm"
            :class="item.role === 'user' ? 'text-sky-800' : 'text-slate-700'"
          >
            <span class="font-semibold">{{ item.role === 'user' ? '你' : '助手' }}：</span>
            {{ item.content }}
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import axios from 'axios'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useVoice } from '../composables/useVoice'

const {
  connected,
  recording,
  status,
  sttText,
  replyText,
  errorText,
  connect,
  disconnect,
  startRecording,
  stopRecording,
} = useVoice()

const history = ref([])

const promptText = computed(() => {
  if (recording.value) return '正在录音，松开结束'
  if (status.value === 'thinking') return '识别和思考中'
  return '按住说话'
})

async function loadHistory() {
  try {
    const { data } = await axios.get('/api/conversations', { params: { limit: 50 } })
    history.value = data
  } catch (error) {
    console.warn('加载对话记录失败', error)
  }
}

watch(replyText, (value) => {
  if (value) loadHistory()
})

onMounted(() => {
  connect()
  loadHistory()
})

onBeforeUnmount(disconnect)
</script>
