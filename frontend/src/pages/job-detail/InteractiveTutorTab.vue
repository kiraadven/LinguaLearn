<template>
  <div class="it-container">

    <!-- Setup panel (before session starts) -->
    <div v-if="!sessionActive" class="it-setup">
      <div class="it-setup-card">
        <div class="it-logo">🎓</div>
        <h2>互动 AI 老师</h2>
        <p class="it-setup-desc">
          AI 老师会为你逐句讲解视频内容，控制视频播放，并与你实时互动。
        </p>

        <div class="it-form">
          <label>学习者名称</label>
          <input v-model="learnerName" placeholder="输入你的名字" class="it-input" />

          <label>英语水平</label>
          <select v-model="learnerLevel" class="it-select">
            <option v-for="l in levels" :key="l" :value="l">{{ l }}</option>
          </select>

          <label>学习模式</label>
          <div class="it-mode-row">
            <button
              v-for="m in modes"
              :key="m.id"
              :class="['it-mode-btn', { active: selectedMode === m.id }]"
              @click="selectedMode = m.id"
            >
              {{ m.icon }} {{ m.label }}
            </button>
          </div>
        </div>

        <button class="it-start-btn" :disabled="!learnerName.trim()" @click="startSession">
          开始上课
        </button>
      </div>
    </div>

    <!-- Active session -->
    <div v-else class="it-session">

      <!-- Left sidebar: progress + memory -->
      <div class="it-sidebar">
        <!-- Teaching progress -->
        <div class="it-progress-card" v-if="selectedMode === 'course'">
          <div class="it-progress-title">
            <span>📖</span>
            <span>学习进度</span>
            <span class="it-phase-badge" :class="phaseClass">{{ phaseLabel }}</span>
          </div>
          <div v-if="teachingState.total > 0" class="it-sentence-dots">
            <div
              v-for="i in teachingState.total"
              :key="i"
              class="it-sdot"
              :class="{
                done: i - 1 < teachingState.sentence_index,
                active: i - 1 === teachingState.sentence_index,
              }"
              :title="`句子 ${i}`"
            ></div>
          </div>
          <div class="it-progress-text">
            <span v-if="teachingState.sentence_index >= 0">
              第 {{ teachingState.sentence_index + 1 }}/{{ teachingState.total }} 句
            </span>
            <span v-else>等待开始</span>
          </div>
        </div>

        <!-- Curriculum -->
        <details v-if="curriculum" class="it-curriculum">
          <summary>课程大纲</summary>
          <pre class="it-curriculum-text">{{ curriculum }}</pre>
        </details>

        <!-- Memory panel -->
        <LearnerMemoryPanel
          :learner-id="learnerId"
          :job-id="jobId"
        />

        <!-- End session -->
        <button class="it-end-btn" @click="endSession">结束课程</button>
      </div>

      <!-- Center: conversation -->
      <div class="it-chat-col">
        <!-- Conversation messages -->
        <div class="it-chat-list" ref="chatListEl">
          <div
            v-for="(msg, i) in conversationHistory"
            :key="i"
            :class="['it-msg', msg.role]"
          >
            <div class="it-msg-bubble">
              <span class="it-msg-role">{{ msg.role === 'teacher' ? '👩‍🏫 Sarah' : '🧑‍💻 你' }}</span>
              <p class="it-msg-text">{{ msg.text }}</p>
            </div>
          </div>

          <!-- Typing indicator -->
          <div v-if="isTeacherThinking" class="it-msg teacher">
            <div class="it-msg-bubble it-thinking">
              <span class="it-dot"></span><span class="it-dot"></span><span class="it-dot"></span>
            </div>
          </div>
        </div>

        <!-- Input area -->
        <div class="it-input-row">
          <input
            v-model="textInput"
            class="it-text-input"
            placeholder="输入回答，或直接说话..."
            @keydown.enter="sendText"
          />
          <button class="it-send-btn" @click="sendText" :disabled="!textInput.trim()">发送</button>
        </div>

        <!-- Connection status -->
        <div class="it-status-bar">
          <span :class="['it-status-dot', { online: tutor.connected.value, offline: !tutor.connected.value }]"></span>
          <span>{{ statusLabel }}</span>
          <span v-if="tutor.error.value" class="it-error-text">{{ tutor.error.value }}</span>
        </div>
      </div>

      <!-- Right: current sentence card -->
      <div class="it-right-col">
        <!-- Current sentence info -->
        <div v-if="currentSentence" class="it-sentence-card">
          <div class="it-sc-label">当前句子</div>
          <p class="it-sc-text">{{ currentSentence.text }}</p>
          <p class="it-sc-trans">{{ currentSentence.translation }}</p>

          <!-- Key vocab -->
          <div v-if="currentSentence.vocab?.length" class="it-vocab-list">
            <div
              v-for="v in currentSentence.vocab"
              :key="v.word"
              :class="['it-vocab-item', { highlighted: highlightedWord?.word === v.word }]"
            >
              <span class="it-vocab-word">{{ v.word }}</span>
              <span class="it-vocab-ph">{{ v.phonetic }}</span>
              <span class="it-vocab-cn">{{ v.translation }}</span>
            </div>
          </div>
        </div>

        <!-- Note popup -->
        <Transition name="note">
          <div v-if="currentNote" class="it-note-card" :class="['note-' + (currentNote.note_type || 'grammar')]">
            <div class="it-note-header">
              <span class="it-note-type-icon">{{ noteTypeIcon(currentNote.note_type) }}</span>
              <span class="it-note-title">{{ currentNote.title }}</span>
              <button class="it-note-close" @click="tutor.dismissNote()">✕</button>
            </div>
            <p class="it-note-content">{{ currentNote.content }}</p>
          </div>
        </Transition>

        <!-- Shadow reading prompt -->
        <Transition name="note">
          <div v-if="shadowRequest" class="it-shadow-card">
            <div class="it-shadow-header">
              <span>🎤 跟读练习</span>
              <button @click="tutor.dismissShadow()">✕</button>
            </div>
            <p class="it-shadow-text">{{ shadowRequest.text }}</p>
            <p class="it-shadow-hint">请大声跟读上面这句话，老师会在你说完后继续。</p>
          </div>
        </Transition>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onUnmounted } from 'vue'
