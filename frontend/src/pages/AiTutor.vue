<template>
  <div class="tutor-page page-inner">
    <!-- Aurora glow orbs -->
    <div class="tp-glow tp-glow-a"></div>
    <div class="tp-glow tp-glow-b"></div>

    <div class="page-header">
      <div class="page-header-badge">🎙️ {{ tr('tutor_badge', 'AI 伴学讲师') }}</div>
      <h1>{{ tr('tutor_page_title', 'AI 互动课堂') }}</h1>
      <p>{{ tr('tutor_page_sub', '从你的学习视频生成可跟读、可回放、可导出的智能讲课流程') }}</p>
    </div>

    <!-- 未登录 -->
    <section v-if="!isLoggedIn" class="panel empty">
      <div class="empty-icon">🔒</div>
      <p>{{ tr('create_login_required', 'Please log in first') }}</p>
      <button class="btn primary" @click="openAuth?.()">{{ tr('nav_login_register', 'Login / Register') }}</button>
    </section>

    <template v-else>

      <!-- 选择视频 -->
      <section v-if="phase === 'select'" class="panel select-panel">
        <header class="panel-head">
          <h2>{{ tr('tutor_select_video', '选择一个已完成的视频，开始 AI 讲课') }}</h2>
        </header>
        <div v-if="loadingJobs" class="loading-row">
          <span class="spinner"></span>{{ tr('loading', '加载中...') }}
        </div>
        <div v-else-if="doneJobs.length === 0" class="empty-hint">
          {{ tr('tutor_no_jobs', '暂无已完成的视频，请先在"创建"页面生成视频') }}
        </div>
        <ul v-else class="job-list">
          <li
            v-for="j in doneJobs" :key="j.id"
            class="job-item"
            @click="selectJob(j)"
          >
            <span class="job-name">{{ j.name || j.video_filename || j.id }}</span>
            <span class="job-meta">{{ j.source_lang }} → {{ j.target_lang }}</span>
            <span class="job-badge done">{{ tr('status_done', '已完成') }}</span>
          </li>
        </ul>
      </section>

      <!-- 生成中 / 等待 -->
      <section v-else-if="phase === 'generating'" class="panel center-panel">
        <div class="gen-status">
          <div class="gen-icon">
            <span class="spinner large"></span>
          </div>
          <h3>{{ genStatusText }}</h3>
          <p class="gen-hint">{{ tr('tutor_gen_hint', '首次生成需要约 30-60 秒，请稍候') }}</p>
          <button class="btn ghost" @click="cancelGenerate">{{ tr('cancel', '取消') }}</button>
        </div>
      </section>

      <!-- 主讲课界面 -->
      <section v-else-if="phase === 'lesson'" class="lesson-layout">

        <!-- 左侧：视频 + 控制区 -->
        <div class="lesson-left">

          <!-- 视频播放器 -->
          <div class="video-wrap">
            <video
              ref="videoEl"
              class="lesson-video"
              :src="videoSrc"
              preload="auto"
              @timeupdate="onTimeUpdate"
            ></video>
          </div>

          <!-- 当前正在播放的内容说明 -->
          <div class="now-playing" :class="nowPlayingClass">
            <span class="np-icon">{{ nowPlayingIcon }}</span>
            <span class="np-text">{{ nowPlayingText }}</span>
          </div>

          <!-- 进度条 -->
          <div class="lesson-progress">
            <div class="progress-bar">
              <div
                class="progress-fill"
                :style="{ width: progressPct + '%' }"
              ></div>
            </div>
            <span class="progress-label">{{ currentStep + 1 }} / {{ script.length }}</span>
          </div>

          <!-- 控制按钮 -->
          <div class="lesson-controls">
            <button class="ctrl-btn" :disabled="isPlaying" @click="prevStep">
              {{ tr('tutor_prev', '上一步') }}
            </button>
            <button
              class="ctrl-btn primary"
              @click="isPlaying ? pauseLesson() : resumeLesson()"
            >
              {{ isPlaying ? tr('tutor_pause', '暂停') : tr('tutor_play', '继续') }}
            </button>
            <button class="ctrl-btn" :disabled="isPlaying" @click="nextStep">
              {{ tr('tutor_next', '下一步') }}
            </button>
          </div>

          <!-- Podcast 下载 -->
          <div class="podcast-row">
            <button class="btn ghost podcast-btn" @click="downloadPodcast" :disabled="podcastLoading">
              <span v-if="podcastLoading" class="spinner small"></span>
              🎧 {{ tr('tutor_download_podcast', '下载讲课音频') }}
            </button>
            <span class="podcast-hint">{{ tr('tutor_podcast_hint', '通勤途中收听完整讲课') }}</span>
          </div>
        </div>

        <!-- 右侧：脚本面板 -->
        <div class="lesson-right">
          <div class="script-header">
            <h3>{{ tr('tutor_script', '课程脚本') }}</h3>
            <span class="job-label">{{ selectedJob?.name || selectedJob?.video_filename }}</span>
          </div>

          <div class="script-list" ref="scriptListEl">
            <div
              v-for="(item, idx) in script"
              :key="idx"
              class="script-item"
              :class="[item.type, { active: idx === currentStep }]"
              @click="jumpToStep(idx)"
            >
              <!-- AI 讲解 -->
              <template v-if="item.type === 'speak'">
                <span class="item-icon">
                  {{ item.subtype === 'grammar' ? '📐' : item.subtype === 'culture' ? '🌏' : '🎙️' }}
                </span>
                <p class="item-text">{{ item.text }}</p>
              </template>

              <!-- 播放原句 -->
              <template v-else-if="item.type === 'play'">
                <span class="item-icon">▶</span>
                <p class="item-text">
                  {{ item.label || '播放原句' }}
                  <span class="sentence-preview">{{ getSentenceText(item.sentence_id) }}</span>
                </p>
              </template>

              <!-- 互动提问 -->
              <template v-else-if="item.type === 'question'">
                <span class="item-icon">💬</span>
                <p class="item-text">{{ item.text }}</p>
              </template>
            </div>
          </div>
        </div>

      </section>

    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch, onBeforeUnmount, inject, nextTick } from 'vue'
