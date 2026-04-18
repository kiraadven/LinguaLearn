/**
 * useAiTutor.js
 *
 * Manages the WebSocket connection to the AI Tutor backend (/ai-tutor/ws/{learner_id}).
 *
 * Handles:
 *   - Connection lifecycle (connect / disconnect)
 *   - Dispatching incoming tool_call messages to registered callbacks
 *   - Sending student messages (text + binary PCM audio)
 *   - Exposing reactive state for the UI
 *
 * Usage:
 *   const tutor = useAiTutor()
 *   tutor.connect(learnerId, jobId, mode)
 *   tutor.onToolCall('play_sentence', (args) => { ... })
 *   tutor.send({ type: 'text_input', text: '...' })
 *   tutor.disconnect()
 */
import { ref, shallowRef } from 'vue'

const AI_TUTOR_WS_PORT = 8080 // ai_tutor server port

function getWsUrl(learnerId) {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
  // Connect to the AI tutor server (may be on a different port from the main API)
  return `${proto}//${location.hostname}:${AI_TUTOR_WS_PORT}/ai-tutor/ws/${learnerId}`
}

// ── Browser TTS helper ─────────────────────────────────────────────────────────

let _ttsEnabled = true

function _speak(text, lang = 'zh-CN') {
  if (!_ttsEnabled || !text || !window.speechSynthesis) return
  // Cancel any ongoing speech before speaking new text
  window.speechSynthesis.cancel()
  const utterance = new SpeechSynthesisUtterance(text)
  utterance.lang = lang
  utterance.rate = 0.95
  // Prefer a local voice if available
  const voices = window.speechSynthesis.getVoices()
  const preferred = voices.find(v => v.lang === lang && !v.remote)
    || voices.find(v => v.lang.startsWith('zh'))
  if (preferred) utterance.voice = preferred
  window.speechSynthesis.speak(utterance)
}

