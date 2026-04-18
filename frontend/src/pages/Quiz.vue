<template>
  <div class="quiz-page page-inner">
    <section v-if="!isLoggedIn" class="panel empty">
      <div class="empty-icon">🔒</div>
      <p>{{ tr('create_login_required', 'Please log in first') }}</p>
      <button class="btn primary" @click="openAuth?.()">{{ tr('nav_login_register', 'Login / Register') }}</button>
    </section>

    <template v-else>
      <section v-if="phase !== 'exam'" class="module-hub">
        <button class="module-card book" @click="openMasteredBoard">
          <span class="module-icon">📚</span>
          <span class="module-title">{{ tr('quiz_mastered_board', 'Mastered Notebook') }}</span>
          <span class="module-desc">{{ tr('quiz_module_mastered_desc', 'Manage mastered words, expressions and sentences') }}</span>
        </button>
        <button class="module-card global" @click="openGlobalSetup">
          <span class="module-icon">🌐</span>
          <span class="module-title">{{ tr('quiz_global_review', 'Global Review') }}</span>
          <span class="module-desc">{{ tr('quiz_module_global_desc', 'Practice across all completed videos with daily limits') }}</span>
        </button>
      </section>

      <section v-if="phase === 'select'" class="panel select-panel">
        <header class="panel-head">
          <div>
            <h2>{{ tr('quiz_select_video', '选择一个已完成的视频') }}</h2>
            <p>{{ tr('quiz_select_hint', '或直接进入全局复习（跨视频）') }}</p>
          </div>
        </header>

        <div v-if="jobsLoading" class="empty">{{ tr('results_loading', 'Loading...') }}</div>
        <div v-else-if="doneJobs.length === 0" class="empty">
          <div class="empty-icon">📭</div>
          <p>{{ tr('quiz_no_completed_videos', 'No completed videos yet') }}</p>
          <button class="btn primary" @click="$router.push('/create')">{{ tr('nav_create', 'Create Video') }}</button>
        </div>
        <div v-else class="job-grid">
          <article v-for="job in doneJobs" :key="job.id" class="job-card" @click="openJobSetup(job)">
            <div class="job-main">
              <h3>{{ job.name || job.video_filename || job.id.slice(0, 12) }}</h3>
              <p>{{ (job.source_lang || '?') + ' → ' + (job.target_lang || '?') }}</p>
            </div>
            <span class="job-date">{{ fmtDate(job.created_at) }}</span>
          </article>
        </div>
      </section>

      <section v-else-if="phase === 'setup'" class="panel setup-panel">
        <div class="setup-header">
          <h2>
            {{ reviewScope === 'global' ? tr('quiz_global_review', '全局复习') : (selectedJob?.name || selectedJob?.video_filename || selectedJob?.id?.slice(0, 12) || tr('quiz_single_video', '单视频复习')) }}
          </h2>
          <p>{{ tr('quiz_setup_tip', '勾选要测内容，系统会混合打乱顺序进行检测') }}</p>
        </div>

        <div class="type-grid">
          <label class="type-card">
            <input type="checkbox" v-model="includeTypes.word">
            <span>{{ tr('quiz_type_word', '单词') }}</span>
          </label>
          <label class="type-card">
            <input type="checkbox" v-model="includeTypes.expression">
            <span>{{ tr('quiz_type_expression', '词组') }}</span>
          </label>
          <label class="type-card">
            <input type="checkbox" v-model="includeTypes.sentence">
            <span>{{ tr('quiz_sentence_mode', '句子听力') }}</span>
          </label>
        </div>

        <div class="field-row">
          <label>{{ tr('quiz_requested_count', '本次题量') }}</label>
          <input class="num-input" type="number" min="1" max="500" v-model.number="requestedCount">
        </div>

        <div v-if="reviewScope === 'global'" class="global-meta">
          <div class="quota-row">
            <span>{{ tr('quiz_today_reviewed', '今日已复习') }}: <strong>{{ globalSettings.reviewed_today }}</strong></span>
            <span>{{ tr('quiz_today_remaining', '今日剩余') }}: <strong>{{ globalSettings.remaining_today }}</strong></span>
          </div>
          <div class="quota-row">
            <label>{{ tr('quiz_daily_max', '每日最大复习量') }}</label>
            <input class="num-input" type="number" min="1" max="1000" v-model.number="globalSettings.daily_global_max">
            <button class="btn ghost" :disabled="globalSettingsSaving" @click="saveGlobalSettings">
              {{ globalSettingsSaving ? tr('results_loading', 'Loading...') : tr('quiz_save', '保存') }}
            </button>
          </div>
        </div>

        <div class="setup-actions">
          <button class="btn ghost" @click="goToSelect">{{ tr('quiz_cancel', '取消') }}</button>
          <button class="btn primary" :disabled="sessionStarting" @click="startSession">
            {{ sessionStarting ? tr('results_loading', 'Loading...') : tr('quiz_start', '开始测试') }}
          </button>
        </div>
      </section>

      <section v-else-if="phase === 'exam'" class="panel exam-panel">
        <div class="exam-head">
          <h2>{{ examTitle }}</h2>
          <span>{{ currentQuestionIndex + 1 }} / {{ queue.length }}</span>
        </div>

        <div class="progress-wrap">
          <div class="progress-inner" :style="{ width: progressPct + '%' }"></div>
        </div>

        <article v-if="currentQuestion" class="question-card">
          <header class="question-top">
            <span class="type-chip" :class="currentQuestion.item_type">{{ itemTypeLabel(currentQuestion.item_type) }}</span>
            <button class="btn warm" :disabled="grading" @click="markCurrentAsMastered">
              {{ tr('quiz_add_mastered_now', '加入熟词本') }}
            </button>
          </header>

          <div v-if="currentQuestion.item_type !== 'sentence'" class="spelling-body">
            <p class="prompt-text">{{ currentQuestion.prompt_text || tr('quiz_spell_prompt', '请拼写') }}</p>
            <div class="spelling-grid">
              <template v-for="(part, pi) in spellingLayout" :key="`sp_${pi}`">
                <span v-if="part.kind === 'sep'" :class="['sp-sep', { space: part.char === ' ' }]">{{ part.char === ' ' ? '' : part.char }}</span>
                <input
                  v-else
                  :ref="(el) => setSpellingRef(part.slotIndex, el)"
                  class="cell-input"
                  :value="spellingChars[part.slotIndex] || ''"
                  :disabled="grading"
                  maxlength="1"
                  @input="onSpellingInput(part.slotIndex, $event.target.value)"
                  @keydown="onSpellingKeydown(part.slotIndex, $event)"
                >
              </template>
            </div>
          </div>

          <div v-else class="sentence-body">
            <div class="audio-row">
              <button class="btn ghost" :disabled="!currentQuestion.audio_url" @click="toggleSentenceAudio">
                {{ audioPlaying ? tr('quiz_audio_playing', '播放中...') : tr('quiz_play_original_audio', '播放原声') }}
              </button>
              <span class="audio-note">{{ currentQuestion.job_name || '' }}</span>
            </div>

            <div class="cloze-wrap">
              <template v-for="(seg, si) in currentQuestion.masked_segments || []" :key="`seg_${si}`">
                <span v-if="seg.type === 'text'" class="seg-text">{{ seg.text }}</span>
                <span v-else class="blank-word">
                  <input
                    v-for="(_, ci) in sentenceLens[seg.blank_order] || []"
                    :key="`b_${seg.blank_order}_${ci}`"
                    :ref="(el) => setBlankRef(seg.blank_order, ci, el)"
                    class="cell-input blank-cell"
                    :disabled="grading"
                    maxlength="1"
                    :value="sentenceInputs[seg.blank_order]?.[ci] || ''"
                    @input="onSentenceCellInput(seg.blank_order, ci, $event.target.value)"
                    @keydown="onSentenceCellKeydown(seg.blank_order, ci, $event)"
                  >
                </span>
              </template>
            </div>
          </div>

          <footer class="submit-row">
            <button class="btn primary" :disabled="grading || !canSubmitCurrent" @click="submitCurrentAnswer">
              {{ grading ? tr('results_loading', 'Loading...') : tr('quiz_confirm', '确认') }}
            </button>
          </footer>
        </article>

        <audio ref="sentenceAudioEl" class="hidden-audio" @ended="audioPlaying = false" @pause="audioPlaying = false"></audio>
      </section>

      <section v-else-if="phase === 'result'" class="panel result-panel">
        <div class="score-head">
          <div class="score-value">{{ examScore }}</div>
          <div class="score-label">{{ tr('quiz_score_unit', '分') }}</div>
        </div>

        <div class="result-stats">
          <div class="stat">
            <strong>{{ gradedCount }}</strong>
            <span>{{ tr('quiz_total_count', '评分题') }}</span>
          </div>
          <div class="stat">
            <strong>{{ passedCount }}</strong>
            <span>{{ tr('quiz_correct_count', '通过') }}</span>
          </div>
          <div class="stat">
            <strong>{{ failedCount }}</strong>
            <span>{{ tr('quiz_wrong_count', '未通过') }}</span>
          </div>
          <div class="stat">
            <strong>{{ masteredSkipCount }}</strong>
            <span>{{ tr('quiz_mastered_skip', '熟悉跳过') }}</span>
          </div>
        </div>

        <article v-if="reviewScope === 'job'" class="global-hint-card">
          <h3>{{ tr('quiz_after_job_title', '本视频复习完成') }}</h3>
          <p>{{ tr('quiz_after_job_desc', '是否继续进入全局复习？系统会从你所有视频中智能推荐今日应复习内容。') }}</p>
          <button class="btn primary" @click="openGlobalSetupFromResult">{{ tr('quiz_go_global_now', '进入全局复习') }}</button>
        </article>

        <div class="setup-actions">
          <button class="btn ghost" @click="goToSelect">{{ tr('quiz_back_to_select', '返回选择') }}</button>
          <button class="btn primary" @click="openMasteredBoard">{{ tr('quiz_mastered_board', '管理熟词本') }}</button>
        </div>

        <div class="record-list">
          <article v-for="(rec, idx) in examRecords" :key="`rec_${idx}`" class="record-item" :class="rec.kind">
            <div class="record-top">
              <span class="type-chip" :class="rec.item_type">{{ itemTypeLabel(rec.item_type) }}</span>
              <span v-if="rec.kind === 'graded'" class="record-score">{{ rec.score }}</span>
              <span v-else class="record-score">{{ tr('quiz_mastered_skip_tag', '熟悉跳过') }}</span>
            </div>

            <p class="record-main">{{ rec.prompt || rec.display_text }}</p>

            <p class="record-sub" v-if="rec.kind === 'graded'">
              {{ tr('quiz_expected', '标准答案') }}: {{ rec.expected }}
              <span v-if="rec.user"> · {{ tr('quiz_col_user_answer', '你的答案') }}: {{ rec.user }}</span>
            </p>

            <div class="record-actions" v-if="!rec.masteredActionDone">
              <button class="btn warm mini" @click="markRecordMastered(rec)">
                {{ tr('quiz_add_mastered', '加入熟词本') }}
              </button>
            </div>
          </article>
        </div>
      </section>

      <section v-else-if="phase === 'mastered'" class="panel mastered-panel">
        <div class="mastered-head">
          <h2>{{ tr('quiz_mastered_board', '熟词本管理') }}</h2>
          <div class="mastered-tools">
            <input class="answer-input" v-model="masteredQ" :placeholder="tr('quiz_search', '搜索内容')" @keyup.enter="loadMasteredItems">
            <select class="type-select" v-model="masteredType" @change="loadMasteredItems">
              <option value="all">{{ tr('quiz_type_all', '全部') }}</option>
              <option value="word">{{ tr('quiz_type_word', '单词') }}</option>
              <option value="expression">{{ tr('quiz_type_expression', '词组') }}</option>
              <option value="sentence">{{ tr('quiz_sentence_mode', '句子') }}</option>
            </select>
            <button class="btn ghost" @click="loadMasteredItems">{{ tr('quiz_search_btn', '查询') }}</button>
          </div>
        </div>

        <div v-if="masteredLoading" class="empty">{{ tr('results_loading', 'Loading...') }}</div>
        <div v-else-if="masteredItems.length === 0" class="empty">{{ tr('quiz_mastered_empty', '熟词本为空') }}</div>
        <div v-else class="mastered-grid">
          <article v-for="item in masteredItems" :key="item.id" class="mastered-card">
            <div class="record-top">
              <span class="type-chip" :class="item.item_type">{{ itemTypeLabel(item.item_type) }}</span>
            </div>
            <p class="record-main">{{ item.display_text }}</p>
            <p class="record-sub" v-if="item.prompt_text">{{ item.prompt_text }}</p>
            <button class="btn ghost mini" @click="unmasterItem(item)">{{ tr('quiz_unmaster', '取消熟悉') }}</button>
          </article>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, inject, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAuth } from '../composables/useAuth.js'
