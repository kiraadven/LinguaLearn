<template>
  <div class="jd-page">

    <!-- Sticky top bar -->
    <div v-if="!isProcessing" class="jd-topbar">
      <button class="back-btn" @click="$router.push('/results')">{{ t.detail_back }}</button>
      <div class="jd-title" :title="jobName">{{ jobName }}</div>
      <button v-if="activeTab === 'jingting'" class="toggle-btn" @click="transcriptOpen = !transcriptOpen" :title="transcriptOpen ? t.detail_hide_transcript : t.detail_show_transcript">
        <span>{{ transcriptOpen ? `⟩ ${t.detail_hide_transcript}` : `⟨ ${t.detail_show_transcript}` }}</span>
      </button>
    </div>

    <!-- Loading / error -->
    <div v-if="loading" class="jd-center"><div class="spin">⟳</div><p>{{ t.detail_loading }}</p></div>
    <div v-else-if="!job" class="jd-center"><p>{{ t.detail_not_found }}</p></div>

    <!-- ── Live progress view (running / queued) ── -->
    <div v-else-if="isProcessing" class="jd-progress-view">
      <div class="jd-create-header">
        <h1>{{ t.create_title }}</h1>
        <p>{{ t.create_subtitle }}</p>
      </div>
      <div class="card progress-card">
        <div class="card-title">{{ t.create_progress }}</div>
        <div class="step-bar">
          <template v-for="i in 5" :key="i">
            <div :class="['step-dot', i < liveStep ? 'done' : i === liveStep ? 'active' : '']">{{ i }}</div>
            <div v-if="i < 5" :class="['step-ln', i < liveStep ? 'done' : '']"></div>
          </template>
        </div>
        <div class="cur-step"><span class="pulse-dot"></span><span>{{ liveStepName }}</span></div>
        <div v-if="liveStep >= 5" style="margin-top:14px">
          <div class="pbar-row"><span>{{ t.create_segment_render }}</span><span>{{ liveClipsPct }}%</span></div>
          <div class="pbar-track"><div class="pbar-fill" :style="{width: liveClipsPct+'%', background: 'linear-gradient(90deg,var(--accent),var(--accent2))'}"></div></div>
          <div class="pbar-row" style="margin-top:8px"><span>{{ t.create_video_write }}</span><span>{{ liveWritePct }}%</span></div>
          <div class="pbar-track"><div class="pbar-fill" :style="{width: liveWritePct+'%', background: 'linear-gradient(90deg,var(--accent3,#10b981),var(--accent4,#059669))'}"></div></div>
        </div>
        <div class="log-box" ref="liveLogBox">
          <div v-for="(l, i) in liveLogs" :key="i" :class="['log-line', logClass(l)]">{{ l }}</div>
        </div>
        <div v-if="job.status === 'running'" style="margin-top:14px;text-align:center">
          <button class="btn-ghost cancel-job-btn" @click="cancelJob">{{ t.create_cancel_job }}</button>
        </div>
      </div>
    </div>

    <!-- ── Error view ── -->
    <div v-else-if="job.status === 'error'" class="jd-center">
      <p style="font-size:48px">❌</p>
      <p style="font-weight:700;margin-top:8px">{{ tr('detail_processing_failed', 'Processing failed') }}</p>
      <p v-if="job.error" style="color:var(--err);font-size:13px;margin-top:6px">{{ job.error }}</p>
    </div>

    <div v-else class="jd-body">

      <!-- ── Learning Studio Tabs ── -->
      <div class="studio-tabs">
        <button v-for="tab in studioTabs" :key="tab.id"
          :class="['studio-tab', { active: activeTab === tab.id }]"
          @click="activeTab = tab.id">
          {{ tab.icon }} {{ tab.label }}
        </button>
      </div>

      <!-- ── Tab 1: 精听 ── -->
      <div v-show="activeTab === 'jingting'">

      <!-- ── Main row ── -->
      <div :class="['jd-main', {wide: !transcriptOpen}]">

        <!-- Video column -->
        <div class="jd-video-col">
          <div class="video-wrap">
            <div class="player-surface">
              <video
                ref="videoEl"
                preload="metadata"
                :src="videoSrc"
                class="jd-video"
                @timeupdate="onTimeUpdate"
                @loadedmetadata="onVideoMeta"
                @play="isPlaying = true"
                @pause="isPlaying = false"
                @error="videoError=tr('detail_video_load_failed', 'Video failed to load')"
                @click="togglePlay"
                @dblclick="toggleFullscreen"
              />
              <div class="player-scrim"></div>
              <button class="center-play" :class="{ hidden: isPlaying }" @click="togglePlay" :title="isPlaying ? tr('detail_pause', 'Pause') : tr('detail_play', 'Play')">
                {{ isPlaying ? '❚❚' : '▶' }}
              </button>
              <div v-if="videoError" class="video-err">⚠️ {{ videoError }}</div>

              <div class="player-controls" @click.stop>
                <div class="pc-progress-row">
                  <input
                    class="pc-seek"
                    type="range"
                    min="0"
                    :max="durationSec || 0"
                    step="0.1"
                    :value="currentTimeSec"
                    @input="onSeekInput"
                  />
                </div>

                <div class="pc-main-row">
                  <div class="pc-left-group">
                    <button class="pc-icon-btn primary" @click="togglePlay" :title="isPlaying ? tr('detail_pause', 'Pause') : tr('detail_play', 'Play')">
                      {{ isPlaying ? '❚❚' : '▶' }}
                    </button>
                    <div class="pc-time">{{ fmtClock(currentTimeSec) }} / {{ fmtClock(durationSec) }}</div>
                  </div>

                  <div class="pc-right-group">
                    <div class="pc-volume-wrap">
                      <button class="pc-icon-btn" @click="toggleMute" :title="isMuted ? tr('detail_unmute', 'Unmute') : tr('detail_mute', 'Mute')">{{ volumeIcon }}</button>
                      <input
                        class="pc-volume"
                        type="range"
                        min="0"
                        max="1"
                        step="0.01"
                        :value="isMuted ? 0 : volumeLevel"
                        @input="onVolumeInput"
                      />
                    </div>

                    <div class="pc-menu-wrap" ref="qualityMenuRef">
                      <button class="pc-pill-btn" @click="toggleQualityMenu" :title="tr('detail_quality', 'Quality')">
                        {{ currentQualityLabel }}
                      </button>
                      <div v-if="showQualityMenu" class="pc-menu">
                        <button
                          v-for="opt in qualityOptions"
                          :key="opt.value"
                          :class="['pc-menu-item', { active: selectedQuality === opt.value }]"
                          @click="switchQuality(opt.value)"
                        >
                          {{ opt.label }}
                        </button>
                      </div>
                    </div>

                    <div class="pc-menu-wrap" ref="speedMenuRef">
                      <button class="pc-pill-btn" @click="onSpeedButton" :title="isMember ? tr('detail_speed', 'Playback Speed') : tr('detail_speed_member_only', 'Member-only speed')">
                        {{ isMember ? currentSpeedLabel : tr('detail_speed_short', 'Speed') }}
                      </button>
                      <div v-if="showSpeedMenu && isMember" class="pc-menu">
                        <button
                          v-for="sp in speedOptions"
                          :key="sp"
                          :class="['pc-menu-item', { active: currentSpeed === sp }]"
                          @click="setSpeed(sp)"
                        >
                          {{ sp }}x
                        </button>
                      </div>
                    </div>

                    <button class="pc-pill-btn" @click="onCastClick" :title="isMember ? tr('detail_cast', 'Cast') : tr('detail_cast_member_only', 'Member-only cast')">
                      {{ tr('detail_cast', 'Cast') }}
                    </button>

                    <button class="pc-icon-btn" @click="toggleFullscreen" :title="isFullscreen ? tr('detail_exit_fullscreen', 'Exit Fullscreen') : tr('detail_fullscreen', 'Fullscreen')">
                      {{ isFullscreen ? '🗗' : '⛶' }}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div class="video-meta-row">
            <div class="video-meta-info">
              <div class="vm-name">{{ jobName }}</div>
              <div class="vm-sub">{{ job.result?.source_lang||'?' }} → {{ job.result?.target_lang||'?' }}
                · {{ job.result?.sentences_count||'?' }} {{ t.detail_sentence_count }}</div>
            </div>
            <a :href="`/api/jobs/${jobId}/download/${encodeURIComponent(job.result.full_video)}`"
               download class="dl-chip">{{ t.detail_download_video }}</a>
          </div>
        </div>

        <!-- Transcript panel -->
        <Transition name="panel">
          <div v-if="transcriptOpen" class="jd-transcript-col">
            <div class="tc-header">
              <span class="tc-title">{{ t.detail_transcript }}</span>
              <div v-if="segments.length" class="sync-dot">{{ t.detail_sync_real_time }}</div>
              <div v-else-if="segLoading" style="font-size:11px;color:var(--text3)">{{ t.detail_loading }}</div>
            </div>
            <div class="tc-list" @mouseover="onMdHover" @mouseleave="onMdLeave" @click="onWordClick">
              <div v-if="!segments.length && !segLoading" class="tc-empty">{{ tr('detail_no_transcript', 'No transcript data') }}</div>
              <div v-for="(s, i) in segments" :key="i"
                   :ref="el => segRefs[i] = el"
                   :class="['tc-item', {active: i === activeSeg}]"
                   @click="jumpTo(s.video_start ?? s.start)">
                <button class="tc-ts" @click.stop="jumpTo(s.video_start ?? s.start)">▶ {{ fmtTime(s.video_start ?? s.start) }}</button>
                <div class="tc-texts">
                  <p class="tc-orig" v-html="s._html || s.text"></p>
                </div>
              </div>
            </div>
          </div>
        </Transition>
      </div>

      <!-- ── Learning Notes ── -->
      <div class="jd-notes">
        <div class="notes-hdr">
          <span class="notes-hdr-title">{{ t.detail_notes }}</span>
          <div style="display:flex;gap:8px;flex-wrap:wrap">
            <a v-if="job.result?.markdown && isMember"
               :href="`/api/jobs/${jobId}/download/${encodeURIComponent(job.result.markdown)}`"
               download class="dl-chip">{{ t.detail_download_notes }}</a>
            <button
              v-if="job.result?.markdown && !isMember"
              class="dl-chip dl-chip-btn"
              @click="onClickMemberMarkdown"
            >
              {{ t.detail_download_notes }}
            </button>
            <a v-if="job.result?.markdown"
               :href="`/api/jobs/${jobId}/export-notes-pdf`"
               class="dl-chip">{{ tr('detail_export_pdf', '⬇ Export PDF') }}</a>
          </div>
        </div>
        <div v-if="!markdownHtml" class="md-empty">{{ tr('detail_no_notes', 'No notes yet') }}</div>
        <div v-else class="md-view" ref="mdViewRef" v-html="markdownHtml"
             @click="onWordClick"
             @mouseover="onMdHover" @mouseout="onMdOut" @mouseleave="onMdLeave"></div>
      </div>

      </div><!-- end tab: jingting -->

      <!-- ── Tab 2: AI讲课 ── -->
      <div v-show="activeTab === 'ai_lesson'">
        <AiLessonTab :jobId="jobId" :job="job" :segments="segments" />
      </div>

      <!-- ── Tab 3: 随身听 ── -->
      <div v-show="activeTab === 'podcast'">
        <PodcastTab :jobId="jobId" :segments="segments" />
      </div>

      <!-- ── Tab 4: 测验 ── -->
      <div v-show="activeTab === 'quiz'" class="studio-quiz-panel">
        <div class="studio-quiz-hub">
          <h3>{{ tr('studio_quiz_hub_title', '测验本视频') }}</h3>
          <p>{{ tr('studio_quiz_hub_desc', '测试你对这个视频中词汇、表达和句子听力的掌握程度。') }}</p>
          <button class="btn-primary" @click="goQuiz">{{ tr('studio_quiz_start_btn', '开始测试') }}</button>
        </div>
      </div>

    </div>

    <!-- Dictionary tooltip (teleported to body to avoid z-index/overflow issues) -->
    <Teleport to="body">
      <Transition name="dt">
        <div v-if="tooltip.visible"
             :class="['dict-tooltip', { 'left-side': tooltip.side === 'left' }]"
             :style="tooltipStyle"
             @mouseenter="cancelHide"
             @mouseleave="scheduleHide">
          <div v-if="tooltip.loading" class="dt-loading">
            <span class="dt-spin">⟳</span> {{ tr('dict_loading', 'Loading...') }}
          </div>
          <div v-else-if="tooltip.notFound" class="dt-not-found">
            {{ tr('dict_not_found', 'Not found') }} "{{ tooltip.word }}"
            <p v-if="dictDataNoticeText" class="dt-note-inline dt-note-inline-standalone">{{ dictDataNoticeText }}</p>
          </div>
          <template v-else-if="tooltip.data">
            <div class="dt-head">
              <div class="dt-word-wrap">
                <button
                  v-if="tooltip.data.audio"
                  class="dt-word-btn"
                  @click="playAudio"
                  :title="tr('dict_play_audio', 'Play pronunciation')"
                >
                  {{ tooltip.data.word }}
                </button>
                <span v-else class="dt-word">{{ tooltip.data.word }}</span>
                <span v-if="tooltip.data.phonetic" class="dt-phonetic">{{ tooltip.data.phonetic }}</span>
                <p class="dt-note-inline">{{ dictDataNoticeText }}</p>
              </div>
              <span
                v-if="tooltip.data.provider && String(tooltip.data.provider).toLowerCase() !== 'wiktextract'"
                class="dt-src"
              >
                {{ tooltip.data.provider }}
              </span>
            </div>
            <div v-for="(m, i) in (tooltip.data.meanings || []).slice(0, 3)" :key="i" class="dt-meaning">
              <span v-if="m.pos" class="dt-pos">{{ m.pos }}</span>
              <p class="dt-def">{{ m.definition }}</p>
              <p v-if="tooltip.data.translated_meanings?.[i]" class="dt-def-trans">{{ tooltip.data.translated_meanings[i] }}</p>
              <p v-if="m.example" class="dt-ex">"{{ m.example }}"</p>
              <p v-if="m.synonyms?.length" class="dt-syns">
                {{ tr('dict_synonyms', 'Synonyms') }}: <span v-for="s in m.synonyms" :key="s" class="dt-syn">{{ s }}</span>
              </p>
            </div>
          </template>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, inject } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { marked } from 'marked'
