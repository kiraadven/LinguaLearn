<template>
  <div class="lesson-tab">

    <!-- VIP 门槛 -->
    <div v-if="!isMember" class="lt-gate">
      <div class="lt-gate-icon">🎙️</div>
      <h3>{{ tr('detail_vip_only', 'VIP 专属功能') }}</h3>
      <p>{{ tr('tutor_vip_desc', 'AI 互动讲课是会员专属功能') }}</p>
      <button class="btn-primary" @click="openMembership?.()">
        {{ tr('nav_upgrade_membership', '升级会员') }}
      </button>
    </div>

    <!-- 生成中 -->
    <div v-else-if="phase === 'generating'" class="lt-gen-panel">
      <div class="lt-gen-inner">
        <!-- 步骤指示器 -->
        <div class="lt-steps">
          <div
            v-for="step in GEN_STEPS"
            :key="step.id"
            class="lt-step"
            :class="{
              active: currentGenStep === step.id,
              done: isStepDone(step.id),
            }"
          >
            <div class="lt-step-dot">
              <span v-if="isStepDone(step.id)">✓</span>
              <span v-else-if="currentGenStep === step.id" class="lt-step-spin"></span>
              <span v-else>{{ step.num }}</span>
            </div>
            <span class="lt-step-label">{{ step.label }}</span>
          </div>
        </div>

        <!-- 进度条 -->
        <div class="lt-progress-wrap">
          <div class="lt-progress-bar">
            <div class="lt-progress-fill" :style="{ width: genPercent + '%' }"></div>
          </div>
          <span class="lt-progress-pct">{{ genPercent }}%</span>
        </div>

        <!-- 状态文字 -->
        <p class="lt-gen-msg">{{ genMessage || tr('tutor_gen_in_progress', '正在生成课程脚本...') }}</p>

        <button class="btn-ghost lt-cancel-btn" @click="cancelGenerate">
          {{ tr('cancel', '取消') }}
        </button>
      </div>
    </div>

    <!-- 错误状态 -->
    <div v-else-if="phase === 'error'" class="lt-center-panel">
      <div class="lt-center-inner">
        <div style="font-size:36px;margin-bottom:8px">⚠️</div>
        <h3 style="color:#b91c1c">{{ tr('podcast_gen_error', '生成失败，请重试') }}</h3>
        <pre v-if="errorDetail" class="lt-error-detail">{{ errorDetail }}</pre>
        <button class="btn-primary" @click="startLesson">
          {{ tr('podcast_generate_btn', '重新生成') }}
        </button>
      </div>
    </div>

    <!-- 课程播放器 -->
    <section v-else-if="phase === 'lesson'" class="lt-lesson-layout">

      <!-- 左侧：视频 + 控制器 -->
      <div class="lt-left">
        <div class="lt-video-wrap">
          <video
            ref="videoEl"
            class="lt-video"
            :src="videoSrc"
            preload="auto"
          ></video>
        </div>

        <!-- 当前内容提示条 -->
        <div class="lt-now-playing" :class="currentItem?.type">
          <span class="lt-np-icon">{{ nowPlayingIcon }}</span>
          <span class="lt-np-text">{{ nowPlayingText }}</span>
        </div>

        <!-- 进度条 -->
        <div class="lt-lesson-progress">
          <div class="lt-lp-bar">
            <div class="lt-lp-fill" :style="{ width: progressPct + '%' }"></div>
          </div>
          <span class="lt-lp-label">{{ currentStep + 1 }} / {{ script.length }}</span>
        </div>

        <!-- 问题答案（question 项时显示） -->
        <div v-if="currentItem?.type === 'question' && showAnswerHint" class="lt-answer-hint">
          <span class="lt-hint-label">💡 提示</span>
          <p>{{ currentItem.answer_hint }}</p>
        </div>

        <!-- 控制按钮 -->
        <div class="lt-controls">
          <button class="lt-ctrl-btn" :disabled="isPlaying" @click="prevStep">
            ⏮ {{ tr('tutor_prev', '上一步') }}
          </button>
          <button class="lt-ctrl-btn primary" @click="togglePlay">
            {{ isPlaying ? '⏸ ' + tr('tutor_pause', '暂停') : '▶ ' + tr('tutor_play', '继续') }}
          </button>
          <button class="lt-ctrl-btn" :disabled="isPlaying" @click="nextStep">
            {{ tr('tutor_next', '下一步') }} ⏭
          </button>
        </div>

        <!-- 下载讲课音频 -->
        <div class="lt-podcast-row">
          <button class="btn-ghost lt-dl-btn" @click="downloadPodcast" :disabled="podcastLoading">
            <span v-if="podcastLoading" class="lt-spinner small"></span>
            🎧 {{ tr('tutor_download_podcast', '下载讲课音频') }}
          </button>
        </div>
      </div>

      <!-- 右侧：脚本面板 -->
      <div class="lt-right">
        <div class="lt-script-header">
          <h3>{{ tr('tutor_script', '课程脚本') }}</h3>
          <span class="lt-script-job">{{ job?.name || job?.video_filename }}</span>
        </div>
        <div class="lt-script-list" ref="scriptListEl">
          <div
            v-for="(item, idx) in script"
            :key="idx"
            class="lt-script-item"
            :class="[item.type, { active: idx === currentStep }]"
            @click="jumpToStep(idx)"
          >
            <span class="lt-item-icon">{{ scriptItemIcon(item) }}</span>
            <div class="lt-item-body">
              <p class="lt-item-text">{{ scriptItemText(item) }}</p>
              <span v-if="item.type === 'play'" class="lt-item-sub">
                {{ getSentenceText(item.sentence_id) }}
              </span>
            </div>
          </div>
        </div>
      </div>

    </section>

    <!-- 空闲状态 -->
    <div v-else class="lt-center-panel">
      <div class="lt-center-inner">
        <div style="font-size:44px;margin-bottom:10px">🎙️</div>
        <h3>{{ tr('studio_tab_ai_lesson', 'AI 讲课') }}</h3>
        <p class="lt-hint">{{ tr('tutor_desc', '由 AI 讲师逐句精讲，配合视频互动学习') }}</p>
        <button class="btn-primary lt-start-btn" @click="startLesson">
          {{ tr('podcast_generate_btn', '生成讲课') }}
        </button>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, inject, nextTick } from 'vue'