import { useI18n } from '../i18n.js'
import { useAuth } from '../composables/useAuth.js'

const { t } = useI18n()
const { isLoggedIn } = useAuth()
const openAuth = inject('openAuth', null)
const API = ''  // 同源

function tr(key, fallback = '') {
  return ((t.value?.[key]) ?? fallback) || key
}

// ── 状态 ─────────────────────────────────────────────────────────────────────
const phase = ref('select')          // 'select' | 'generating' | 'lesson'
const loadingJobs = ref(false)
const doneJobs = ref([])
const selectedJob = ref(null)
const segments = ref([])

const script = ref([])               // lesson_script 数组
const currentStep = ref(0)
const isPlaying = ref(false)

const videoEl = ref(null)
const scriptListEl = ref(null)
const podcastLoading = ref(false)

const genStatusText = ref('')
let genPollTimer = null
let stepAudio = null                 // 当前正在播放的 Audio 对象

// ── 计算属性 ──────────────────────────────────────────────────────────────────
const videoSrc = computed(() => {
  if (!selectedJob.value?.result?.full_video) return ''
  return `/api/jobs/${selectedJob.value.id}/stream/${selectedJob.value.result.full_video}`
})

const progressPct = computed(() =>
  script.value.length ? (currentStep.value / (script.value.length - 1)) * 100 : 0
)

const currentItem = computed(() => script.value[currentStep.value] || null)

const nowPlayingText = computed(() => {
  if (!currentItem.value) return ''
  if (currentItem.value.type === 'speak') return currentItem.value.text.slice(0, 60) + (currentItem.value.text.length > 60 ? '...' : '')
  if (currentItem.value.type === 'play') return `▶ ${getSentenceText(currentItem.value.sentence_id)}`
  if (currentItem.value.type === 'question') return `❓ ${currentItem.value.text}`
  return ''
})

const nowPlayingClass = computed(() => currentItem.value?.type || '')
const nowPlayingIcon = computed(() => {
  if (!currentItem.value) return ''
  return { speak: '🎙️', play: '🔊', question: '💬' }[currentItem.value.type] || ''
})