import { apiFetch } from '../composables/useApi.js'
import { useAuth } from '../composables/useAuth.js'
import { useI18n } from '../i18n.js'
import { TRANSLATIONS } from '../i18n/translations.js'
import { wrapDictionaryWords } from '../composables/useDictionaryLookup.js'
import { useJobDetailDictionaryTooltip } from './job-detail/useJobDetailDictionaryTooltip.js'
import AiLessonTab from './job-detail/AiLessonTab.vue'
import PodcastTab from './job-detail/PodcastTab.vue'

const route  = useRoute()
const router = useRouter()
const jobId  = route.params.id
const { user } = useAuth()
const isMember = computed(() => user.value?.membership?.tier === 'member')
const openMembership = inject('openMembership', () => {})
const toast = inject('toast', () => {})
const languagePrefs = inject('languagePrefs', null)
const { t } = useI18n()

function tr(key, fallback = '') {
  return ((t.value?.[key]) ?? fallback) || key
}

const activeTab = ref('jingting') // 'jingting' | 'ai_lesson' | 'podcast' | 'quiz'

const studioTabs = computed(() => [
  { id: 'jingting',  icon: '📺', label: tr('studio_tab_jingting', '精听') },
  { id: 'ai_lesson', icon: '🎙️', label: tr('studio_tab_ai_lesson', 'AI讲课') },
  { id: 'podcast',   icon: '🎧', label: tr('studio_tab_podcast', '随身听') },
  { id: 'quiz',      icon: '✅', label: tr('studio_tab_quiz', '测验') },
])