import { apiFetch } from '../../composables/useApi.js'
import { useAuth } from '../../composables/useAuth.js'
import { useI18n } from '../../i18n.js'

const props = defineProps({
  jobId:    { type: String, required: true },
  job:      { type: Object, required: true },
  segments: { type: Array, default: () => [] },
})

const { t } = useI18n()
const { user } = useAuth()
const openMembership = inject('openMembership', null)

const isMember = computed(() => user.value?.membership?.tier === 'member')

function tr(key, fallback = '') {
  return t.value?.[key] ?? fallback
}

// ── 生成步骤定义 ──────────────────────────────────────────────────────────────
const GEN_STEPS = [
  { id: 'analyze',  num: '1', label: '分析内容' },
  { id: 'plan',     num: '2', label: '规划课程' },
  { id: 'write',    num: '3', label: '生成脚本' },
  { id: 'tts',      num: '4', label: '合成语音' },
]

// phase → step id
const PHASE_STEP_MAP = {
  queued:          'analyze',
  load_input:      'analyze',
  analyze_content: 'analyze',
  plan_lesson:     'plan',
  plan_podcast:    'plan',
  write_lesson:    'write',
  write_podcast:   'write',
  tts_lesson:      'tts',
  tts_podcast:     'tts',
  done:            'tts',
}

const STEP_ORDER = ['analyze', 'plan', 'write', 'tts']

// ── State ─────────────────────────────────────────────────────────────────────
const phase          = ref('idle')   // 'idle' | 'generating' | 'lesson' | 'error'
const genMessage     = ref('')
const genPercent     = ref(0)
const genPhase       = ref('')
const errorDetail    = ref('')
let   genPollTimer   = null

const script         = ref([])
const currentStep    = ref(0)
const isPlaying      = ref(false)
const showAnswerHint = ref(false)
const videoEl        = ref(null)
const scriptListEl   = ref(null)
const podcastLoading = ref(false)
let   stepAudio      = null

// ── Computed ──────────────────────────────────────────────────────────────────
const videoSrc = computed(() =>
  props.job?.result?.full_video
    ? `/api/jobs/${props.jobId}/stream/${props.job.result.full_video}`
    : ''
)

const progressPct = computed(() =>
  script.value.length ? (currentStep.value / (script.value.length - 1)) * 100 : 0
)

const currentItem = computed(() => script.value[currentStep.value] || null)