// ── 初始化：加载已完成的 jobs ─────────────────────────────────────────────────
async function loadJobs() {
  loadingJobs.value = true
  try {
    const token = localStorage.getItem('ll_token')
    const res = await fetch(`${API}/api/jobs`, {
      headers: { Authorization: `Bearer ${token}` }
    })
    const data = await res.json()
    doneJobs.value = (data.jobs || []).filter(j => j.status === 'done')
  } catch (e) {
    console.error('loadJobs error', e)
  } finally {
    loadingJobs.value = false
  }
}

watch(isLoggedIn, (v) => { if (v) loadJobs() }, { immediate: true })

// ── 选择 Job ──────────────────────────────────────────────────────────────────
async function selectJob(job) {
  selectedJob.value = job
  await loadSegments(job.id)
  await checkAndStartLesson(job.id)
}

async function loadSegments(jobId) {
  try {
    const token = localStorage.getItem('ll_token')
    const res = await fetch(`/api/jobs/${jobId}/preview/segments.json`, {
      headers: { Authorization: `Bearer ${token}` }
    })
    if (res.ok) segments.value = await res.json()
  } catch (e) { /* segments 加载失败不阻断 */ }
}

async function checkAndStartLesson(jobId) {
  const token = localStorage.getItem('ll_token')
  // 查询脚本状态
  const res = await fetch(`/api/jobs/${jobId}/tutor/status`, {
    headers: { Authorization: `Bearer ${token}` }
  })
  const data = await res.json()

  if (data.status === 'done') {
    await loadScript(jobId)
    phase.value = 'lesson'
  } else if (data.status === 'in_progress') {
    phase.value = 'generating'
    genStatusText.value = tr('tutor_gen_in_progress', '正在生成课程脚本...')
    startPolling(jobId)
  } else {
    // 触发生成
    phase.value = 'generating'
    genStatusText.value = tr('tutor_gen_starting', '正在启动 AI 讲师...')
    await fetch(`/api/jobs/${jobId}/tutor/generate`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` }
    })
    startPolling(jobId)
  }
}

async function loadScript(jobId) {
  const token = localStorage.getItem('ll_token')
  const res = await fetch(`/api/jobs/${jobId}/tutor/script`, {
    headers: { Authorization: `Bearer ${token}` }
  })
  const data = await res.json()
  script.value = data.script || []
  currentStep.value = 0
}

// ── 轮询生成状态 ──────────────────────────────────────────────────────────────
function startPolling(jobId) {
  genPollTimer = setInterval(async () => {
    const token = localStorage.getItem('ll_token')
    const res = await fetch(`/api/jobs/${jobId}/tutor/status`, {
      headers: { Authorization: `Bearer ${token}` }
    })
    const data = await res.json()
    if (data.status === 'done') {
      clearInterval(genPollTimer)
      await loadScript(jobId)
      phase.value = 'lesson'
    } else if (data.status === 'error') {
      clearInterval(genPollTimer)
      genStatusText.value = `生成失败: ${data.message}`
    } else {
      genStatusText.value = tr('tutor_gen_in_progress', '正在生成课程脚本...')
    }
  }, 3000)
}

function cancelGenerate() {
  clearInterval(genPollTimer)
  phase.value = 'select'
  selectedJob.value = null
}

// ── 课程播放控制 ──────────────────────────────────────────────────────────────
async function resumeLesson() {
  if (!script.value.length) return
  isPlaying.value = true
  await playStep(currentStep.value)
}

function pauseLesson() {
  isPlaying.value = false
  if (stepAudio) { stepAudio.pause(); stepAudio = null }
  if (videoEl.value) videoEl.value.pause()
}

async function playStep(idx) {
  if (idx >= script.value.length) {
    isPlaying.value = false
    return
  }
  currentStep.value = idx
  scrollScriptToActive()

  const item = script.value[idx]

  if (item.type === 'speak') {
    await playSpeakItem(item, idx)
  } else if (item.type === 'play') {
    await playOriginalSentence(item, idx)
  } else if (item.type === 'question') {
    // 互动提问：暂停，等用户点击"继续"
    isPlaying.value = false
    return
  }

  // 播完后自动进入下一步
  if (isPlaying.value) {
    await playStep(idx + 1)
  }
}

async function playSpeakItem(item, idx) {
  if (!item.tts_audio) return  // TTS 未就绪，跳过

  const token = localStorage.getItem('ll_token')
  const url = `/api/jobs/${selectedJob.value.id}/tutor/audio/${item.tts_audio}?token=${token}`

  return new Promise((resolve) => {
    const audio = new Audio()
    // 通过带 token 的请求获取音频
    fetch(url, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.blob())
      .then(blob => {
        audio.src = URL.createObjectURL(blob)
        stepAudio = audio
        audio.onended = () => { stepAudio = null; resolve() }
        audio.onerror = () => resolve()
        audio.play().catch(resolve)
      })
      .catch(resolve)
  })
}

async function playOriginalSentence(item, idx) {
  const seg = segments.value[item.sentence_id]
  if (!seg || !videoEl.value) return

  return new Promise((resolve) => {
    const video = videoEl.value
    // 跳到句子的 video_start 时间戳
    video.currentTime = seg.video_start ?? seg.start ?? 0
    video.play()

    const onTime = () => {
      const endTime = (seg.video_start ?? seg.start) + (seg.end - seg.start) + 0.5
      if (video.currentTime >= endTime) {
        video.pause()
        video.removeEventListener('timeupdate', onTime)
        resolve()
      }
    }
    video.addEventListener('timeupdate', onTime)
    // 超时保护
    setTimeout(() => {
      video.removeEventListener('timeupdate', onTime)
      video.pause()
      resolve()
    }, (seg.end - seg.start + 3) * 1000)
  })
}

// ── 步骤导航 ──────────────────────────────────────────────────────────────────
async function prevStep() {
  pauseLesson()
  if (currentStep.value > 0) currentStep.value--
}

async function nextStep() {
  pauseLesson()
  if (currentStep.value < script.value.length - 1) currentStep.value++
}

async function jumpToStep(idx) {
  pauseLesson()
  currentStep.value = idx
}

// ── 时间同步 ──────────────────────────────────────────────────────────────────
function onTimeUpdate() { /* 仅用于视频进度反馈，目前留空 */ }

// ── 自动滚动脚本列表到当前步骤 ───────────────────────────────────────────────
function scrollScriptToActive() {
  nextTick(() => {
    const list = scriptListEl.value
    if (!list) return
    const active = list.querySelector('.script-item.active')
    if (active) active.scrollIntoView({ behavior: 'smooth', block: 'center' })
  })
}

// ── 工具函数 ──────────────────────────────────────────────────────────────────
function getSentenceText(sentence_id) {
  return segments.value[sentence_id]?.text || `句子 ${sentence_id + 1}`
}

// ── Podcast 下载 ──────────────────────────────────────────────────────────────
async function downloadPodcast() {
  if (!selectedJob.value) return
  podcastLoading.value = true
  try {
    const token = localStorage.getItem('ll_token')
    const res = await fetch(`/api/jobs/${selectedJob.value.id}/tutor/podcast`, {
      headers: { Authorization: `Bearer ${token}` }
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      alert(err.detail || '生成 Podcast 失败')
      return
    }
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${selectedJob.value.name || 'lesson'}_讲课.mp3`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    alert('下载失败: ' + e.message)
  } finally {
    podcastLoading.value = false
  }
}

// ── 清理 ──────────────────────────────────────────────────────────────────────
onBeforeUnmount(() => {
  clearInterval(genPollTimer)
  if (stepAudio) stepAudio.pause()
})
</script>

<style scoped>
/* Aurora glow orbs */
.tp-glow {
  position: fixed;
  border-radius: 50%;
  filter: blur(90px);
  pointer-events: none;
  z-index: 0;
}
.tp-glow-a {
  width: 500px; height: 500px;
  top: -100px; left: -150px;
  background: radial-gradient(circle, rgba(11,120,209,0.15), transparent 70%);
  animation: tpDrift 15s ease-in-out infinite;
}
.tp-glow-b {
  width: 400px; height: 400px;
  bottom: 60px; right: -80px;
  background: radial-gradient(circle, rgba(242,168,44,0.13), transparent 70%);
  animation: tpDrift 19s ease-in-out infinite reverse;
}
@keyframes tpDrift {
  0%, 100% { transform: translateY(0) scale(1); }
  50% { transform: translateY(36px) scale(1.06); }
}

.tutor-page {
  max-width: 1180px;
  margin: 0 auto;
  padding: 28px 24px 76px;
  display: flex;
  flex-direction: column;
  gap: 18px;
  position: relative;
}

.page-header {
  position: relative;
  z-index: 1;
}

.page-header-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 999px;
  border: 1px solid rgba(11,120,209,0.2);
  background: linear-gradient(120deg, rgba(255,255,255,0.88), rgba(240,249,255,0.7));
  backdrop-filter: blur(8px);
  font-size: 11px;
  font-weight: 700;
  color: #0d4d80;
  letter-spacing: 0.5px;
  margin-bottom: 10px;
}