import { apiFetch } from '../composables/useApi.js'
import { useI18n } from '../i18n.js'

const route = useRoute()

const { isLoggedIn } = useAuth()
const openAuth = inject('openAuth')
const toast = inject('toast')
const { t, uiLang } = useI18n()

function tr(key, fallback = '') {
  return t.value?.[key] || fallback || key
}

const phase = ref('select')

const jobsLoading = ref(false)
const doneJobs = ref([])
const selectedJob = ref(null)
const reviewScope = ref('job')

const includeTypes = reactive({
  word: true,
  expression: true,
  sentence: true,
})
const requestedCount = ref(40)

const globalSettings = reactive({
  daily_global_max: 100,
  reviewed_today: 0,
  remaining_today: 100,
})
const globalSettingsSaving = ref(false)

const queue = ref([])
const currentQuestionIndex = ref(0)
const sessionStarting = ref(false)
const grading = ref(false)

const spellingLayout = ref([])
const spellingChars = ref([])
const spellingRefs = ref([])

const sentenceInputs = ref([])
const sentenceLens = ref([])
const blankRefs = ref([])

const sentenceAudioEl = ref(null)
const audioPlaying = ref(false)
const itemStartedAt = ref(0)

const examRecords = ref([])
const masteredSkipCount = ref(0)