const currentGenStep = computed(() => PHASE_STEP_MAP[genPhase.value] || 'analyze')

function isStepDone(stepId) {
  const cur = PHASE_STEP_MAP[genPhase.value] || 'analyze'
  const curIdx = STEP_ORDER.indexOf(cur)
  const thisIdx = STEP_ORDER.indexOf(stepId)
  if (genPhase.value === 'done') return true
  return thisIdx < curIdx
}

const nowPlayingText = computed(() => {
  const item = currentItem.value
  if (!item) return ''
  if (item.type === 'speak') return item.text?.slice(0, 80) + (item.text?.length > 80 ? '...' : '')
  if (item.type === 'play')  return getSentenceText(item.sentence_id)
  if (item.type === 'question') return item.text
  return ''
})

const nowPlayingIcon = computed(() => {
  const icons = { speak: '🎙️', play: '🔊', question: '❓' }
  return icons[currentItem.value?.type] || ''
})

// ── Lifecycle ─────────────────────────────────────────────────────────────────
onMounted(async () => {
  if (!isMember.value) return
  await checkStatus()
})

onUnmounted(() => {
  clearInterval(genPollTimer)
  if (stepAudio) stepAudio.pause()
})

// ── Status / generation ───────────────────────────────────────────────────────
async function checkStatus() {
  try {
    const data = await apiFetch(`/api/jobs/${props.jobId}/tutor/status`)
    if (data.status === 'done') {
      await loadScript()
      phase.value = 'lesson'
    } else if (data.status === 'in_progress') {
      applyProgress(data)
      phase.value = 'generating'
      startPolling()
    } else if (data.status === 'error') {
      errorDetail.value = data.message || ''
      phase.value = 'error'
    } else {
      phase.value = 'idle'
    }
  } catch {
    phase.value = 'idle'
  }
}

async function startLesson() {
  phase.value = 'generating'
  genPercent.value = 0
  genMessage.value = '正在启动 AI 讲师...'
  genPhase.value   = 'queued'
  errorDetail.value = ''
  try {
    await apiFetch(`/api/jobs/${props.jobId}/tutor/generate`, { method: 'POST' })
    startPolling()
  } catch (e) {
    errorDetail.value = e?.message || '启动失败'
    phase.value = 'error'
  }
}

function startPolling() {
  clearInterval(genPollTimer)
  genPollTimer = setInterval(async () => {
    try {
      const data = await apiFetch(`/api/jobs/${props.jobId}/tutor/status`)
      if (data.status === 'done') {
        clearInterval(genPollTimer)
        genPercent.value = 100
        await loadScript()
        phase.value = 'lesson'
      } else if (data.status === 'error') {
        clearInterval(genPollTimer)
        errorDetail.value = data.message || ''
        phase.value = 'error'
      } else {
        applyProgress(data)
      }
    } catch { /* keep polling */ }
  }, 2500)
}

function applyProgress(data) {
  const p = data.progress || {}
  genPhase.value   = p.phase || genPhase.value
  genMessage.value = p.message || ''
  genPercent.value = typeof p.percent === 'number' ? p.percent : genPercent.value
}

function cancelGenerate() {
  clearInterval(genPollTimer)
  phase.value = 'idle'
}

async function loadScript() {
  const data = await apiFetch(`/api/jobs/${props.jobId}/tutor/script`)
  script.value = data.script || []
  currentStep.value = 0
}

// ── Playback ──────────────────────────────────────────────────────────────────
function togglePlay() {
  if (isPlaying.value) {
    pauseLesson()
  } else {
    resumeLesson()
  }
}

async function resumeLesson() {
  if (!script.value.length) return
  isPlaying.value = true
  showAnswerHint.value = false
  await playStep(currentStep.value)
}

function pauseLesson() {
  isPlaying.value = false
  if (stepAudio) { stepAudio.pause(); stepAudio = null }
  if (videoEl.value) videoEl.value.pause()
}

async function playStep(idx) {
  if (!isPlaying.value || idx >= script.value.length) {
    isPlaying.value = false
    return
  }
  currentStep.value = idx
  showAnswerHint.value = false
  scrollScriptToActive()

  const item = script.value[idx]
  if (item.type === 'speak') {
    await playSpeakItem(item)
  } else if (item.type === 'play') {
    await playOriginalSentence(item)
  } else if (item.type === 'question') {
    // 暂停，显示答案提示后继续
    isPlaying.value = false
    showAnswerHint.value = true
    return
  }

  if (isPlaying.value) await playStep(idx + 1)
}

