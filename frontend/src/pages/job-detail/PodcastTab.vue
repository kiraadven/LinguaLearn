<template>
  <div class="podcast-tab">

    <!-- 未开始 -->
    <div v-if="status === 'not_started'" class="pt-empty">
      <div class="pt-icon">🎧</div>
      <h3>{{ tr('podcast_player_title', '随身听') }}</h3>
      <p class="pt-hint">{{ tr('podcast_player_hint', '通勤途中收听，无需看屏幕') }}</p>
      <button class="btn-primary pt-gen-btn" :disabled="loading" @click="generate">
        <span v-if="loading" class="pt-spinner"></span>
        {{ loading ? '...' : tr('podcast_generate_btn', '生成随身听') }}
      </button>
    </div>

    <!-- 生成中 -->
    <div v-else-if="status === 'in_progress'" class="pt-generating">

      <!-- 步骤指示器 -->
      <div class="pt-steps">
        <div
          v-for="step in GEN_STEPS"
          :key="step.id"
          class="pt-step"
          :class="{ active: currentGenStep === step.id, done: isStepDone(step.id) }"
        >
          <div class="pt-step-dot">
            <span v-if="isStepDone(step.id)">✓</span>
            <span v-else-if="currentGenStep === step.id" class="pt-step-spin"></span>
            <span v-else>{{ step.num }}</span>
          </div>
          <span class="pt-step-label">{{ step.label }}</span>
        </div>
      </div>

      <!-- 进度条 -->
      <div class="pt-progress-wrap">
        <div class="pt-progress-bar">
          <div class="pt-progress-fill" :style="{ width: progressPercent + '%' }"></div>
        </div>
        <span class="pt-progress-pct">{{ progressPercent }}%</span>
      </div>

      <p class="pt-status-msg">{{ progressMessage || tr('podcast_generating', '正在生成中，请稍候...') }}</p>

      <!-- 细节数据 -->
      <div v-if="lessonSpeakTotal > 0 || podcastSpeakTotal > 0" class="pt-counters">
        <div v-if="lessonSpeakTotal > 0" class="pt-counter-item">
          <span class="pt-counter-label">讲课语音</span>
          <span class="pt-counter-val">{{ lessonSpeakReady }} / {{ lessonSpeakTotal }}</span>
        </div>
        <div v-if="podcastSpeakTotal > 0" class="pt-counter-item">
          <span class="pt-counter-label">随身听语音</span>
          <span class="pt-counter-val">{{ podcastSpeakReady }} / {{ podcastSpeakTotal }}</span>
        </div>
      </div>
    </div>

    <!-- 播放器 -->
    <div v-else-if="status === 'done'" class="pt-player-view">
      <div class="pt-player-header">
        <h3>{{ tr('podcast_player_title', '随身听') }}</h3>
        <p class="pt-player-hint">{{ tr('podcast_player_hint', '通勤途中收听，无需看屏幕') }}</p>
      </div>

      <!-- 音频播放器 -->
      <div v-if="loadingBlob" class="pt-blob-loading">
        <span class="pt-spinner"></span>
        <span>加载音频...</span>
      </div>
      <audio
        v-else-if="podcastBlobUrl"
        controls
        :src="podcastBlobUrl"
        class="pt-audio"
      ></audio>

      <!-- 下载按钮 -->
      <button class="pt-dl-btn" :disabled="downloading" @click="downloadPodcast">
        <span v-if="downloading" class="pt-spinner small"></span>
        {{ downloading ? '...' : tr('podcast_download_btn', '⬇ 下载 MP3') }}
      </button>

      <!-- 句子参考列表 -->
      <div v-if="segments && segments.length" class="pt-sentences">
        <div class="pt-section-title">{{ tr('podcast_sentence_list_title', '内容参考') }}</div>
        <div v-for="(s, i) in segments" :key="i" class="pt-sentence-item">
          <span class="pt-sentence-num">{{ i + 1 }}</span>
          <span class="pt-sentence-text">{{ s.text }}</span>
        </div>
      </div>
    </div>

    <!-- 错误 -->
    <div v-else-if="status === 'error'" class="pt-error">
      <div class="pt-icon">⚠️</div>
      <p>{{ tr('podcast_gen_error', '生成失败，请重试') }}</p>
      <pre v-if="errorDetail" class="pt-error-detail">{{ errorDetail }}</pre>
      <button class="btn-primary pt-gen-btn" @click="generate">
        {{ tr('podcast_generate_btn', '重新生成') }}
      </button>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { apiFetch } from '../../composables/useApi.js'