const masteredLoading = ref(false)
const masteredItems = ref([])
const masteredQ = ref('')
const masteredType = ref('all')

const currentQuestion = computed(() => queue.value[currentQuestionIndex.value] || null)
const progressPct = computed(() => {
  if (!queue.value.length) return 0
  return Math.round((currentQuestionIndex.value / queue.value.length) * 100)
})

const examTitle = computed(() => {
  if (reviewScope.value === 'global') return tr('quiz_global_review', '全局复习')
  const j = selectedJob.value
  return j?.name || j?.video_filename || j?.id?.slice(0, 12) || tr('quiz_single_video', '单视频复习')
})

const canSubmitCurrent = computed(() => {
  const q = currentQuestion.value
  if (!q) return false
  if (q.item_type === 'sentence') {
    return sentenceInputs.value.some(chars => chars.some(ch => String(ch || '').trim()))
  }
  return spellingChars.value.some(ch => String(ch || '').trim())
})

const gradedRecords = computed(() => examRecords.value.filter(r => r.kind === 'graded'))
const gradedCount = computed(() => gradedRecords.value.length)
const passedCount = computed(() => gradedRecords.value.filter(r => r.passed).length)
const failedCount = computed(() => gradedCount.value - passedCount.value)
const examScore = computed(() => {
  if (!gradedCount.value) return 0
  const total = gradedRecords.value.reduce((sum, r) => sum + (Number(r.score) || 0), 0)
  return Math.round(total / gradedCount.value)
})

function fmtDate(v) {
  if (!v) return '-'
  try {
    return new Date(v).toLocaleDateString(uiLang.value || 'en-US')
  } catch {
    return String(v).slice(0, 10)
  }
}

function itemTypeLabel(itemType) {
  if (itemType === 'word') return tr('quiz_type_word', '单词')
  if (itemType === 'expression') return tr('quiz_type_expression', '词组')
  if (itemType === 'sentence') return tr('quiz_sentence_mode', '句子听力')
  return itemType || '-'
}