async function playSpeakItem(item) {
  if (!item.tts_audio) return
  const token = localStorage.getItem('ll_token')
  const url = `/api/jobs/${props.jobId}/tutor/audio/${item.tts_audio}`
  return new Promise((resolve) => {
    fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      .then(r => r.blob())
      .then(blob => {
        const audio = new Audio(URL.createObjectURL(blob))
        stepAudio = audio
        audio.onended = () => { stepAudio = null; resolve() }
        audio.onerror = () => resolve()
        audio.play().catch(resolve)
      })
      .catch(resolve)
  })
}

async function playOriginalSentence(item) {
  const seg = props.segments[item.sentence_id]
  if (!seg || !videoEl.value) return
  return new Promise((resolve) => {
    const video = videoEl.value
    const startT = seg.video_start ?? seg.start ?? 0
    const dur = (seg.end - seg.start) + 0.5
    video.currentTime = startT
    video.play()
    const onTime = () => {
      if (video.currentTime >= startT + dur) {
        video.pause()
        video.removeEventListener('timeupdate', onTime)
        resolve()
      }
    }
    video.addEventListener('timeupdate', onTime)
    setTimeout(() => {
      video.removeEventListener('timeupdate', onTime)
      video.pause()
      resolve()
    }, dur * 1000 + 2000)
  })
}

function prevStep() {
  pauseLesson()
  if (currentStep.value > 0) currentStep.value--
  showAnswerHint.value = false
}

function nextStep() {
  pauseLesson()
  if (currentStep.value < script.value.length - 1) currentStep.value++
  showAnswerHint.value = false
}

function jumpToStep(idx) {
  pauseLesson()
  currentStep.value = idx
  showAnswerHint.value = false
}

function scrollScriptToActive() {
  nextTick(() => {
    const list = scriptListEl.value
    if (!list) return
    const el = list.querySelector('.lt-script-item.active')
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  })
}

// ── 辅助函数 ──────────────────────────────────────────────────────────────────
function getSentenceText(sid) {
  return props.segments[sid]?.text || `句子 ${sid + 1}`
}

function scriptItemIcon(item) {
  if (item.type === 'play') return '▶'
  if (item.type === 'question') return '💬'
  const subIcons = {
    grammar:      '📐',
    culture:      '🌏',
    pronunciation:'🗣️',
    usage:        '💡',
    synonym:      '🔄',
    summary:      '📝',
    transition:   '➡️',
    intro:        '👋',
    outro:        '🎓',
  }
  return subIcons[item.subtype] || '🎙️'
}

function scriptItemText(item) {
  if (item.type === 'play') return item.label || '播放原句'
  return item.text?.slice(0, 100) + (item.text?.length > 100 ? '...' : '')
}