import { useI18n } from '../../i18n.js'

const props = defineProps({
  jobId:    { type: String, required: true },
  segments: { type: Array, default: () => [] },
})

const { t } = useI18n()

function tr(key, fallback = '') {
  return t.value?.[key] ?? fallback
}

// ── 生成步骤 ──────────────────────────────────────────────────────────────────
const GEN_STEPS = [
  { id: 'analyze', num: '1', label: '分析内容' },
  { id: 'plan',    num: '2', label: '规划课程' },
  { id: 'write',   num: '3', label: '生成脚本' },
  { id: 'tts',     num: '4', label: '合成语音' },
]

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
const status           = ref('not_started')
const loading          = ref(false)
const podcastBlobUrl   = ref(null)
const loadingBlob      = ref(false)
const downloading      = ref(false)
const progressMessage  = ref('')
const progressPhase    = ref('')
const progressPercent  = ref(0)
const lessonSpeakReady = ref(0)
const lessonSpeakTotal = ref(0)
const podcastSpeakReady= ref(0)
const podcastSpeakTotal= ref(0)
const errorDetail      = ref('')
let   pollTimer        = null

// ── Computed ──────────────────────────────────────────────────────────────────
const currentGenStep = computed(() => PHASE_STEP_MAP[progressPhase.value] || 'analyze')

function isStepDone(stepId) {
  if (progressPhase.value === 'done') return true
  const cur = PHASE_STEP_MAP[progressPhase.value] || 'analyze'
  return STEP_ORDER.indexOf(stepId) < STEP_ORDER.indexOf(cur)
}

// ── Lifecycle ─────────────────────────────────────────────────────────────────
onMounted(async () => {
  try {
    const data = await apiFetch(`/api/jobs/${props.jobId}/tutor/status`)
    applyStatus(data)
    if (status.value === 'in_progress') startPolling()
    if (status.value === 'done') fetchBlobUrl()
  } catch {
    status.value = 'not_started'
  }
})

onUnmounted(() => {
  clearInterval(pollTimer)
  if (podcastBlobUrl.value) URL.revokeObjectURL(podcastBlobUrl.value)
})

// ── Actions ───────────────────────────────────────────────────────────────────
async function generate() {
  loading.value = true
  errorDetail.value = ''
  try {
    const data = await apiFetch(`/api/jobs/${props.jobId}/tutor/generate`, { method: 'POST' })
    progressMessage.value = data?.message || '任务已启动'
    status.value = 'in_progress'
    progressPercent.value = 0
    progressPhase.value = 'queued'
    startPolling()
  } catch {
    status.value = 'error'
    errorDetail.value = '启动生成失败'
  } finally {
    loading.value = false
  }
}

function applyStatus(data = {}) {
  const s = data.status || 'not_started'
  status.value = s
  const p = data.progress || {}
  progressMessage.value  = p.message || ''
  progressPhase.value    = p.phase || ''
  progressPercent.value  = typeof p.percent === 'number' ? p.percent : progressPercent.value
  lessonSpeakReady.value = Number(data.lesson?.speak_ready || 0)
  lessonSpeakTotal.value = Number(data.lesson?.speak_total || 0)
  podcastSpeakReady.value= Number(data.podcast?.speak_ready || 0)
  podcastSpeakTotal.value= Number(data.podcast?.speak_total || 0)
  if (s === 'error') {
    errorDetail.value = String(data.message || p.message || '未知错误').slice(0, 2000)
  }
}