export function useAiTutor() {
  const ws = shallowRef(null)
  const connected = ref(false)
  const connecting = ref(false)
  const error = ref('')

  // Reactive state from the server
  const teachingState = ref({ phase: 'idle', sentence_index: -1, total: 0 })
  const teacherText = ref('')
  const transcript = ref('')         // ASR transcript (student speech)
  const curriculum = ref(null)
  const conversationHistory = ref([]) // [{role, text, timestamp}]
  const currentNote = ref(null)       // {title, content, note_type} for show_note popup
  const shadowRequest = ref(null)     // {text, sentence_index} for shadow reading UI
  const highlightedWord = ref(null)   // {word, sentence_index}
  const mode = ref('course')
  const ttsEnabled = ref(true)
  const isSpeaking = ref(false)       // TTS playback state

  // Tool call callbacks registry
  const _toolCallbacks = {}

  // ── Connection ─────────────────────────────────────────────────────────────

  function connect(learnerId, jobId = '', sessionMode = 'course') {
    if (ws.value) disconnect()
    mode.value = sessionMode
    connecting.value = true
    error.value = ''

    const socket = new WebSocket(getWsUrl(learnerId))
    ws.value = socket

    socket.onopen = () => {
      connecting.value = false
      connected.value = true

      const startMsg = {
        type: 'start_course',
        job_id: jobId,
        mode: sessionMode,
      }
      socket.send(JSON.stringify(startMsg))
    }

    socket.onmessage = (event) => {
      if (event.data instanceof ArrayBuffer || event.data instanceof Blob) {
        // Binary PCM audio (TTS) — handled by audio pipeline
        _emitToolCall('__audio__', event.data)
        return
      }

      let msg
      try {
        msg = JSON.parse(event.data)
      } catch {
        return
      }

      _handleMessage(msg)
    }

    socket.onerror = () => {
      error.value = '连接AI老师失败，请检查服务器是否启动'
      connecting.value = false
    }

    socket.onclose = () => {
      connected.value = false
      connecting.value = false
    }
  }

  function disconnect() {
    if (ws.value) {
      ws.value.close()
      ws.value = null
    }
    connected.value = false
  }

  // ── Message dispatch ────────────────────────────────────────────────────────

  function _handleMessage(msg) {
    const type = msg.type

    if (type === 'ready') {
      // Server confirmed session start
      return
    }

    if (type === 'teaching_state') {
      teachingState.value = {
        phase: msg.phase || 'idle',
        sentence_index: msg.sentence_index ?? -1,
        total: msg.total ?? teachingState.value.total,
      }
      return
    }

    if (type === 'teacher_text') {
      const text = msg.text || ''
      teacherText.value = text
      conversationHistory.value.push({
        role: 'teacher',
        text,
        timestamp: Date.now(),
      })
      // Speak Sarah's text via browser TTS
      if (_ttsEnabled && text) {
        _speak(text)
      }
      return
    }

    if (type === 'transcript') {
      transcript.value = msg.text || ''
      if (msg.is_final && msg.text) {
        conversationHistory.value.push({
          role: 'student',
          text: msg.text,
          timestamp: Date.now(),
        })
      }
      return
    }

    if (type === 'curriculum') {
      curriculum.value = msg.plan
      return
    }

    if (type === 'tool_call') {
      _dispatchToolCall(msg.tool, msg.args || {})
      return
    }

    if (type === 'error') {
      error.value = msg.message || '未知错误'
      return
    }
  }

  function _dispatchToolCall(toolName, args) {
    // Built-in tool side effects
    if (toolName === 'show_note') {
      currentNote.value = args
    } else if (toolName === 'request_shadow') {
      shadowRequest.value = args
    } else if (toolName === 'highlight_word') {
      highlightedWord.value = args
    }

    _emitToolCall(toolName, args)
  }

  function _emitToolCall(toolName, args) {
    const cb = _toolCallbacks[toolName]
    if (cb) cb(args)
  }

  // ── Public API ──────────────────────────────────────────────────────────────

  function onToolCall(toolName, callback) {
    _toolCallbacks[toolName] = callback
  }

  function send(msgObj) {
    if (ws.value && ws.value.readyState === WebSocket.OPEN) {
      ws.value.send(JSON.stringify(msgObj))
    }
  }

  function sendAudio(pcmBuffer) {
    if (ws.value && ws.value.readyState === WebSocket.OPEN) {
      ws.value.send(pcmBuffer)
    }
  }

  function sendText(text) {
    send({ type: 'text_input', text })
    // Optimistically add to history
    conversationHistory.value.push({
      role: 'student',
      text,
      timestamp: Date.now(),
    })
  }

  function sendVideoEvent(eventType, position = 0) {
    send({ type: 'video_event', event: eventType, position })
  }

  function sendAttentionSignal(signal, value = 1.0) {
    send({ type: 'attention', signal, value })
  }

  function endSession() {
    send({ type: 'session_end' })
    setTimeout(() => disconnect(), 1000)
  }

  function dismissNote() {
    currentNote.value = null
  }

  function dismissShadow() {
    shadowRequest.value = null
  }

  function toggleTts() {
    _ttsEnabled = !_ttsEnabled
    ttsEnabled.value = _ttsEnabled
    if (!_ttsEnabled) window.speechSynthesis?.cancel()
  }

  function stopSpeaking() {
    window.speechSynthesis?.cancel()
  }

  return {
    // State
    connected,
    connecting,
    error,
    teachingState,
    teacherText,
    transcript,
    curriculum,
    conversationHistory,
    currentNote,
    shadowRequest,
    highlightedWord,
    mode,
    ttsEnabled,
    isSpeaking,

    // Actions
    connect,
    disconnect,
    onToolCall,
    send,
    sendAudio,
    sendText,
    sendVideoEvent,
    sendAttentionSignal,
    endSession,
    dismissNote,
    dismissShadow,
    toggleTts,
    stopSpeaking,
  }
}