async function downloadPodcast() {
  podcastLoading.value = true
  try {
    const token = localStorage.getItem('ll_token')
    const res = await fetch(`/api/jobs/${props.jobId}/tutor/podcast`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!res.ok) { alert('生成讲课音频失败'); return }
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${props.job?.name || 'lesson'}_讲课.mp3`
    a.click()
    setTimeout(() => URL.revokeObjectURL(url), 3000)
  } catch (e) {
    alert('下载失败: ' + e.message)
  } finally {
    podcastLoading.value = false
  }
}
</script>

<style scoped>
.lesson-tab { padding: 8px 0; }

/* ── 通用中央面板 ── */
.lt-center-panel {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 42vh;
}
.lt-center-inner {
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 16px;
}
.lt-center-inner h3 { font-size: 20px; font-weight: 800; }
.lt-hint { font-size: 13px; color: var(--text2); max-width: 320px; line-height: 1.6; }
.lt-start-btn { padding: 12px 32px; font-size: 15px; margin-top: 6px; }

/* ── VIP 门槛 ── */
.lt-gate {
  max-width: 420px;
  margin: 48px auto;
  text-align: center;
  padding: 36px 28px;
  border-radius: 18px;
  border: 1px solid var(--border);
  background: var(--bg2, #f8fafc);
}
.lt-gate-icon { font-size: 48px; margin-bottom: 12px; }
.lt-gate h3 { font-size: 18px; font-weight: 800; margin-bottom: 8px; }
.lt-gate p { color: var(--text2); font-size: 14px; margin-bottom: 20px; }

/* ── 生成中面板 ── */
.lt-gen-panel {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 50vh;
}
.lt-gen-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
  padding: 32px 24px;
  border-radius: 20px;
  border: 1px solid rgba(11,120,209,.15);
  background: rgba(255,255,255,.85);
  min-width: 340px;
  max-width: 480px;
}

/* 步骤指示器 */
.lt-steps {
  display: flex;
  gap: 6px;
  align-items: flex-start;
}
.lt-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 5px;
  flex: 1;
  opacity: .4;
  transition: opacity .3s;
}
.lt-step.active, .lt-step.done { opacity: 1; }
.lt-step-dot {
  width: 28px; height: 28px;
  border-radius: 50%;
  background: rgba(148,163,184,.2);
  border: 2px solid rgba(148,163,184,.35);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  color: var(--text3);
  transition: background .3s, border-color .3s;
}
.lt-step.active .lt-step-dot {
  background: rgba(14,165,233,.12);
  border-color: #0ea5e9;
  color: #0ea5e9;
}
.lt-step.done .lt-step-dot {
  background: #0ea5e9;
  border-color: #0ea5e9;
  color: #fff;
}
.lt-step-label { font-size: 11px; color: var(--text2); text-align: center; white-space: nowrap; }
.lt-step.active .lt-step-label { color: #0ea5e9; font-weight: 600; }

.lt-step-spin {
  display: inline-block;
  width: 12px; height: 12px;
  border: 2px solid rgba(14,165,233,.3);
  border-top-color: #0ea5e9;
  border-radius: 50%;
  animation: ltSpin .7s linear infinite;
}
@keyframes ltSpin { to { transform: rotate(360deg); } }

/* 进度条 */
.lt-progress-wrap {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
}
.lt-progress-bar {
  flex: 1;
  height: 10px;
  background: rgba(148,163,184,.2);
  border-radius: 999px;
  overflow: hidden;
  border: 1px solid rgba(148,163,184,.2);
}
.lt-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #0f4c81, #0ea5e9 55%, #22d3ee);
  border-radius: inherit;
  transition: width .6s ease;
  min-width: 4px;
}
.lt-progress-pct {
  font-size: 13px;
  font-weight: 700;
  color: #0ea5e9;
  white-space: nowrap;
  min-width: 36px;
  text-align: right;
}

.lt-gen-msg {
  font-size: 13px;
  color: var(--text2);
  text-align: center;
  line-height: 1.5;
  min-height: 18px;
}
.lt-cancel-btn { font-size: 12px; padding: 6px 16px; }

/* ── 错误状态 ── */
.lt-error-detail {
  margin: 8px 0 12px;
  max-height: 160px;
  overflow: auto;
  text-align: left;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 11px;
  color: #7f1d1d;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 10px;
  padding: 10px;
  max-width: 400px;
}

/* ── 课程布局 ── */
.lt-lesson-layout {
  display: grid;
  grid-template-columns: 1fr 360px;
  gap: 16px;
  align-items: start;
}

/* 左侧 */
.lt-left {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px;
  border-radius: 16px;
  border: 1px solid rgba(11,120,209,.12);
  background: rgba(255,255,255,.8);
}
.lt-video-wrap {
  background: #000;
  border-radius: 12px;
  overflow: hidden;
  aspect-ratio: 16/9;
  box-shadow: 0 8px 24px rgba(15,23,42,.2);
}
.lt-video { width: 100%; height: 100%; display: block; object-fit: contain; }

/* 当前播放提示 */
.lt-now-playing {
  padding: 9px 12px;
  border-radius: 10px;
  background: rgba(255,255,255,.75);
  border: 1px solid rgba(11,120,209,.13);
  border-left: 4px solid #0ea5e9;
  font-size: 13px;
  color: var(--text2);
  display: flex;
  align-items: flex-start;
  gap: 8px;
  min-height: 42px;
  line-height: 1.45;
}
.lt-now-playing.play     { border-left-color: #1d4ed8; }
.lt-now-playing.question { border-left-color: #f59e0b; }
.lt-np-icon { flex-shrink: 0; margin-top: 1px; }
.lt-np-text { flex: 1; }

/* 进度条 */
.lt-lesson-progress {
  display: flex;
  align-items: center;
  gap: 10px;
}
.lt-lp-bar {
  flex: 1;
  height: 9px;
  background: rgba(148,163,184,.22);
  border-radius: 999px;
  overflow: hidden;
  border: 1px solid rgba(148,163,184,.18);
}
.lt-lp-fill {
  height: 100%;
  background: linear-gradient(90deg, #0f4c81, #0ea5e9 55%, #f59e0b);
  border-radius: inherit;
  transition: width .35s ease;
}
.lt-lp-label { font-size: 12px; font-weight: 700; color: var(--text2); white-space: nowrap; }

/* 答案提示 */
.lt-answer-hint {
  padding: 10px 14px;
  background: rgba(245,158,11,.06);
  border: 1px solid rgba(245,158,11,.25);
  border-radius: 10px;
}
.lt-hint-label { font-size: 11px; font-weight: 700; color: #b45309; display: block; margin-bottom: 4px; }
.lt-answer-hint p { font-size: 13px; color: var(--text); margin: 0; line-height: 1.55; }

/* 控制器 */
.lt-controls {
  display: flex;
  gap: 8px;
}
.lt-ctrl-btn {
  flex: 1;
  padding: 10px 8px;
  border-radius: 10px;
  border: 1px solid rgba(148,163,184,.28);
  background: rgba(255,255,255,.92);
  font-size: 13px;
  color: var(--text);
  cursor: pointer;
  transition: .16s ease;
  white-space: nowrap;
}
.lt-ctrl-btn:hover:not(:disabled) { border-color: rgba(11,120,209,.3); transform: translateY(-1px); }
.lt-ctrl-btn:disabled { opacity: .45; cursor: not-allowed; }
.lt-ctrl-btn.primary {
  color: #fff;
  border: none;
  background: linear-gradient(135deg, #0f4c81, #0ea5e9 55%, #f59e0b);
  box-shadow: 0 6px 18px rgba(11,120,209,.22);
  font-weight: 700;
}

.lt-podcast-row { display: flex; align-items: center; gap: 8px; }
.lt-dl-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 13px;
  padding: 8px 16px;
}

.lt-spinner {
  display: inline-block;
  width: 14px; height: 14px;
  border: 2px solid rgba(148,163,184,.3);
  border-top-color: #0ea5e9;
  border-radius: 50%;
  animation: ltSpin .7s linear infinite;
}

/* 右侧脚本面板 */
.lt-right {
  border-radius: 16px;
  border: 1px solid rgba(11,120,209,.12);
  background: rgba(255,255,255,.82);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 180px);
}
.lt-script-header {
  padding: 12px 14px;
  border-bottom: 1px solid rgba(148,163,184,.2);
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}
.lt-script-header h3 { font-size: 15px; font-weight: 800; color: #0d4d80; margin: 0; }
.lt-script-job { font-size: 11px; color: var(--text3); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.lt-script-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.lt-script-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 9px;
  cursor: pointer;
  border: 1px solid transparent;
  background: rgba(255,255,255,.7);
  transition: background .16s, border-color .16s;
}
.lt-script-item:hover { border-color: rgba(11,120,209,.2); background: rgba(255,255,255,.95); }
.lt-script-item.active {
  background: rgba(14,165,233,.08);
  border-color: rgba(14,165,233,.3);
}
.lt-item-icon {
  flex-shrink: 0;
  font-size: 14px;
  margin-top: 1px;
  width: 18px;
  text-align: center;
}
.lt-item-body { flex: 1; min-width: 0; }
.lt-item-text {
  font-size: 12.5px;
  color: var(--text2);
  line-height: 1.45;
  margin: 0;
  word-break: break-word;
}
.lt-item-sub {
  display: block;
  font-size: 11.5px;
  color: var(--text3);
  font-style: italic;
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 颜色区分 */
.lt-script-item.play .lt-item-icon    { color: #1d4ed8; }
.lt-script-item.question .lt-item-icon { color: #b45309; }
.lt-script-item.speak .lt-item-icon   { color: #0ea5e9; }

/* 响应式 */
@media (max-width: 900px) {
  .lt-lesson-layout { grid-template-columns: 1fr; }
  .lt-right { max-height: none; }
}
@media (max-width: 600px) {
  .lt-controls { flex-wrap: wrap; }
  .lt-ctrl-btn { min-width: 120px; }
  .lt-steps { gap: 4px; }
}
</style>