function goQuiz() {
  router.push({ path: '/quiz', query: { jobId, auto: '1' } })
}

const job        = ref(null)
const loading    = ref(true)
const videoEl    = ref(null)
const videoError = ref('')
const videoSrc   = ref('')
const isPlaying  = ref(false)
const isFullscreen = ref(false)
const currentTimeSec = ref(0)
const durationSec = ref(0)
const selectedQuality = ref('auto')
const currentSpeed = ref(1.0)
const volumeLevel = ref(0.85)
const isMuted = ref(false)
const showQualityMenu = ref(false)
const showSpeedMenu = ref(false)
const qualityMenuRef = ref(null)
const speedMenuRef = ref(null)
const segments   = ref([])
const segLoading = ref(false)
const activeSeg  = ref(-1)
const segRefs    = ref([])
const transcriptOpen = ref(true)
const markdownHtml = ref('')
const isProcessing = computed(() => job.value?.status === 'running' || job.value?.status === 'queued')
const sourceLangForLookup = computed(() =>
  job.value?.result?.source_lang ||
  languagePrefs?.learningLang?.value ||
  localStorage.getItem('ll_learning_lang') ||
  'en'
)
const targetLangForLookup = computed(() =>
  languagePrefs?.familiarLang?.value ||
  localStorage.getItem('ll_familiar_lang') ||
  job.value?.result?.target_lang ||
  'zh'
)
function normalizeDictNoticeLang(lang) {
  const raw = String(lang || '').trim()
  if (!raw) return 'en'
  const low = raw.toLowerCase()
  const norm = low.replace(/_/g, '-')
  if (norm === 'zh' || norm === 'zh-hans' || norm === 'zh-cn' || norm === 'zh-sg') return 'zh-Hans'
  if (norm === 'zh-hant' || norm === 'zh-tw' || norm === 'zh-hk' || norm === 'zh-mo') return 'zh-Hant'
  if (norm.startsWith('zh-hans-')) return 'zh-Hans'
  if (norm.startsWith('zh-hant-')) return 'zh-Hant'
  if (norm.startsWith('ja')) return 'ja'
  if (norm.startsWith('ko')) return 'ko'
  if (norm.startsWith('de')) return 'de'
  if (norm.startsWith('fr')) return 'fr'
  if (norm.startsWith('es')) return 'es'
  if (norm.startsWith('ru')) return 'ru'
  return 'en'
}
const dictDataNoticeText = computed(() => {
  const lang = normalizeDictNoticeLang(targetLangForLookup.value)
  return (
    TRANSLATIONS?.[lang]?.dict_data_notice ||
    t.value?.dict_data_notice ||
    TRANSLATIONS?.en?.dict_data_notice ||
    ''
  )
})
const mdViewRef = ref(null)