.page-header h1 {
  font-size: 38px;
  font-weight: 900;
  letter-spacing: -0.03em;
  background: linear-gradient(118deg, #0d2f5a 0%, #0b78d1 56%, #f2a82c 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  background-size: 200% 100%;
  animation: shimmerMove 10s linear infinite;
}
@keyframes shimmerMove {
  0% { background-position: 100% 50%; }
  100% { background-position: -100% 50%; }
}

.page-header p {
  margin-top: 6px;
  color: var(--text2);
  font-size: 14px;
  line-height: 1.6;
}

.panel {
  border-radius: 20px;
  border: 1px solid rgba(11,120,209,.16);
  background:
    radial-gradient(120% 120% at 0% 0%, rgba(11,120,209,.1), transparent 46%),
    radial-gradient(80% 80% at 100% 100%, rgba(242,168,44,.06), transparent 50%),
    linear-gradient(165deg, rgba(255,255,255,.97), rgba(248,252,255,.92));
  box-shadow: 0 20px 48px rgba(13,59,102,.1);
  backdrop-filter: blur(8px);
  position: relative;
  z-index: 1;
}

.select-panel { padding: 22px; }

.panel-head h2 {
  font-size: 22px;
  font-weight: 800;
  background: linear-gradient(118deg, #0d2f5a 0%, #0b78d1 56%, #f2a82c 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin-bottom: 14px;
}

.job-list { list-style: none; display: flex; flex-direction: column; gap: 8px; }

.job-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(255,255,255,.84);
  border: 1px solid rgba(148,163,184,.25);
  cursor: pointer;
  transition: .2s ease;
}

.job-item:hover {
  border-color: rgba(11,120,209,.3);
  box-shadow: 0 10px 20px rgba(11,120,209,.12);
  transform: translateY(-2px);
}

.job-name { flex: 1; font-weight: 700; color: var(--text); font-size: 14px; }
.job-meta { font-size: 12px; color: var(--text3); }

.job-badge.done {
  font-size: 11px;
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(16,185,129,.12);
  color: #047857;
  border: 1px solid rgba(16,185,129,.2);
}

.center-panel { display: flex; justify-content: center; align-items: center; min-height: 45vh; }
.gen-status { text-align: center; display: flex; flex-direction: column; align-items: center; gap: 10px; padding: 12px; }
.gen-status h3 { font-size: 20px; color: #0d4d80; }
.gen-hint { font-size: 13px; color: var(--text2); }

.lesson-layout {
  display: grid;
  grid-template-columns: 1fr 360px;
  gap: 16px;
  align-items: start;
}

.lesson-left {
  padding: 14px;
  border-radius: 16px;
  border: 1px solid rgba(11,120,209,.14);
  background: rgba(255,255,255,.74);
  backdrop-filter: blur(8px);
}

.video-wrap {
  background: #000;
  border-radius: 12px;
  overflow: hidden;
  aspect-ratio: 16/9;
  box-shadow: 0 10px 26px rgba(15,23,42,.22);
}

.lesson-video { width: 100%; height: 100%; display: block; }

.now-playing {
  margin-top: 10px;
  padding: 10px 12px;
  border-radius: 11px;
  font-size: 13px;
  color: var(--text2);
  background: rgba(255,255,255,.72);
  border: 1px solid rgba(11,120,209,.15);
  border-left: 4px solid #0ea5e9;
  display: flex;
  align-items: flex-start;
  gap: 8px;
  min-height: 44px;
}

.now-playing.play { border-left-color: #0f4c81; }
.now-playing.question { border-left-color: #f59e0b; }
.np-icon { flex-shrink: 0; margin-top: 1px; }
.np-text { flex: 1; line-height: 1.45; }

.lesson-progress {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 12px;
}

.progress-bar {
  flex: 1;
  height: 10px;
  background: rgba(148,163,184,.25);
  border-radius: 999px;
  overflow: hidden;
  border: 1px solid rgba(148,163,184,.2);
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #0f4c81, #0ea5e9 60%, #f59e0b);
  border-radius: inherit;
  transition: width .3s ease;
}

.progress-label { font-size: 12px; color: var(--text2); white-space: nowrap; font-weight: 700; }

.lesson-controls {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}

.ctrl-btn {
  flex: 1;
  padding: 10px;
  border-radius: 10px;
  border: 1px solid rgba(148,163,184,.3);
  background: rgba(255,255,255,.9);
  font-size: 13px;
  color: var(--text);
  cursor: pointer;
  transition: .18s ease;
}

.ctrl-btn:hover:not(:disabled) {
  border-color: rgba(11,120,209,.28);
  transform: translateY(-1px);
}

.ctrl-btn:disabled { opacity: .45; cursor: not-allowed; }

.ctrl-btn.primary {
  color: #fff;
  border: none;
  background: linear-gradient(135deg, #0f4c81, #0ea5e9 58%, #f59e0b);
  box-shadow: 0 8px 20px rgba(11,120,209,.25);
  font-weight: 700;
}

.podcast-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 14px;
  flex-wrap: wrap;
}

.podcast-btn { display: flex; align-items: center; gap: 5px; font-size: 13px; }
.podcast-hint { font-size: 12px; color: var(--text2); }

.lesson-right {
  border-radius: 16px;
  border: 1px solid rgba(11,120,209,.14);
  background: rgba(255,255,255,.78);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 150px);
}

.script-header {
  padding: 12px 14px;
  border-bottom: 1px solid rgba(148,163,184,.22);
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}

.script-header h3 {
  font-size: 16px;
  font-weight: 800;
  color: #0d4d80;
}

.job-label { font-size: 11px; color: var(--text3); }

.script-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.script-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 9px 10px;
  border-radius: 10px;
  cursor: pointer;
  transition: .18s ease;
  border: 1px solid transparent;
  background: rgba(255,255,255,.7);
}

.script-item:hover { border-color: rgba(11,120,209,.22); }

.script-item.active {
  background: rgba(11,120,209,.09);
  border-color: rgba(11,120,209,.28);
  box-shadow: inset 0 0 0 1px rgba(11,120,209,.08);
}

.script-item.speak .item-icon { color: #0ea5e9; }
.script-item.play .item-icon { color: #0f4c81; }
.script-item.question .item-icon { color: #f59e0b; }

.item-icon { flex-shrink: 0; font-size: 14px; margin-top: 1px; }

.item-text {
  font-size: 13px;
  color: var(--text2);
  line-height: 1.45;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.sentence-preview {
  font-size: 12px;
  color: var(--text3);
  font-style: italic;
  margin-top: 2px;
}

.empty-hint { color: var(--text3); font-size: 14px; padding: 20px 0; }
.loading-row { display: flex; align-items: center; gap: 6px; color: var(--text3); font-size: 14px; }

.spinner {
  display: inline-block;
  width: 18px;
  height: 18px;
  border: 2px solid rgba(148,163,184,.35);
  border-top-color: #0ea5e9;
  border-radius: 50%;
  animation: spin .7s linear infinite;
}

.spinner.large { width: 36px; height: 36px; border-width: 3px; }
.spinner.small { width: 14px; height: 14px; }

@keyframes spin { to { transform: rotate(360deg); } }

@media (max-width: 900px) {
  .lesson-layout { grid-template-columns: 1fr; }
  .lesson-right { max-height: none; }
}

@media (max-width: 760px) {
  .tutor-page { padding: 20px 14px 72px; }
  .page-header h1 { font-size: 28px; }
  .lesson-controls { flex-wrap: wrap; }
  .ctrl-btn { min-width: 140px; }
}
</style>