import { useAiTutor } from '../../composables/useAiTutor.js'
import LearnerMemoryPanel from './LearnerMemoryPanel.vue'

const props = defineProps({
  videoEl: { type: Object, default: null },   // ref to HTMLVideoElement
  jobId: { type: String, required: true },
  segments: { type: Array, default: () => [] }, // [{start, end, text}, ...]
  jobContent: { type: Object, default: null },  // parsed lesson content from API
})

const emit = defineEmits(['video-control'])

// ── Session state ─────────────────────────────────────────────────────────────

const sessionActive = ref(false)
const learnerName = ref(localStorage.getItem('at_learner_name') || '')
const learnerLevel = ref(localStorage.getItem('at_learner_level') || 'B1')
const selectedMode = ref('course')
const learnerId = ref('')

const levels = ['A1', 'A2', 'B1', 'B2', 'C1']
const modes = [
  { id: 'course', icon: '📖', label: '课程讲解' },
  { id: 'global', icon: '💬', label: '复习/闲聊' },
]

// ── AI Tutor composable ───────────────────────────────────────────────────────

const tutor = useAiTutor()
const {
  connected, teachingState, teacherText, transcript,
  curriculum, conversationHistory, currentNote, shadowRequest, highlightedWord,
} = tutor

const isTeacherThinking = ref(false)
const chatListEl = ref(null)
const textInput = ref('')

// ── Lesson content ─────────────────────────────────────────────────────────────

const lessonSentences = ref([])  // loaded from backend