const qualityOptions = computed(() => ([
  { value: 'auto', label: tr('detail_quality_auto', 'Auto') },
  { value: '1080', label: '1080p' },
  { value: '720', label: '720p' },
  { value: '360', label: '360p' },
]))
const speedOptions = [0.5, 0.75, 1, 1.25, 1.5, 2]
const currentQualityLabel = computed(
  () => qualityOptions.value.find(o => o.value === selectedQuality.value)?.label || tr('detail_quality_auto', 'Auto')
)
const currentSpeedLabel = computed(() => `${currentSpeed.value.toFixed(2).replace(/\.00$/, '')}x`)
const volumeIcon = computed(() => {
  if (isMuted.value || volumeLevel.value <= 0.001) return '🔇'
  if (volumeLevel.value < 0.5) return '🔉'
  return '🔊'
})

// ── Live progress (for running/queued jobs) ──
const liveStep    = ref(0)
const liveStepName= ref(tr('create_waiting', 'Waiting...'))
const liveClipsPct= ref(0)
const liveWritePct= ref(0)
const liveLogs    = ref([])
const liveLogBox  = ref(null)
let ws = null

function logClass(l) {
  if (l.includes('✅') || l.toLowerCase().includes('success') || l.includes('成功')) return 'ok'
  if (l.includes('❌') || l.toLowerCase().includes('error') || l.includes('错误') || l.includes('失败')) return 'err'
  if (l.includes('⚠️')) return 'warn'
  return ''
}

