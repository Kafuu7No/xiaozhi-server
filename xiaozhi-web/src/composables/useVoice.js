import { ref } from 'vue'

const TARGET_RATE = 16000

function downsampleTo16k(input, inputRate) {
  const ratio = inputRate / TARGET_RATE
  const outputLength = Math.floor(input.length / ratio)
  const output = new Int16Array(outputLength)
  for (let i = 0; i < outputLength; i += 1) {
    const sample = Math.max(-1, Math.min(1, input[Math.floor(i * ratio)]))
    output[i] = sample < 0 ? sample * 0x8000 : sample * 0x7fff
  }
  return output.buffer
}

export function useVoice() {
  const connected = ref(false)
  const recording = ref(false)
  const status = ref('idle')
  const sttText = ref('')
  const replyText = ref('')
  const errorText = ref('')

  let ws = null
  let audioCtx = null
  let mediaStream = null
  let processor = null
  let source = null
  let pendingAudio = false
  let currentAudioUrl = null
  let responseTimer = null

  function clearResponseTimer() {
    if (responseTimer) {
      clearTimeout(responseTimer)
      responseTimer = null
    }
  }

  function releaseAudioUrl() {
    if (currentAudioUrl) {
      URL.revokeObjectURL(currentAudioUrl)
      currentAudioUrl = null
    }
  }

  function connect() {
    if (ws && ws.readyState <= WebSocket.OPEN) return
    const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
    ws = new WebSocket(`${protocol}://${location.host}/ws/voice`)
    ws.binaryType = 'arraybuffer'
    ws.onopen = () => {
      connected.value = true
      errorText.value = ''
    }
    ws.onclose = () => {
      connected.value = false
      recording.value = false
      status.value = 'idle'
    }
    ws.onerror = () => {
      errorText.value = '语音服务连接失败'
    }
    ws.onmessage = (event) => {
      if (typeof event.data === 'string') {
        const message = JSON.parse(event.data)
        if (message.type === 'stt') sttText.value = message.text
        else if (message.type === 'reply') {
          replyText.value = message.text
          status.value = 'idle'
          clearResponseTimer()
        } else if (message.type === 'tts_audio') {
          pendingAudio = true
        } else if (message.type === 'error') {
          errorText.value = message.message || '语音处理失败'
          status.value = 'idle'
          clearResponseTimer()
        }
      } else if (pendingAudio) {
        pendingAudio = false
        releaseAudioUrl()
        currentAudioUrl = URL.createObjectURL(new Blob([event.data], { type: 'audio/mpeg' }))
        new Audio(currentAudioUrl).play().catch(() => {})
      }
    }
  }

  async function startRecording() {
    if (!ws || ws.readyState !== WebSocket.OPEN || recording.value) return
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true })
      audioCtx = new AudioContext()
      source = audioCtx.createMediaStreamSource(mediaStream)
      processor = audioCtx.createScriptProcessor(4096, 1, 1)
      processor.onaudioprocess = (event) => {
        const pcm = downsampleTo16k(event.inputBuffer.getChannelData(0), audioCtx.sampleRate)
        if (pcm.byteLength && ws.readyState === WebSocket.OPEN) ws.send(pcm)
      }
      source.connect(processor)
      processor.connect(audioCtx.destination)
      sttText.value = ''
      replyText.value = ''
      errorText.value = ''
      ws.send(JSON.stringify({ type: 'start' }))
      recording.value = true
    } catch (error) {
      errorText.value = '无法访问麦克风'
      stopRecording()
    }
  }

  function stopRecording() {
    if (!recording.value) return
    recording.value = false
    status.value = 'thinking'
    if (processor) {
      processor.onaudioprocess = null
      processor.disconnect()
    }
    if (source) source.disconnect()
    if (audioCtx) audioCtx.close()
    if (mediaStream) mediaStream.getTracks().forEach((track) => track.stop())
    processor = null
    source = null
    audioCtx = null
    mediaStream = null
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'stop' }))
      clearResponseTimer()
      responseTimer = setTimeout(() => {
        status.value = 'idle'
        errorText.value = '语音处理超时，请检查后端服务日志'
      }, 50000)
    }
  }

  function disconnect() {
    stopRecording()
    if (ws) {
      ws.onclose = null
      ws.close()
      ws = null
    }
    releaseAudioUrl()
    clearResponseTimer()
    connected.value = false
  }

  return {
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
  }
}