function normalizeTypeParam(v) {
  if (!v || v === 'all') return ''
  return v
}

function isFillableChar(ch) {
  return /[A-Za-zÀ-ÖØ-öø-ÿ0-9\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]/.test(ch || '')
}

function toSingleChar(v) {
  const list = [...String(v || '').replace(/\s+/g, '')]
  return list.length ? list[list.length - 1] : ''
}

function initSpellingLayout(text) {
  const layout = []
  let slotIndex = 0
  for (const ch of [...String(text || '')]) {
    if (isFillableChar(ch)) {
      layout.push({ kind: 'slot', slotIndex, char: ch })
      slotIndex += 1
    } else {
      layout.push({ kind: 'sep', char: ch })
    }
  }
  spellingLayout.value = layout
  spellingChars.value = Array.from({ length: slotIndex }, () => '')
  spellingRefs.value = []
}

function getSpellingAnswerText() {
  let out = ''
  for (const p of spellingLayout.value) {
    if (p.kind === 'sep') {
      out += p.char
    } else {
      out += (spellingChars.value[p.slotIndex] || '')
    }
  }
  return out.trim()
}

function setSpellingRef(slotIndex, el) {
  if (!el) return
  spellingRefs.value[slotIndex] = el
}

function focusSpellingSlot(slotIndex) {
  const idx = Number(slotIndex)
  if (Number.isNaN(idx) || idx < 0) return
  const el = spellingRefs.value[idx]
  if (el?.focus) {
    el.focus()
    if (el.select) el.select()
  }
}

function onSpellingInput(slotIndex, value) {
  const ch = toSingleChar(value)
  const next = [...spellingChars.value]
  next[slotIndex] = ch
  spellingChars.value = next
  if (ch && slotIndex + 1 < next.length) {
    focusSpellingSlot(slotIndex + 1)
  }
}

function onSpellingKeydown(slotIndex, event) {
  if (event.key === 'ArrowLeft') {
    event.preventDefault()
    focusSpellingSlot(slotIndex - 1)
    return
  }
  if (event.key === 'ArrowRight') {
    event.preventDefault()
    focusSpellingSlot(slotIndex + 1)
    return
  }
  if (event.key === 'Backspace') {
    event.preventDefault()
    const next = [...spellingChars.value]
    if (next[slotIndex]) {
      next[slotIndex] = ''
      spellingChars.value = next
      return
    }
    if (slotIndex > 0) {
      next[slotIndex - 1] = ''
      spellingChars.value = next
      focusSpellingSlot(slotIndex - 1)
    }
    return
  }
  if (event.key === 'Enter') {
    event.preventDefault()
    submitCurrentAnswer()
  }
}

function initSentenceInputs(item) {
  const blankCount = Number(item?.blank_count || 0)
  const lens = Array.from({ length: blankCount }, () => 4)

  for (const seg of item?.masked_segments || []) {
    if (seg?.type !== 'blank') continue
    const bi = Number(seg.blank_order)
    if (Number.isNaN(bi) || bi < 0 || bi >= blankCount) continue
    const len = String(seg.placeholder || '').length
    lens[bi] = Math.max(1, Math.min(14, len || 4))
  }

  sentenceLens.value = lens.map(v => Array.from({ length: v }, (_, i) => i))
  sentenceInputs.value = lens.map(v => Array.from({ length: v }, () => ''))
  blankRefs.value = lens.map(() => [])
}

function setBlankRef(blankIndex, charIndex, el) {
  const bi = Number(blankIndex)
  const ci = Number(charIndex)
  if (Number.isNaN(bi) || Number.isNaN(ci) || !el) return
  if (!blankRefs.value[bi]) blankRefs.value[bi] = []
  blankRefs.value[bi][ci] = el
}

function focusBlankCell(blankIndex, charIndex = 0) {
  const bi = Number(blankIndex)
  const ci = Number(charIndex)
  if (Number.isNaN(bi) || Number.isNaN(ci) || bi < 0) return
  const row = blankRefs.value[bi]
  if (!row || !row.length) return
  const target = row[Math.max(0, Math.min(ci, row.length - 1))]
  if (target?.focus) {
    target.focus()
    if (target.select) target.select()
  }
}

function onSentenceCellInput(blankIndex, charIndex, value) {
  const bi = Number(blankIndex)
  const ci = Number(charIndex)
  if (Number.isNaN(bi) || Number.isNaN(ci) || bi < 0 || ci < 0) return

  const ch = toSingleChar(value)
  const next = sentenceInputs.value.map(row => [...row])
  next[bi][ci] = ch
  sentenceInputs.value = next

  if (ch) {
    if (ci + 1 < next[bi].length) {
      focusBlankCell(bi, ci + 1)
    } else {
      focusBlankCell(bi + 1, 0)
    }
  }
}

function onSentenceCellKeydown(blankIndex, charIndex, event) {
  const bi = Number(blankIndex)
  const ci = Number(charIndex)
  if (Number.isNaN(bi) || Number.isNaN(ci)) return

  if (event.key === 'ArrowLeft') {
    event.preventDefault()
    focusBlankCell(bi - 1, ci)
    return
  }
  if (event.key === 'ArrowRight') {
    event.preventDefault()
    focusBlankCell(bi + 1, ci)
    return
  }
  if (event.key === 'Backspace') {
    event.preventDefault()
    const next = sentenceInputs.value.map(row => [...row])
    if (next[bi]?.[ci]) {
      next[bi][ci] = ''
      sentenceInputs.value = next
      return
    }
    if (ci > 0) {
      next[bi][ci - 1] = ''
      sentenceInputs.value = next
      focusBlankCell(bi, ci - 1)
    } else {
      focusBlankCell(bi - 1, 0)
    }
    return
  }
  if (event.key === 'Enter') {
    event.preventDefault()
    submitCurrentAnswer()
  }
}