function onClickMemberMarkdown() {
  openMembership()
}

function connectProgressWS() {
  if (ws) { try { ws.close() } catch {} }
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  ws = new WebSocket(`${proto}://${location.host}/api/ws/${jobId}`)
  ws.onmessage = async (e) => {
    const msg = JSON.parse(e.data)
    switch (msg.type) {
      case 'log':
        liveLogs.value.push(msg.data)
        await nextTick()
        if (liveLogBox.value) liveLogBox.value.scrollTop = liveLogBox.value.scrollHeight
        break
      case 'step':
        liveStep.value = msg.data.step
        liveStepName.value = msg.data.name
        if (job.value) { job.value.step = msg.data.step; job.value.step_name = msg.data.name }
        break
      case 'video_clips': liveClipsPct.value = msg.data.pct || 0; break
      case 'video_write': liveWritePct.value = msg.data.pct || 0; break
      case 'done':
        liveClipsPct.value = 100; liveWritePct.value = 100
        // Reload job to get done state
        try {
          const d = await apiFetch(`/api/jobs/${jobId}`)
          job.value = d
          if (d.status === 'done' && d.result?.full_video) {
            refreshVideoSrc()
            loadSegments()
            if (d.result.markdown) loadMarkdown(d.result.markdown)
          }
        } catch {}
        break
      case 'error':
        if (job.value) job.value.status = 'error'
        break
      case 'cancelled':
        if (job.value) job.value.status = 'cancelled'
        break
      case 'status':
        if (msg.data && job.value) {
          job.value.step = msg.data.step
          job.value.step_name = msg.data.step_name
          liveStep.value = msg.data.step || 0
          liveStepName.value = msg.data.step_name || tr('create_waiting', 'Waiting...')
          liveClipsPct.value = msg.data.video_clips_pct || 0
          liveWritePct.value = msg.data.video_write_pct || 0
        }
        break
    }
  }
  ws.onerror = () => { /* silent */ }
}