function startPolling() {
  clearInterval(pollTimer)
  pollTimer = setInterval(async () => {
    try {
      const data = await apiFetch(`/api/jobs/${props.jobId}/tutor/status`)
      applyStatus(data)
      if (data.status === 'done') {
        clearInterval(pollTimer)
        progressPercent.value = 100
        await fetchBlobUrl()
      } else if (data.status === 'error') {
        clearInterval(pollTimer)
      }
    } catch { /* keep polling */ }
  }, 2500)
}

async function fetchBlobUrl() {
  loadingBlob.value = true
  try {
    const token = localStorage.getItem('ll_token')
    const res = await fetch(`/api/jobs/${props.jobId}/tutor/podcast`, {
      headers: token ? { Authorization: 'Bearer ' + token } : {},
    })
    if (!res.ok) throw new Error('fetch failed')
    const blob = await res.blob()
    if (podcastBlobUrl.value) URL.revokeObjectURL(podcastBlobUrl.value)
    podcastBlobUrl.value = URL.createObjectURL(blob)
  } catch {
    // podcast may not exist yet — it's built on demand; just skip
    loadingBlob.value = false
    return
  } finally {
    loadingBlob.value = false
  }
}

async function downloadPodcast() {
  downloading.value = true
  try {
    const token = localStorage.getItem('ll_token')
    const res = await fetch(`/api/jobs/${props.jobId}/tutor/podcast`, {
      headers: token ? { Authorization: 'Bearer ' + token } : {},
    })
    if (!res.ok) throw new Error('download failed')
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `podcast_${props.jobId}.mp3`
    a.click()
    setTimeout(() => URL.revokeObjectURL(url), 3000)
  } catch (e) {
    alert('下载失败: ' + (e.message || ''))
  } finally {
    downloading.value = false
  }
}
</script>

<style scoped>
.podcast-tab { padding: 20px 0; }