function collectSentenceAnswers() {
  return sentenceInputs.value.map(chars => chars.join('').trim())
}

async function loadJobs() {
  if (!isLoggedIn.value) return
  jobsLoading.value = true
  try {
    const resp = await apiFetch('/api/jobs')
    doneJobs.value = (resp.jobs || [])
      .filter(j => j.status === 'done')
      .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
  } catch (e) {
    toast?.(`${tr('results_load_failed', 'Load failed')}: ${e.message}`, 'err')
  } finally {
    jobsLoading.value = false
  }
}

async function loadGlobalSettings() {
  if (!isLoggedIn.value) return
  try {
    const resp = await apiFetch('/api/review/settings')
    globalSettings.daily_global_max = Number(resp.daily_global_max || 100)
    globalSettings.reviewed_today = Number(resp.reviewed_today || 0)
    globalSettings.remaining_today = Number(resp.remaining_today || 0)
  } catch (e) {
    toast?.(`${tr('quiz_load_failed', 'Failed to load quiz data')}: ${e.message}`, 'err')
  }
}

async function saveGlobalSettings() {
  globalSettingsSaving.value = true
  try {
    const resp = await apiFetch('/api/review/settings', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ daily_global_max: Number(globalSettings.daily_global_max || 100) }),
    })
    globalSettings.daily_global_max = Number(resp.daily_global_max || globalSettings.daily_global_max)
    globalSettings.reviewed_today = Number(resp.reviewed_today || 0)
    globalSettings.remaining_today = Number(resp.remaining_today || 0)
    toast?.(tr('quiz_save_ok', '保存成功'), 'ok')
  } catch (e) {
    toast?.(`${tr('quiz_save_fail', '保存失败')}: ${e.message}`, 'err')
  } finally {
    globalSettingsSaving.value = false
  }
}

function resetExamState() {
  queue.value = []
  currentQuestionIndex.value = 0
  spellingLayout.value = []
  spellingChars.value = []
  spellingRefs.value = []
  sentenceInputs.value = []
  sentenceLens.value = []
  blankRefs.value = []
  examRecords.value = []
  masteredSkipCount.value = 0
  stopSentenceAudio()
}

function openJobSetup(job) {
  selectedJob.value = job
  reviewScope.value = 'job'
  requestedCount.value = 40
  includeTypes.word = true
  includeTypes.expression = true
  includeTypes.sentence = true
  phase.value = 'setup'
}

async function openGlobalSetup() {
  selectedJob.value = null
  reviewScope.value = 'global'
  requestedCount.value = 40
  includeTypes.word = true
  includeTypes.expression = true
  includeTypes.sentence = true
  await loadGlobalSettings()
  phase.value = 'setup'
}

async function openGlobalSetupFromResult() {
  await openGlobalSetup()
  toast?.(tr('quiz_enter_global_tip', '已切换到全局复习设置'), 'ok')
}

function goToSelect() {
  resetExamState()
  phase.value = 'select'
}

async function startSession() {
  if (!includeTypes.word && !includeTypes.expression && !includeTypes.sentence) {
    toast?.(tr('quiz_need_type', '请至少选择一种题型'), 'err')
    return
  }

  if (reviewScope.value === 'job' && !selectedJob.value?.id) {
    toast?.(tr('quiz_need_job', '请选择一个视频'), 'err')
    return
  }

  sessionStarting.value = true
  try {
    const payload = {
      scope: reviewScope.value,
      include_types: {
        word: !!includeTypes.word,
        expression: !!includeTypes.expression,
        sentence: !!includeTypes.sentence,
      },
      requested_count: Number(requestedCount.value || 40),
    }
    if (reviewScope.value === 'job') payload.job_id = selectedJob.value.id

    const resp = await apiFetch('/api/review/session', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })

    queue.value = resp.items || []
    currentQuestionIndex.value = 0
    examRecords.value = []
    masteredSkipCount.value = 0

    if (!queue.value.length) {
      await loadGlobalSettings()
      toast?.(tr('quiz_no_items', '当前没有可复习题目'), 'err')
      return
    }

    phase.value = 'exam'
    await nextTick()
    prepareQuestion()
  } catch (e) {
    toast?.(`${tr('quiz_load_failed', 'Failed to load quiz data')}: ${e.message}`, 'err')
  } finally {
    sessionStarting.value = false
  }
}

function prepareQuestion() {
  spellingLayout.value = []
  spellingChars.value = []
  spellingRefs.value = []
  sentenceInputs.value = []
  sentenceLens.value = []
  blankRefs.value = []
  stopSentenceAudio()

  const q = currentQuestion.value
  if (!q) return

  if (q.item_type === 'sentence') {
    initSentenceInputs(q)
    nextTick(() => focusBlankCell(0, 0))
  } else {
    initSpellingLayout(q.display_text || q.answer_text || '')
    nextTick(() => focusSpellingSlot(0))
  }

  itemStartedAt.value = Date.now()
}