async function cancelJob() {
  if (!confirm(tr('create_confirm_cancel', 'Cancel this task?'))) return
  try {
    await fetch(`/api/jobs/${jobId}`, {
      method: 'DELETE',
      headers: { Authorization: 'Bearer ' + localStorage.getItem('ll_token') }
    })
    if (job.value) job.value.status = 'cancelled'
  } catch {}
}

const jobName = computed(() =>
  job.value?.name || job.value?.video_filename || jobId.slice(0,12)
)

function buildStreamUrl(quality = selectedQuality.value) {
  const f = job.value?.result?.full_video
  if (!f) return ''
  const q = encodeURIComponent(quality || 'auto')
  return `/api/jobs/${jobId}/stream/${encodeURIComponent(f)}?quality=${q}`
}

function refreshVideoSrc() {
  videoSrc.value = buildStreamUrl(selectedQuality.value)
}

function togglePlay() {
  const v = videoEl.value
  if (!v) return
  if (v.paused) v.play().catch(() => {})
  else v.pause()
}

function onVideoMeta() {
  const v = videoEl.value
  if (!v) return
  durationSec.value = Number.isFinite(v.duration) ? v.duration : 0
  v.volume = volumeLevel.value
  v.muted = isMuted.value
  if (isMember.value) {
    v.playbackRate = currentSpeed.value
  } else {
    v.playbackRate = 1
    currentSpeed.value = 1
  }
}

function onSeekInput(e) {
  const v = videoEl.value
  if (!v) return
  const t = Number(e?.target?.value || 0)
  v.currentTime = t
  currentTimeSec.value = t
}

function seekRelative(deltaSec) {
  const v = videoEl.value
  if (!v) return
  const duration = Number.isFinite(v.duration) ? v.duration : (durationSec.value || 1e9)
  const next = Math.max(0, Math.min(duration, (v.currentTime || 0) + deltaSec))
  v.currentTime = next
  currentTimeSec.value = next
}