/* ── 空闲/错误 通用 ── */
.pt-empty, .pt-error {
  max-width: 420px;
  margin: 48px auto;
  text-align: center;
  padding: 36px 28px;
  border-radius: 18px;
  border: 1px solid var(--border);
  background: var(--bg2, #f8fafc);
}
.pt-icon { font-size: 48px; margin-bottom: 12px; }
.pt-empty h3 { font-size: 18px; font-weight: 800; margin-bottom: 8px; }
.pt-hint { color: var(--text2); font-size: 14px; margin-bottom: 20px; line-height: 1.6; }
.pt-gen-btn { padding: 11px 28px; font-size: 14px; display: inline-flex; align-items: center; gap: 6px; }

/* ── 生成中 ── */
.pt-generating {
  max-width: 480px;
  margin: 0 auto;
  padding: 32px 24px;
  border-radius: 20px;
  border: 1px solid rgba(11,120,209,.13);
  background: rgba(255,255,255,.85);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 18px;
}

/* 步骤 */
.pt-steps {
  display: flex;
  gap: 6px;
  width: 100%;
}
.pt-step {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 5px;
  opacity: .4;
  transition: opacity .3s;
}
.pt-step.active, .pt-step.done { opacity: 1; }
.pt-step-dot {
  width: 28px; height: 28px;
  border-radius: 50%;
  background: rgba(148,163,184,.18);
  border: 2px solid rgba(148,163,184,.3);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  color: var(--text3);
  transition: background .3s, border-color .3s;
}
.pt-step.active .pt-step-dot {
  background: rgba(14,165,233,.1);
  border-color: #0ea5e9;
  color: #0ea5e9;
}
.pt-step.done .pt-step-dot {
  background: #0ea5e9;
  border-color: #0ea5e9;
  color: #fff;
}
.pt-step-label { font-size: 11px; color: var(--text2); text-align: center; white-space: nowrap; }
.pt-step.active .pt-step-label { color: #0ea5e9; font-weight: 600; }

.pt-step-spin {
  display: inline-block;
  width: 12px; height: 12px;
  border: 2px solid rgba(14,165,233,.3);
  border-top-color: #0ea5e9;
  border-radius: 50%;
  animation: ptSpin .7s linear infinite;
}
@keyframes ptSpin { to { transform: rotate(360deg); } }

/* 进度条 */
.pt-progress-wrap {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
}
.pt-progress-bar {
  flex: 1;
  height: 10px;
  background: rgba(148,163,184,.2);
  border-radius: 999px;
  overflow: hidden;
}
.pt-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #0f4c81, #0ea5e9 55%, #22d3ee);
  border-radius: inherit;
  transition: width .6s ease;
  min-width: 4px;
}
.pt-progress-pct {
  font-size: 13px;
  font-weight: 700;
  color: #0ea5e9;
  white-space: nowrap;
  min-width: 36px;
  text-align: right;
}

.pt-status-msg { font-size: 13px; color: var(--text2); text-align: center; line-height: 1.5; min-height: 18px; }

.pt-counters {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  justify-content: center;
}
.pt-counter-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  font-size: 12px;
  padding: 6px 12px;
  border-radius: 8px;
  background: rgba(14,165,233,.06);
  border: 1px solid rgba(14,165,233,.12);
}
.pt-counter-label { color: var(--text3); font-size: 11px; }
.pt-counter-val { font-weight: 700; color: #0ea5e9; }

/* ── 播放器 ── */
.pt-player-view {
  max-width: 720px;
  margin: 0 auto;
}
.pt-player-header { margin-bottom: 18px; }
.pt-player-header h3 { font-size: 20px; font-weight: 800; margin-bottom: 4px; }
.pt-player-hint { color: var(--text2); font-size: 13px; margin: 0; }

.pt-audio {
  width: 100%;
  border-radius: 12px;
  margin-bottom: 12px;
  background: var(--bg2, #f1f5f9);
}
.pt-blob-loading {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 0;
  color: var(--text2);
  font-size: 14px;
}

.pt-dl-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 9px 20px;
  border-radius: 999px;
  border: 1px solid var(--accent);
  color: var(--accent);
  font-size: 13px;
  font-weight: 700;
  background: transparent;
  cursor: pointer;
  transition: background .15s, color .15s;
  margin-bottom: 28px;
}
.pt-dl-btn:hover:not(:disabled) { background: var(--accent); color: #fff; }
.pt-dl-btn:disabled { opacity: .5; cursor: not-allowed; }

/* 句子列表 */
.pt-sentences { border-top: 1px solid var(--border); padding-top: 20px; }
.pt-section-title {
  font-size: 11px;
  font-weight: 700;
  color: var(--text3);
  text-transform: uppercase;
  letter-spacing: .06em;
  margin-bottom: 12px;
}
.pt-sentence-item {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 8px 0;
  border-bottom: 1px solid rgba(0,0,0,.04);
  font-size: 14px;
  line-height: 1.55;
}
.pt-sentence-num {
  flex-shrink: 0;
  width: 22px; height: 22px;
  border-radius: 50%;
  background: rgba(14,165,233,.1);
  color: var(--accent);
  font-size: 11px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 1px;
}
.pt-sentence-text { color: var(--text); }

/* 错误 */
.pt-error-detail {
  margin: 10px 0 14px;
  max-height: 180px;
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
}

/* Spinner */
.pt-spinner {
  display: inline-block;
  width: 18px; height: 18px;
  border: 2px solid rgba(14,165,233,.2);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: ptSpin .8s linear infinite;
  flex-shrink: 0;
}
.pt-spinner.small { width: 12px; height: 12px; }
</style>