async function toggleSentenceAudio() {
  const q = currentQuestion.value
  if (!q?.audio_url) {
    toast?.(tr('quiz_audio_not_ready', 'Audio not ready for this sentence yet'), 'err')
    return
  }
  const el = sentenceAudioEl.value
  if (!el) return

  try {
    if (audioPlaying.value) {
      el.pause()
      audioPlaying.value = false
      return
    }

    const src = q.audio_url
    if (el.dataset.src !== src) {
      el.src = `${src}?_ts=${Date.now()}`
      el.dataset.src = src
    }
    el.currentTime = 0
    await el.play()
    audioPlaying.value = true
  } catch {
    audioPlaying.value = false
    toast?.(tr('quiz_audio_play_failed', 'Failed to play audio'), 'err')
  }
}

function stopSentenceAudio() {
  const el = sentenceAudioEl.value
  if (!el) return
  try {
    el.pause()
    el.removeAttribute('src')
    el.load()
  } catch {}
  audioPlaying.value = false
}

function pushGradedRecord(question, gradeResp, userAnswerText) {
  const isSentence = question.item_type === 'sentence'

  examRecords.value.push({
    kind: 'graded',
    item_id: question.id,
    item_type: question.item_type,
    content_key: question.content_key,
    display_text: question.display_text,
    prompt: isSentence ? question.display_text : (question.prompt_text || ''),
    expected: isSentence
      ? (gradeResp.expected_blanks || []).join(' | ')
      : (gradeResp.expected_text || question.display_text || ''),
    user: userAnswerText,
    score: Number(gradeResp.score || 0),
    passed: !!gradeResp.passed,
    masteredActionDone: false,
  })
}

async function submitCurrentAnswer() {
  if (grading.value || !currentQuestion.value || !canSubmitCurrent.value) return

  const q = currentQuestion.value
  grading.value = true
  try {
    const elapsedMs = Math.max(0, Date.now() - itemStartedAt.value)
    const payload = {
      item_id: q.id,
      item_type: q.item_type,
      elapsed_ms: elapsedMs,
      job_id: q.job_id || undefined,
    }

    let userAnswerText = ''
    if (q.item_type === 'sentence') {
      const blanks = collectSentenceAnswers()
      payload.user_blanks = blanks
      payload.mask_indices = q.mask_indices || []
      userAnswerText = blanks.join(' | ').trim()
    } else {
      const answer = getSpellingAnswerText()
      payload.answer_text = answer
      userAnswerText = answer
    }

    const resp = await apiFetch('/api/review/grade', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })

    pushGradedRecord(q, resp, userAnswerText)

    currentQuestionIndex.value += 1
    if (currentQuestionIndex.value >= queue.value.length) {
      stopSentenceAudio()
      phase.value = 'result'
      await loadGlobalSettings()
      return
    }
    await nextTick()
    prepareQuestion()
  } catch (e) {
    toast?.(`${tr('quiz_submit_failed', '提交失败')}: ${e.message}`, 'err')
  } finally {
    grading.value = false
  }
}

async function markCurrentAsMastered() {
  if (grading.value || !currentQuestion.value) return
  const q = currentQuestion.value

  grading.value = true
  try {
    await apiFetch(`/api/review/items/${q.id}/mastered`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        mastered: 1,
        context: 'exam',
        job_id: q.job_id || undefined,
      }),
    })

    masteredSkipCount.value += 1
    examRecords.value.push({
      kind: 'mastered_skip',
      item_id: q.id,
      item_type: q.item_type,
      content_key: q.content_key,
      display_text: q.display_text,
      prompt: q.item_type === 'sentence' ? q.display_text : (q.prompt_text || ''),
      masteredActionDone: true,
    })

    const idx = currentQuestionIndex.value
    const key = q.content_key
    queue.value = queue.value.filter((item, i) => {
      if (i < idx) return true
      if (i === idx) return false
      return item.content_key !== key
    })

    if (idx >= queue.value.length) {
      stopSentenceAudio()
      phase.value = 'result'
      await loadGlobalSettings()
      return
    }

    await nextTick()
    prepareQuestion()
  } catch (e) {
    toast?.(`${tr('quiz_mastered_fail', '加入熟词本失败')}: ${e.message}`, 'err')
  } finally {
    grading.value = false
  }
}

async function markRecordMastered(rec) {
  if (!rec?.item_id || rec.masteredActionDone) return
  try {
    await apiFetch(`/api/review/items/${rec.item_id}/mastered`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mastered: 1, context: 'result' }),
    })
    rec.masteredActionDone = true
    toast?.(tr('quiz_marked_mastered', '已加入熟词本'), 'ok')
  } catch (e) {
    toast?.(`${tr('quiz_mastered_fail', '加入熟词本失败')}: ${e.message}`, 'err')
  }
}

async function loadMasteredItems() {
  if (!isLoggedIn.value) return
  masteredLoading.value = true
  try {
    const q = new URLSearchParams()
    const typeParam = normalizeTypeParam(masteredType.value)
    if (typeParam) q.set('item_type', typeParam)
    if (masteredQ.value.trim()) q.set('q', masteredQ.value.trim())
    q.set('limit', '500')
    const resp = await apiFetch(`/api/review/mastered?${q.toString()}`)
    masteredItems.value = resp.items || []
  } catch (e) {
    toast?.(`${tr('quiz_load_failed', 'Failed to load quiz data')}: ${e.message}`, 'err')
  } finally {
    masteredLoading.value = false
  }
}