const currentSentence = computed(() => {
  const idx = teachingState.value.sentence_index
  if (idx < 0 || !lessonSentences.value.length) return null
  return lessonSentences.value[idx] || null
})

// ── Video control (segment timing) ───────────────────────────────────────────

let segmentEndTimer = null

function playVideoFull() {
  const video = props.videoEl
  if (!video) return
  video.currentTime = 0
  video.play()

  // Listen for video end → notify backend
  video.onended = () => {
    tutor.sendVideoEvent('ended', video.currentTime)
  }
}

function playSentenceClip(sentenceIndex, loopCount = 1) {
  const video = props.videoEl
  if (!video) return

  // Find timing from props.segments or lessonSentences
  let start = 0, end = 0
  const seg = props.segments[sentenceIndex] || lessonSentences.value[sentenceIndex]
  if (seg) {
    start = seg.start ?? seg.video_start ?? 0
    end = seg.end ?? 0
  }

  if (segmentEndTimer) clearTimeout(segmentEndTimer)

  video.currentTime = start
  video.play()

  const duration = (end - start) * 1000
  if (duration > 0) {
    segmentEndTimer = setTimeout(() => {
      video.pause()
      tutor.sendVideoEvent('segment_ended', video.currentTime)
    }, duration * (loopCount || 1))
  }
}

function pauseVideo() {
  props.videoEl?.pause()
}

// ── Register tool call handlers ────────────────────────────────────────────────

tutor.onToolCall('play_full_video', () => {
  playVideoFull()
})

tutor.onToolCall('play_sentence', (args) => {
  playSentenceClip(args.sentence_index, args.loop_count)
})

tutor.onToolCall('pause_video', () => {
  pauseVideo()
})

tutor.onToolCall('advance_sentence', () => {
  // Server already handles state; UI updates via teaching_state message
})

// ── Attention monitoring ────────────────────────────────────────────────────────

let mouseIdleTimer = null
let lastMouseMove = Date.now()

function onMouseMove() {
  lastMouseMove = Date.now()
}

function onVisibilityChange() {
  if (document.hidden && sessionActive.value) {
    tutor.sendAttentionSignal('tab_switch', 1.0)
  }
}

function startAttentionMonitor() {
  document.addEventListener('mousemove', onMouseMove)
  document.addEventListener('visibilitychange', onVisibilityChange)

  mouseIdleTimer = setInterval(() => {
    const idleMs = Date.now() - lastMouseMove
    if (idleMs > 30000 && sessionActive.value) {
      tutor.sendAttentionSignal('mouse_idle', idleMs / 1000)
    }
  }, 15000)
}

function stopAttentionMonitor() {
  document.removeEventListener('mousemove', onMouseMove)
  document.removeEventListener('visibilitychange', onVisibilityChange)
  if (mouseIdleTimer) clearInterval(mouseIdleTimer)
}

// ── Session control ────────────────────────────────────────────────────────────

async function startSession() {
  const name = learnerName.value.trim()
  if (!name) return

  // Persist preferences
  localStorage.setItem('at_learner_name', name)
  localStorage.setItem('at_learner_level', learnerLevel.value)

  // Use name as learner ID (simple approach; could use a UUID)
  learnerId.value = name.toLowerCase().replace(/\s+/g, '_')

  // First create/update the learner profile on the server
  try {
    await fetch(
      `http://${location.hostname}:8080/ai-tutor/learner`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          learner_id: learnerId.value,
          name,
          level: learnerLevel.value,
        }),
      }
    )
  } catch (e) {
    console.warn('Could not create learner profile:', e)
  }

  // Load lesson content for the right-side panel
  if (props.jobId) {
    await loadLessonContent()
  }

  // Connect WebSocket
  tutor.connect(learnerId.value, props.jobId, selectedMode.value)
  sessionActive.value = true
  startAttentionMonitor()
}