function fmtClock(sec) {
  const n = Math.max(0, Math.floor(sec || 0))
  const h = Math.floor(n / 3600)
  const m = Math.floor((n % 3600) / 60)
  const s = n % 60
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  return `${m}:${String(s).padStart(2, '0')}`
}

function toggleQualityMenu() {
  showQualityMenu.value = !showQualityMenu.value
  if (showQualityMenu.value) showSpeedMenu.value = false
}

function onSpeedButton() {
  if (!isMember.value) {
    toast(tr('detail_speed_member_only', 'Member-only speed'), 'warn')
    openMembership()
    return
  }
  showSpeedMenu.value = !showSpeedMenu.value
  if (showSpeedMenu.value) showQualityMenu.value = false
}

function setSpeed(speed) {
  if (!isMember.value) {
    toast(tr('detail_speed_member_only', 'Member-only speed'), 'warn')
    openMembership()
    return
  }
  currentSpeed.value = speed
  if (videoEl.value) videoEl.value.playbackRate = speed
  showSpeedMenu.value = false
}

function onVolumeInput(e) {
  const val = Number(e?.target?.value || 0)
  volumeLevel.value = Math.max(0, Math.min(1, val))
  isMuted.value = volumeLevel.value <= 0.001
  const v = videoEl.value
  if (!v) return
  v.muted = isMuted.value
  v.volume = volumeLevel.value
}

function toggleMute() {
  const v = videoEl.value
  isMuted.value = !isMuted.value
  if (v) {
    v.muted = isMuted.value
    if (!isMuted.value) v.volume = volumeLevel.value
  }
}

function switchQuality(quality) {
  showQualityMenu.value = false
  if (selectedQuality.value === quality) return

  const v = videoEl.value
  const current = v?.currentTime || 0
  const wasPlaying = !!(v && !v.paused)

  selectedQuality.value = quality
  refreshVideoSrc()

  if (!v) return
  const restore = () => {
    try {
      v.currentTime = Math.max(0, Math.min(current, Number.isFinite(v.duration) ? v.duration : current))
    } catch {}
    if (isMember.value) v.playbackRate = currentSpeed.value
    if (wasPlaying) v.play().catch(() => {})
  }
  v.addEventListener('loadedmetadata', restore, { once: true })
  v.load()
}

async function onCastClick() {
  if (!isMember.value) {
    toast(tr('detail_cast_member_only', 'Member-only cast'), 'warn')
    openMembership()
    return
  }
  const v = videoEl.value
  if (!v) return
  try {
    if (v.remote && typeof v.remote.prompt === 'function') {
      await v.remote.prompt()
      return
    }
    if (typeof v.webkitShowPlaybackTargetPicker === 'function') {
      v.webkitShowPlaybackTargetPicker()
      return
    }
    toast(tr('detail_cast_not_supported', 'Casting is not supported in this browser'), 'warn')
  } catch {
    toast(tr('detail_cast_cancelled', 'Casting not connected or cancelled'), 'warn')
  }
}

function toggleFullscreen() {
  const container = videoEl.value?.closest('.video-wrap')
  if (!container) return
  if (!document.fullscreenElement) {
    container.requestFullscreen?.().catch(() => {})
  } else {
    document.exitFullscreen?.().catch(() => {})
  }
}

function handleDocClick(e) {
  const t = e.target
  if (qualityMenuRef.value && !qualityMenuRef.value.contains(t)) showQualityMenu.value = false
  if (speedMenuRef.value && !speedMenuRef.value.contains(t)) showSpeedMenu.value = false
}

function handleFullscreenChange() {
  const container = videoEl.value?.closest('.video-wrap')
  isFullscreen.value = !!container && document.fullscreenElement === container
}

function handlePlayerHotkeys(e) {
  const active = document.activeElement
  if (active && ['INPUT', 'TEXTAREA', 'SELECT'].includes(active.tagName)) return
  if (!videoEl.value || !job.value || job.value.status !== 'done') return

  const key = String(e.key || '').toLowerCase()
  if (key === ' ' || key === 'k') {
    e.preventDefault()
    togglePlay()
  } else if (key === 'arrowleft' || key === 'j') {
    e.preventDefault()
    seekRelative(-5)
  } else if (key === 'arrowright' || key === 'l') {
    e.preventDefault()
    seekRelative(5)
  } else if (key === 'f') {
    e.preventDefault()
    toggleFullscreen()
  } else if (key === 'm') {
    e.preventDefault()
    toggleMute()
  }
}