async function unmasterItem(item) {
  try {
    await apiFetch(`/api/review/items/${item.id}/mastered`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mastered: 0, context: 'mastered_list' }),
    })
    masteredItems.value = masteredItems.value.filter(x => x.id !== item.id)
  } catch (e) {
    toast?.(`${tr('quiz_unmaster_failed', '取消失败')}: ${e.message}`, 'err')
  }
}

async function openMasteredBoard() {
  phase.value = 'mastered'
  await loadMasteredItems()
}

watch(currentQuestion, () => {
  if (phase.value === 'exam') prepareQuestion()
})

watch(isLoggedIn, async (v) => {
  if (!v) {
    doneJobs.value = []
    resetExamState()
    phase.value = 'select'
    return
  }
  await loadJobs()
  await loadGlobalSettings()
  // Auto-skip job selection when navigated from JobDetail quiz tab
  const qJobId = route.query.jobId
  if (qJobId && route.query.auto === '1') {
    const targetJob = doneJobs.value.find(j => j.id === qJobId)
    if (targetJob) openJobSetup(targetJob)
  }
}, { immediate: true })

onBeforeUnmount(() => {
  stopSentenceAudio()
})
</script>

<style scoped>
.quiz-page {
  max-width: 1020px;
  margin: 0 auto;
  padding: 28px 22px 84px;
}

.module-hub {
  margin-bottom: 14px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.module-card {
  border-radius: 16px;
  border: 1px solid var(--border);
  background: var(--card);
  box-shadow: var(--shadow);
  text-align: left;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  cursor: pointer;
  transition: transform .18s ease, border-color .18s ease, box-shadow .18s ease;
}

.module-card:hover {
  transform: translateY(-2px);
}

.module-card.book {
  background: linear-gradient(140deg, rgba(99, 102, 241, 0.14), rgba(99, 102, 241, 0.05));
  border-color: rgba(99, 102, 241, 0.35);
}

.module-card.global {
  background: linear-gradient(140deg, rgba(236, 72, 153, 0.14), rgba(236, 72, 153, 0.05));
  border-color: rgba(236, 72, 153, 0.28);
}

.module-icon {
  font-size: 30px;
  line-height: 1;
}

.module-title {
  font-size: 20px;
  font-weight: 900;
  color: var(--text);
}

.module-desc {
  font-size: 13px;
  line-height: 1.55;
  color: var(--text2);
}

.panel {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--r);
  box-shadow: var(--shadow);
  padding: 18px;
}

.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}

.panel-head h2 {
  margin: 0;
  font-size: 22px;
  background: linear-gradient(118deg, #0d2f5a 0%, #0b78d1 56%, #f2a82c 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.panel-head p {
  margin: 6px 0 0;
  color: var(--text3);
  font-size: 13px;
}

.empty {
  min-height: 150px;
  display: grid;
  place-items: center;
  text-align: center;
  color: var(--text3);
  gap: 10px;
}

.empty-icon {
  font-size: 46px;
}

.btn {
  border-radius: 10px;
  padding: 9px 14px;
  font-size: 14px;
  font-weight: 700;
  border: 1px solid transparent;
  cursor: pointer;
  transition: all .16s ease;
}

.btn:not(:disabled):hover {
  transform: translateY(-1px);
}

.btn:disabled {
  opacity: .55;
  cursor: not-allowed;
}

.btn.primary {
  color: #fff;
  background: linear-gradient(135deg, var(--accent), var(--accent2));
  box-shadow: 0 8px 24px rgba(99, 102, 241, 0.28);
}

.btn.ghost {
  color: var(--accent);
  background: rgba(99, 102, 241, 0.08);
  border-color: rgba(99, 102, 241, 0.24);
}

.btn.warm {
  color: #fff;
  background: linear-gradient(135deg, #f59e0b, #f97316);
  box-shadow: 0 8px 24px rgba(249, 115, 22, 0.24);
}

.btn.mini {
  padding: 7px 10px;
  font-size: 12px;
}

.job-grid {
  display: grid;
  gap: 10px;
}

.job-card {
  padding: 13px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--bg3);
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  cursor: pointer;
  transition: all .18s ease;
}

.job-card:hover {
  border-color: rgba(99, 102, 241, 0.35);
  transform: translateY(-1px);
}

.job-main h3 {
  margin: 0;
  font-size: 15px;
  color: var(--text);
}

.job-main p {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--text3);
}

.job-date {
  color: var(--text3);
  font-size: 12px;
}