function endSession() {
  tutor.endSession()
  sessionActive.value = false
  stopAttentionMonitor()
  if (segmentEndTimer) clearTimeout(segmentEndTimer)
}

async function loadLessonContent() {
  if (props.jobContent) {
    lessonSentences.value = props.jobContent.sentences || []
    return
  }
  try {
    const resp = await fetch(
      `http://${location.hostname}:8080/ai-tutor/jobs/${encodeURIComponent(props.jobId)}/content`
    )
    if (resp.ok) {
      const data = await resp.json()
      lessonSentences.value = data.sentences || []
    }
  } catch (e) {
    console.warn('Could not load lesson content:', e)
  }
}

function sendText() {
  const text = textInput.value.trim()
  if (!text) return
  tutor.sendText(text)
  textInput.value = ''
}

// ── Auto-scroll chat ──────────────────────────────────────────────────────────

watch(conversationHistory, () => {
  nextTick(() => {
    if (chatListEl.value) {
      chatListEl.value.scrollTop = chatListEl.value.scrollHeight
    }
  })
}, { deep: true })

// ── Computed display helpers ──────────────────────────────────────────────────

const statusLabel = computed(() => {
  if (tutor.connecting.value) return '连接中...'
  if (tutor.connected.value) return '已连接'
  return '未连接'
})

const phaseClass = computed(() => {
  const ph = teachingState.value.phase
  if (ph === 'intro') return 'phase-intro'
  if (ph === 'teaching') return 'phase-teaching'
  if (ph === 'review') return 'phase-review'
  return ''
})

const phaseLabel = computed(() => {
  const ph = teachingState.value.phase
  const map = { idle: '待机', intro: '整体预览', teaching: '逐句讲解', review: '复习总结', end: '已结束' }
  return map[ph] || ph
})

function noteTypeIcon(type) {
  return { grammar: '📝', culture: '🌏', vocabulary: '📖', pronunciation: '🔊' }[type] || '💡'
}

// ── Cleanup ────────────────────────────────────────────────────────────────────

onUnmounted(() => {
  tutor.disconnect()
  stopAttentionMonitor()
  if (segmentEndTimer) clearTimeout(segmentEndTimer)
})
</script>

<style scoped>
/* ── Container ── */
.it-container {
  height: 100%;
  min-height: 600px;
  display: flex;
  flex-direction: column;
}