onMounted(async () => {
  document.addEventListener('click', handleDocClick)
  document.addEventListener('fullscreenchange', handleFullscreenChange)
  document.addEventListener('keydown', handlePlayerHotkeys)
  try {
    const d = await apiFetch(`/api/jobs/${jobId}`)
    job.value = d
    if (d.status === 'done' && d.result?.full_video) {
      refreshVideoSrc()
      loadSegments()
      if (d.result.markdown) loadMarkdown(d.result.markdown)
    } else if (d.status === 'running' || d.status === 'queued') {
      liveStep.value = d.step || 0
      liveStepName.value = d.step_name || tr('create_waiting', 'Waiting...')
      liveClipsPct.value = d.video_clips_pct || 0
      liveWritePct.value = d.video_write_pct || 0
      connectProgressWS()
    }
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
})

onUnmounted(() => {
  if (ws) { try { ws.close() } catch {} }
  document.removeEventListener('click', handleDocClick)
  document.removeEventListener('fullscreenchange', handleFullscreenChange)
  document.removeEventListener('keydown', handlePlayerHotkeys)
})

async function loadSegments() {
  segLoading.value = true
  try {
    const d = await apiFetch(`/api/jobs/${jobId}/segments?_ts=${Date.now()}`)
    const list = Array.isArray(d) ? d : []
    segments.value = list.map(s => ({
      ...s,
      _html: wrapDictionaryWords(`<span>${s.text || ''}</span>`, sourceLangForLookup.value).replace(/^<span>|<\/span>$/g, ''),
    }))
  } catch { segments.value = [] }
  finally { segLoading.value = false }
}

async function loadMarkdown(mdFile) {
  try {
    const d = await apiFetch(`/api/jobs/${jobId}/preview/${encodeURIComponent(mdFile)}`)
    const text = d.content || ''
    let html = marked.parse(text)
    if (html instanceof Promise) html = await html
    markdownHtml.value = wrapDictionaryWords(html, sourceLangForLookup.value)
  } catch (e) {
    console.error('loadMarkdown error:', e)
  }
}

// ── Dictionary tooltip ──────────────────────────────────────────────────────
const {
  tooltip,
  tooltipStyle,
  onMdHover,
  onMdOut,
  onMdLeave,
  onWordClick,
  cancelHide,
  scheduleHide,
  playAudio,
} = useJobDetailDictionaryTooltip({
  sourceLangForLookup,
  targetLangForLookup,
  mdViewRef,
  apiFetch,
})

// ── Video sync ──────────────────────────────────────────────────────────────
function onTimeUpdate() {
  if (!videoEl.value) return
  const ct = videoEl.value.currentTime
  currentTimeSec.value = ct
  if (Number.isFinite(videoEl.value.duration)) durationSec.value = videoEl.value.duration
  if (!segments.value.length) return
  let idx = -1
  for (let i = 0; i < segments.value.length; i++) {
    const s = segments.value[i]
    const vStart = s.seg_start ?? s.start
    const vEnd   = s.seg_end   ?? s.end
    if (ct >= vStart && ct < vEnd) { idx = i; break }
  }
  if (idx !== activeSeg.value) {
    activeSeg.value = idx
    if (idx >= 0) scrollToSeg(idx)
  }
}

function scrollToSeg(idx) {
  const el = segRefs.value[idx]
  el?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
}

function jumpTo(t) {
  if (!videoEl.value) return
  videoEl.value.currentTime = t
  currentTimeSec.value = t
  videoEl.value.play()
}

function fmtTime(sec) {
  const m = Math.floor(sec / 60), s2 = Math.floor(sec % 60)
  return `${m}:${String(s2).padStart(2, '0')}`
}
</script>

<style scoped src="./job-detail/JobDetail.css"></style>