.setup-header h2 {
  margin: 0;
  font-size: 22px;
  background: linear-gradient(118deg, #0d2f5a 0%, #0b78d1 56%, #f2a82c 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.setup-header p {
  margin: 8px 0 0;
  color: var(--text3);
}

.type-grid {
  margin-top: 14px;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.type-card {
  padding: 11px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--bg3);
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  font-weight: 700;
  color: var(--text2);
}

.type-card input {
  width: 16px;
  height: 16px;
}

.field-row {
  margin-top: 12px;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.field-row label {
  color: var(--text3);
  font-size: 13px;
}

.num-input,
.type-select,
.answer-input {
  border: 1px solid var(--border);
  background: var(--bg2);
  color: var(--text);
  border-radius: 10px;
  padding: 9px 12px;
  font-size: 14px;
}

.num-input {
  width: 110px;
}

.answer-input {
  width: 100%;
}

.global-meta {
  margin-top: 14px;
  border: 1px dashed rgba(99, 102, 241, 0.3);
  border-radius: 12px;
  padding: 10px;
  background: rgba(99, 102, 241, 0.04);
}

.quota-row {
  margin-top: 6px;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  color: var(--text3);
}

.setup-actions {
  margin-top: 16px;
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  flex-wrap: wrap;
}

.exam-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.exam-head h2 {
  margin: 0;
  font-size: 20px;
  background: linear-gradient(118deg, #0d2f5a 0%, #0b78d1 56%, #f2a82c 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.exam-head span {
  color: var(--text3);
  font-size: 13px;
  font-weight: 700;
}

.progress-wrap {
  margin-top: 12px;
  height: 10px;
  border-radius: 999px;
  overflow: hidden;
  background: rgba(99, 102, 241, 0.14);
}

.progress-inner {
  height: 100%;
  background: linear-gradient(90deg, var(--accent), var(--accent2));
  transition: width .2s ease;
}

.question-card {
  margin-top: 16px;
  border-radius: 14px;
  border: 1px solid var(--border);
  background: var(--bg3);
  padding: 15px;
}

.question-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.type-chip {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 800;
  color: #fff;
  padding: 4px 10px;
}

.type-chip.word { background: #0ea5a4; }
.type-chip.expression { background: #ec4899; }
.type-chip.sentence { background: #6366f1; }

.prompt-text {
  margin: 14px 0 10px;
  font-size: 22px;
  font-weight: 800;
  color: var(--text);
}

.spelling-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.sp-sep {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 12px;
  color: var(--text3);
  font-size: 18px;
  font-weight: 700;
}

.sp-sep.space {
  min-width: 16px;
}

.cell-input {
  width: 38px;
  height: 46px;
  border-radius: 12px;
  border: 1px solid rgba(99, 102, 241, 0.28);
  background: #fff;
  color: var(--accent);
  text-align: center;
  font-size: 22px;
  font-weight: 800;
  outline: none;
}

.cell-input:focus {
  border-color: rgba(99, 102, 241, 0.8);
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.14);
}

.audio-row {
  margin-top: 10px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}

.audio-note {
  font-size: 12px;
  color: var(--text3);
}

.cloze-wrap {
  margin-top: 14px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px 8px;
  line-height: 1.75;
}

.seg-text {
  font-size: 20px;
  color: var(--text);
}

.blank-word {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 8px;
  border-radius: 999px;
  border: 1px solid rgba(99, 102, 241, 0.22);
  background: rgba(99, 102, 241, 0.08);
}

.blank-cell {
  width: 30px;
  height: 38px;
  font-size: 18px;
  border-radius: 9px;
}

.submit-row {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.hidden-audio {
  display: none;
}

.score-head {
  width: 132px;
  height: 132px;
  margin: 4px auto 14px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, var(--accent), var(--accent2));
  color: #fff;
  box-shadow: 0 12px 28px rgba(99, 102, 241, 0.25);
}

.score-value {
  font-size: 42px;
  font-weight: 900;
  line-height: 1;
}

.score-label {
  font-size: 13px;
}

.result-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.stat {
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--bg3);
  text-align: center;
  padding: 10px;
}

.stat strong {
  display: block;
  font-size: 23px;
  color: var(--text);
}

.stat span {
  font-size: 12px;
  color: var(--text3);
}

.global-hint-card {
  margin-top: 14px;
  padding: 14px;
  border-radius: 13px;
  border: 1px solid rgba(99, 102, 241, 0.25);
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.10), rgba(167, 139, 250, 0.09));
}

.global-hint-card h3 {
  margin: 0;
  font-size: 18px;
  background: linear-gradient(118deg, #0d2f5a 0%, #0b78d1 56%, #f2a82c 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.global-hint-card p {
  margin: 8px 0 12px;
  color: var(--text2);
  font-size: 14px;
  line-height: 1.6;
}

.record-list {
  margin-top: 14px;
  display: grid;
  gap: 10px;
}

.record-item {
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--bg3);
  padding: 11px;
}

.record-item.mastered_skip {
  border-style: dashed;
  background: rgba(249, 115, 22, 0.08);
}

.record-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.record-score {
  color: var(--text3);
  font-size: 12px;
  font-weight: 700;
}

.record-main {
  margin: 8px 0 0;
  font-size: 15px;
  font-weight: 700;
  color: var(--text);
}

.record-sub {
  margin: 6px 0 0;
  color: var(--text3);
  font-size: 12px;
}

.record-actions {
  margin-top: 8px;
}

.mastered-head {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.mastered-head h2 {
  margin: 0;
  font-size: 22px;
  background: linear-gradient(118deg, #0d2f5a 0%, #0b78d1 56%, #f2a82c 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.mastered-tools {
  display: grid;
  grid-template-columns: 1fr 150px auto;
  gap: 10px;
}

.mastered-grid {
  margin-top: 12px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.mastered-card {
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--bg3);
  padding: 11px;
}

@media (max-width: 900px) {
  .quiz-page {
    padding: 20px 12px 76px;
  }

  .module-hub {
    grid-template-columns: 1fr;
  }

  .panel-head {
    flex-direction: column;
    align-items: flex-start;
  }

  .type-grid {
    grid-template-columns: 1fr;
  }

  .result-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .mastered-tools {
    grid-template-columns: 1fr;
  }

  .mastered-grid {
    grid-template-columns: 1fr;
  }

  .seg-text {
    font-size: 18px;
  }
}
</style>