/* ── Setup panel ── */
.it-setup {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px 24px;
}
.it-setup-card {
  max-width: 420px;
  width: 100%;
  background: var(--surface2, #1e1e2e);
  border: 1px solid var(--border, #2a2a3e);
  border-radius: 16px;
  padding: 32px;
  text-align: center;
}
.it-logo { font-size: 48px; margin-bottom: 12px; }
.it-setup-card h2 { color: var(--text1, #eee); margin: 0 0 8px; }
.it-setup-desc { color: var(--text2, #bbb); font-size: 14px; line-height: 1.6; margin-bottom: 24px; }

.it-form { text-align: left; display: flex; flex-direction: column; gap: 10px; margin-bottom: 24px; }
.it-form label { font-size: 12px; color: var(--text3, #888); font-weight: 600; text-transform: uppercase; }
.it-input, .it-select {
  width: 100%;
  padding: 8px 12px;
  background: var(--surface3, #252538);
  border: 1px solid var(--border, #2a2a3e);
  border-radius: 8px;
  color: var(--text1, #eee);
  font-size: 14px;
  box-sizing: border-box;
}

.it-mode-row { display: flex; gap: 8px; }
.it-mode-btn {
  flex: 1;
  padding: 8px;
  border-radius: 8px;
  border: 1px solid var(--border, #2a2a3e);
  background: var(--surface3, #252538);
  color: var(--text2, #bbb);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
}
.it-mode-btn.active {
  border-color: var(--accent, #a78bfa);
  background: rgba(167,139,250,0.12);
  color: var(--accent, #a78bfa);
}

.it-start-btn {
  width: 100%;
  padding: 12px;
  border-radius: 10px;
  border: none;
  background: linear-gradient(135deg, var(--accent, #a78bfa), var(--accent2, #818cf8));
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s;
}
.it-start-btn:disabled { opacity: 0.4; cursor: not-allowed; }

/* ── Active session layout ── */
.it-session {
  display: grid;
  grid-template-columns: 220px 1fr 260px;
  gap: 16px;
  padding: 16px;
  height: 100%;
  min-height: 600px;
}

/* ── Sidebar ── */
.it-sidebar {
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
}

.it-progress-card {
  background: var(--surface2, #1e1e2e);
  border: 1px solid var(--border, #2a2a3e);
  border-radius: 10px;
  padding: 12px;
}
.it-progress-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text1, #eee);
  margin-bottom: 8px;
}
.it-phase-badge {
  margin-left: auto;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  background: var(--surface4, #333);
  color: var(--text2, #bbb);
}
.phase-intro { background: rgba(59,130,246,0.2); color: #93c5fd; }
.phase-teaching { background: rgba(167,139,250,0.2); color: var(--accent, #a78bfa); }
.phase-review { background: rgba(16,185,129,0.2); color: #6ee7b7; }

.it-sentence-dots {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 6px;
}
.it-sdot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--surface4, #333);
  border: 1px solid var(--border, #2a2a3e);
  transition: all 0.2s;
}
.it-sdot.done { background: #10b981; border-color: #10b981; }
.it-sdot.active { background: var(--accent, #a78bfa); border-color: var(--accent, #a78bfa); transform: scale(1.3); }

.it-progress-text { font-size: 12px; color: var(--text2, #bbb); }

.it-curriculum {
  background: var(--surface2, #1e1e2e);
  border: 1px solid var(--border, #2a2a3e);
  border-radius: 10px;
  padding: 8px 12px;
  font-size: 12px;
  color: var(--text2, #bbb);
}
.it-curriculum summary { cursor: pointer; color: var(--accent, #a78bfa); }
.it-curriculum-text { font-size: 11px; white-space: pre-wrap; margin: 8px 0 0; line-height: 1.6; }

.it-end-btn {
  padding: 8px 14px;
  border-radius: 8px;
  border: 1px solid #ef4444;
  background: rgba(239,68,68,0.1);
  color: #f87171;
  font-size: 13px;
  cursor: pointer;
  margin-top: auto;
}

/* ── Chat column ── */
.it-chat-col {
  display: flex;
  flex-direction: column;
  background: var(--surface2, #1e1e2e);
  border: 1px solid var(--border, #2a2a3e);
  border-radius: 12px;
  overflow: hidden;
}
.it-chat-list {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.it-msg { display: flex; }
.it-msg.teacher { justify-content: flex-start; }
.it-msg.student { justify-content: flex-end; }

.it-msg-bubble {
  max-width: 80%;
  padding: 10px 14px;
  border-radius: 14px;
  font-size: 14px;
  line-height: 1.6;
}
.it-msg.teacher .it-msg-bubble {
  background: var(--surface3, #252538);
  border-bottom-left-radius: 4px;
}
.it-msg.student .it-msg-bubble {
  background: rgba(167,139,250,0.15);
  border-bottom-right-radius: 4px;
}
.it-msg-role { display: block; font-size: 11px; color: var(--text3, #888); margin-bottom: 3px; }
.it-msg-text { margin: 0; color: var(--text1, #eee); }

.it-thinking { display: flex; align-items: center; gap: 4px; padding: 12px 16px; }
.it-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--text3, #888);
  animation: blink 1.4s infinite;
}
.it-dot:nth-child(2) { animation-delay: 0.2s; }
.it-dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes blink { 0%, 80%, 100% { opacity: 0.2 } 40% { opacity: 1 } }

.it-input-row {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid var(--border, #2a2a3e);
}
.it-text-input {
  flex: 1;
  padding: 8px 12px;
  background: var(--surface3, #252538);
  border: 1px solid var(--border, #2a2a3e);
  border-radius: 8px;
  color: var(--text1, #eee);
  font-size: 14px;
}
.it-send-btn {
  padding: 8px 16px;
  border-radius: 8px;
  border: none;
  background: var(--accent, #a78bfa);
  color: #fff;
  font-size: 13px;
  cursor: pointer;
}
.it-send-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.it-status-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 16px;
  font-size: 11px;
  color: var(--text3, #888);
  border-top: 1px solid var(--border, #2a2a3e);
}
.it-status-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--text4, #444); }
.it-status-dot.online { background: #10b981; }
.it-status-dot.offline { background: #ef4444; }
.it-error-text { color: #f87171; margin-left: 8px; }

/* ── Right column ── */
.it-right-col {
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
}

.it-sentence-card {
  background: var(--surface2, #1e1e2e);
  border: 1px solid var(--border, #2a2a3e);
  border-radius: 12px;
  padding: 14px;
}
.it-sc-label { font-size: 11px; color: var(--accent, #a78bfa); font-weight: 600; margin-bottom: 6px; }
.it-sc-text { font-size: 14px; color: var(--text1, #eee); line-height: 1.6; margin: 0 0 6px; }
.it-sc-trans { font-size: 12px; color: var(--text3, #888); margin: 0 0 10px; }

.it-vocab-list { display: flex; flex-direction: column; gap: 6px; }
.it-vocab-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 8px;
  border-radius: 6px;
  background: var(--surface3, #252538);
  font-size: 12px;
  transition: background 0.2s;
}
.it-vocab-item.highlighted { background: rgba(167,139,250,0.2); }
.it-vocab-word { font-weight: 600; color: var(--text1, #eee); min-width: 60px; }
.it-vocab-ph { color: var(--text3, #888); flex: 1; }
.it-vocab-cn { color: var(--text2, #bbb); text-align: right; }

/* ── Note card ── */
.it-note-card {
  border-radius: 12px;
  padding: 14px;
  border: 1px solid var(--border, #2a2a3e);
}
.note-grammar { background: rgba(59,130,246,0.1); border-color: rgba(59,130,246,0.3); }
.note-culture { background: rgba(16,185,129,0.1); border-color: rgba(16,185,129,0.3); }
.note-vocabulary { background: rgba(167,139,250,0.1); border-color: rgba(167,139,250,0.3); }
.note-pronunciation { background: rgba(249,115,22,0.1); border-color: rgba(249,115,22,0.3); }

.it-note-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}
.it-note-type-icon { font-size: 16px; }
.it-note-title { flex: 1; font-size: 13px; font-weight: 600; color: var(--text1, #eee); }
.it-note-close { border: none; background: none; color: var(--text3, #888); cursor: pointer; font-size: 14px; }
.it-note-content { font-size: 13px; color: var(--text1, #eee); line-height: 1.6; margin: 0; }

/* ── Shadow reading card ── */
.it-shadow-card {
  background: rgba(249,115,22,0.1);
  border: 1px solid rgba(249,115,22,0.3);
  border-radius: 12px;
  padding: 14px;
}
.it-shadow-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
  font-weight: 600;
  color: #fb923c;
  margin-bottom: 8px;
}
.it-shadow-header button { border: none; background: none; color: var(--text3, #888); cursor: pointer; }
.it-shadow-text {
  font-size: 15px;
  color: var(--text1, #eee);
  font-style: italic;
  margin: 0 0 8px;
  line-height: 1.6;
}
.it-shadow-hint { font-size: 12px; color: var(--text3, #888); margin: 0; }

/* ── Transitions ── */
.note-enter-active, .note-leave-active { transition: all 0.25s; }
.note-enter-from, .note-leave-to { opacity: 0; transform: translateY(-8px); }
</style>
